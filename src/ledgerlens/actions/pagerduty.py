"""Safety-gated PagerDuty Events API v2 adapter."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import Field, JsonValue, SecretStr, model_validator

from .auth import ActionAuthorizer, Clock, utc_now
from .base import BaseActionAdapter, ReceiptFields
from .errors import ActionHTTPError, ActionProviderError
from .idempotency import IdempotencyStore
from .models import ActionPreview, BaseAction
from .transport import HttpRequest, HttpResponse, HttpTransport, RetryPolicy


class PagerDutyEventActionType(StrEnum):
    TRIGGER = "trigger"
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"


class PagerDutySeverity(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class PagerDutyEventAction(BaseAction):
    event_action: PagerDutyEventActionType = PagerDutyEventActionType.TRIGGER
    summary: str | None = Field(default=None, min_length=1, max_length=1024)
    source: str | None = Field(default=None, min_length=1, max_length=1024)
    severity: PagerDutySeverity | None = None
    dedup_key: str | None = Field(default=None, min_length=1, max_length=255)
    component: str | None = Field(default=None, max_length=1024)
    group: str | None = Field(default=None, max_length=1024)
    event_class: str | None = Field(default=None, max_length=1024)
    custom_details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_shape(self) -> PagerDutyEventAction:
        if self.event_action is PagerDutyEventActionType.TRIGGER:
            if not self.summary or not self.source or self.severity is None:
                raise ValueError("trigger events require summary, source, and severity")
        elif not self.dedup_key:
            raise ValueError("acknowledge and resolve events require dedup_key")
        return self


class PagerDutyEventsAdapter(BaseActionAdapter[PagerDutyEventAction]):
    """Send trigger/acknowledge/resolve events with provider-native dedup keys."""

    name = "pagerduty"
    operation = "send_event"
    action_type = PagerDutyEventAction

    def __init__(
        self,
        routing_key: str,
        *,
        authorizer: ActionAuthorizer,
        endpoint: str = "https://events.pagerduty.com/v2/enqueue",
        transport: HttpTransport | None = None,
        idempotency_store: IdempotencyStore | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: float = 8.0,
        clock: Clock = utc_now,
        sleep: Callable[[float], None] | None = None,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        if not routing_key:
            raise ValueError("PagerDuty routing_key cannot be blank")
        self._routing_key = SecretStr(routing_key)
        self.endpoint = endpoint
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

    def _target(self, action: PagerDutyEventAction) -> str:
        del action
        return "pagerduty:events-v2"

    def _summary(self, action: PagerDutyEventAction) -> str:
        return f"Send PagerDuty {action.event_action.value} event"

    def _preview_payload(self, action: PagerDutyEventAction) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"event_action": action.event_action.value}
        if action.dedup_key:
            payload["dedup_key"] = action.dedup_key
        if action.event_action is PagerDutyEventActionType.TRIGGER:
            assert action.summary is not None
            assert action.source is not None
            assert action.severity is not None
            event_payload: dict[str, JsonValue] = {
                "summary": action.summary,
                "source": action.source,
                "severity": action.severity.value,
            }
            if action.component:
                event_payload["component"] = action.component
            if action.group:
                event_payload["group"] = action.group
            if action.event_class:
                event_payload["class"] = action.event_class
            if action.custom_details:
                event_payload["custom_details"] = action.custom_details
            payload["payload"] = event_payload
        return payload

    def _build_request(
        self,
        action: PagerDutyEventAction,
        preview: ActionPreview,
    ) -> HttpRequest:
        body = self._preview_payload(action)
        body["routing_key"] = self._routing_key.get_secret_value()
        body["dedup_key"] = action.dedup_key or preview.idempotency_key
        return HttpRequest(
            adapter=self.name,
            method="POST",
            url=self.endpoint,
            headers={"Content-Type": "application/json"},
            json_body=body,
            timeout=self.timeout,
        )

    def _parse_response(
        self,
        action: PagerDutyEventAction,
        preview: ActionPreview,
        response: HttpResponse,
        attempts: int,
    ) -> ReceiptFields:
        del action
        if response.status_code != 202:
            raise ActionHTTPError(
                self.name,
                response.status_code,
                attempts=attempts,
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        data = response.json_body if isinstance(response.json_body, dict) else {}
        status = data.get("status")
        if isinstance(status, str) and status.casefold() not in {"success", "ok"}:
            raise ActionProviderError(self.name, "event_rejected")
        dedup_key = data.get("dedup_key")
        if not isinstance(dedup_key, str):
            dedup_key = preview.idempotency_key
        return ReceiptFields(
            remote_id=dedup_key,
            details={"event_action": preview.payload["event_action"], "delivery": "accepted"},
        )

    def _has_remote_idempotency(
        self,
        action: PagerDutyEventAction,
        preview: ActionPreview,
    ) -> bool:
        del action, preview
        return True
