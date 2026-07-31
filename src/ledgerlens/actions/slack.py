"""Safety-gated Slack incoming-webhook and Web API adapter."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from enum import StrEnum

from pydantic import Field, JsonValue, SecretStr, field_validator

from .auth import ActionAuthorizer, Clock, utc_now
from .base import BaseActionAdapter, ReceiptFields
from .errors import ActionHTTPError, ActionProviderError, ActionValidationError
from .idempotency import IdempotencyStore
from .models import ActionPreview, BaseAction
from .transport import HttpRequest, HttpResponse, HttpTransport, RetryPolicy

_CLIENT_MESSAGE_NAMESPACE = uuid.UUID("69cdf4a0-d95c-47ad-a253-1289abc9c389")


class SlackMode(StrEnum):
    WEBHOOK = "webhook"
    API = "api"


class SlackMessageAction(BaseAction):
    text: str = Field(min_length=1, max_length=40_000)
    channel: str | None = Field(default=None, min_length=1, max_length=255)
    blocks: tuple[dict[str, JsonValue], ...] = ()
    thread_ts: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("channel")
    @classmethod
    def reject_channel_newlines(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n"):
            raise ValueError("Slack channel cannot contain newlines")
        return value


class SlackAdapter(BaseActionAdapter[SlackMessageAction]):
    """Post through either an incoming webhook or ``chat.postMessage``."""

    name = "slack"
    operation = "post_message"
    action_type = SlackMessageAction

    def __init__(
        self,
        *,
        authorizer: ActionAuthorizer,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        api_url: str = "https://slack.com/api/chat.postMessage",
        transport: HttpTransport | None = None,
        idempotency_store: IdempotencyStore | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: float = 8.0,
        clock: Clock = utc_now,
        sleep: Callable[[float], None] | None = None,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        if bool(webhook_url) == bool(bot_token):
            raise ValueError("configure exactly one of webhook_url or bot_token")
        self.mode = SlackMode.WEBHOOK if webhook_url else SlackMode.API
        self._webhook_url = SecretStr(webhook_url) if webhook_url else None
        self._bot_token = SecretStr(bot_token) if bot_token else None
        self.api_url = api_url
        super().__init__(
            authorizer=authorizer,
            transport=transport,
            idempotency_store=idempotency_store,
            retry_policy=retry_policy,
            timeout=timeout,
            clock=clock,
            sleep=sleep,
            random_source=random_source,
        )

    def _target(self, action: SlackMessageAction) -> str:
        if self.mode is SlackMode.WEBHOOK:
            return "slack:webhook"
        if not action.channel:
            raise ActionValidationError("Slack Web API actions require a channel")
        return f"slack:channel:{action.channel}"

    def _summary(self, action: SlackMessageAction) -> str:
        if self.mode is SlackMode.WEBHOOK:
            return "Post message to configured Slack webhook"
        return f"Post message to Slack channel {action.channel}"

    def _preview_payload(self, action: SlackMessageAction) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"text": action.text}
        if self.mode is SlackMode.API:
            if not action.channel:
                raise ActionValidationError("Slack Web API actions require a channel")
            payload["channel"] = action.channel
        if action.blocks:
            payload["blocks"] = list(action.blocks)
        if action.thread_ts:
            payload["thread_ts"] = action.thread_ts
        return payload

    def _build_request(
        self,
        action: SlackMessageAction,
        preview: ActionPreview,
    ) -> HttpRequest:
        body: dict[str, JsonValue] = {"text": action.text}
        if action.blocks:
            body["blocks"] = list(action.blocks)
        if action.thread_ts:
            body["thread_ts"] = action.thread_ts
        if self.mode is SlackMode.WEBHOOK:
            assert self._webhook_url is not None
            return HttpRequest(
                adapter=self.name,
                method="POST",
                url=self._webhook_url.get_secret_value(),
                headers={"Content-Type": "application/json"},
                json_body=body,
                timeout=self.timeout,
            )

        assert self._bot_token is not None
        assert action.channel is not None
        body["channel"] = action.channel
        body["client_msg_id"] = str(uuid.uuid5(_CLIENT_MESSAGE_NAMESPACE, preview.idempotency_key))
        return HttpRequest(
            adapter=self.name,
            method="POST",
            url=self.api_url,
            headers={
                "Authorization": f"Bearer {self._bot_token.get_secret_value()}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json_body=body,
            timeout=self.timeout,
        )

    def _parse_response(
        self,
        action: SlackMessageAction,
        preview: ActionPreview,
        response: HttpResponse,
        attempts: int,
    ) -> ReceiptFields:
        del action, preview
        if not 200 <= response.status_code < 300:
            raise ActionHTTPError(
                self.name,
                response.status_code,
                attempts=attempts,
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        if self.mode is SlackMode.WEBHOOK:
            if response.text.strip().casefold() != "ok":
                raise ActionProviderError(self.name, "webhook_rejected")
            return ReceiptFields(details={"mode": self.mode.value, "delivery": "accepted"})

        data = response.json_body if isinstance(response.json_body, dict) else {}
        if data.get("ok") is not True:
            code = data.get("error")
            raise ActionProviderError(
                self.name,
                code if isinstance(code, str) and code.isidentifier() else "api_rejected",
            )
        channel = data.get("channel")
        timestamp = data.get("ts")
        details: dict[str, JsonValue] = {"mode": self.mode.value}
        if isinstance(channel, str):
            details["channel"] = channel
        if isinstance(timestamp, str):
            details["timestamp"] = timestamp
        return ReceiptFields(
            remote_id=timestamp if isinstance(timestamp, str) else None,
            details=details,
        )

    def _has_remote_idempotency(
        self,
        action: SlackMessageAction,
        preview: ActionPreview,
    ) -> bool:
        del action, preview
        return self.mode is SlackMode.API
