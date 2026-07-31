"""Shared typed adapter protocol and safety-gated execution lifecycle."""

from __future__ import annotations

import random
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import JsonValue

from .auth import ActionAuthorization, ActionAuthorizer, Clock, utc_now
from .errors import ActionIndeterminateError, ActionOutcomeUnknownError
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore
from .models import (
    ActionExecutionStatus,
    ActionPreview,
    ActionReceipt,
    BaseAction,
    action_digest,
    normalized_idempotency_key,
    sanitized_remote_url,
)
from .transport import (
    HttpRequest,
    HttpResponse,
    HttpTransport,
    HttpxTransport,
    RetryingHttpExecutor,
    RetryPolicy,
)

ActionT = TypeVar("ActionT", bound=BaseAction)
ActionT_contra = TypeVar("ActionT_contra", bound=BaseAction, contravariant=True)


@runtime_checkable
class ActionAdapter(Protocol[ActionT_contra]):
    """Typed contract implemented by all external-action adapters."""

    name: str
    operation: str

    def preview(self, action: ActionT_contra) -> ActionPreview: ...

    def execute(
        self,
        action: ActionT_contra,
        authorization: ActionAuthorization,
    ) -> ActionReceipt: ...


@dataclass(frozen=True)
class ReceiptFields:
    remote_id: str | None = None
    remote_url: str | None = None
    details: dict[str, JsonValue] | None = None


class BaseActionAdapter(ABC, Generic[ActionT]):
    """Common authorization, deduplication, retry, and receipt machinery."""

    name: str
    operation: str
    action_type: type[ActionT]

    def __init__(
        self,
        *,
        authorizer: ActionAuthorizer,
        transport: HttpTransport | None = None,
        idempotency_store: IdempotencyStore | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: float = 8.0,
        clock: Clock = utc_now,
        sleep: Callable[[float], None] | None = None,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.authorizer = authorizer
        self.timeout = timeout
        self._clock = clock
        self._transport = transport or HttpxTransport()
        self._owns_transport = transport is None
        self.idempotency_store = idempotency_store or InMemoryIdempotencyStore()
        self._http = RetryingHttpExecutor(
            self._transport,
            retry_policy=retry_policy,
            sleep=sleep or time.sleep,
            random_source=random_source or random.random,
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"

    def close(self) -> None:
        if self._owns_transport and isinstance(self._transport, HttpxTransport):
            self._transport.close()

    def __enter__(self) -> BaseActionAdapter[ActionT]:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def preview(self, action: ActionT) -> ActionPreview:
        self._validate_action_type(action)
        target = self._target(action)
        payload = self._preview_payload(action)
        digest = action_digest(
            adapter=self.name,
            operation=self.operation,
            target=target,
            payload=payload,
        )
        return ActionPreview(
            adapter=self.name,
            operation=self.operation,
            target=target,
            summary=self._summary(action),
            payload=payload,
            action_digest=digest,
            idempotency_key=normalized_idempotency_key(action.idempotency_key, digest),
        )

    def execute(
        self,
        action: ActionT,
        authorization: ActionAuthorization,
    ) -> ActionReceipt:
        preview = self.preview(action)
        self.authorizer.verify(authorization, preview)
        store_key = self._store_key(preview)
        claim = self.idempotency_store.claim(store_key, preview.action_digest)
        if not claim.is_new:
            if claim.receipt is None:
                raise AssertionError("deduplicated claim is missing its receipt")
            return claim.receipt.model_copy(
                update={
                    "status": ActionExecutionStatus.DEDUPLICATED,
                    "attempts": 0,
                    "deduplicated_from": claim.receipt.receipt_id,
                }
            )

        try:
            request = self._build_request(action, preview)
            result = self._http.execute(
                request,
                retry_ambiguous_failures=self._has_remote_idempotency(action, preview),
            )
            fields = self._parse_response(action, preview, result.response, result.attempts)
            receipt = ActionReceipt(
                receipt_id=self._receipt_id(preview, fields.remote_id),
                adapter=self.name,
                operation=self.operation,
                target=preview.target,
                action_digest=preview.action_digest,
                idempotency_key=preview.idempotency_key,
                status=ActionExecutionStatus.EXECUTED,
                http_status=result.response.status_code,
                attempts=result.attempts,
                remote_id=fields.remote_id,
                remote_url=sanitized_remote_url(fields.remote_url),
                completed_at=self._clock(),
                details=fields.details or {},
            )
        except ActionOutcomeUnknownError:
            self.idempotency_store.mark_indeterminate(store_key, preview.action_digest)
            raise
        except Exception:
            self.idempotency_store.release(store_key, preview.action_digest)
            raise
        try:
            self.idempotency_store.complete(store_key, preview.action_digest, receipt)
        except Exception as exc:
            with suppress(Exception):
                self.idempotency_store.mark_indeterminate(store_key, preview.action_digest)
            raise ActionIndeterminateError(
                "provider accepted the action but its durable receipt could not be recorded"
            ) from exc
        return receipt

    def _validate_action_type(self, action: ActionT) -> None:
        if not isinstance(action, self.action_type):
            raise TypeError(f"{type(self).__name__} requires {self.action_type.__name__}")

    def _store_key(self, preview: ActionPreview) -> str:
        return f"{preview.adapter}:{preview.operation}:{preview.target}:{preview.idempotency_key}"

    @staticmethod
    def _receipt_id(preview: ActionPreview, remote_id: str | None) -> str:
        value = f"{preview.adapter}:{preview.idempotency_key}:{remote_id or 'accepted'}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, value))

    @abstractmethod
    def _target(self, action: ActionT) -> str: ...

    @abstractmethod
    def _summary(self, action: ActionT) -> str: ...

    @abstractmethod
    def _preview_payload(self, action: ActionT) -> dict[str, JsonValue]: ...

    @abstractmethod
    def _build_request(self, action: ActionT, preview: ActionPreview) -> HttpRequest: ...

    @abstractmethod
    def _parse_response(
        self,
        action: ActionT,
        preview: ActionPreview,
        response: HttpResponse,
        attempts: int,
    ) -> ReceiptFields: ...

    def _has_remote_idempotency(
        self,
        action: ActionT,
        preview: ActionPreview,
    ) -> bool:
        return False
