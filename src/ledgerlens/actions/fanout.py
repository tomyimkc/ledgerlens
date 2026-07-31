"""Bounded action fanout with ordered, sanitized per-target results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .auth import ActionAuthorization
from .base import ActionAdapter
from .errors import ActionError
from .models import ActionPreview, ActionReceipt, BaseAction


@dataclass(frozen=True)
class ActionInvocation:
    """One adapter/action/authorization tuple for fanout execution."""

    adapter: ActionAdapter[Any]
    action: BaseAction
    authorization: ActionAuthorization


class ActionFailure(BaseModel):
    """Sanitized failure safe for logs and API responses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_type: str
    message: str
    retryable: bool = False
    outcome_unknown: bool = False
    http_status: int | None = Field(default=None, ge=100, le=599)


class ActionFanoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    adapter: str
    preview: ActionPreview | None = None
    receipt: ActionReceipt | None = None
    failure: ActionFailure | None = None


class ActionFanoutReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[ActionFanoutItem, ...]

    @property
    def receipts(self) -> tuple[ActionReceipt, ...]:
        return tuple(item.receipt for item in self.items if item.receipt is not None)

    @property
    def failures(self) -> tuple[ActionFailure, ...]:
        return tuple(item.failure for item in self.items if item.failure is not None)

    @property
    def succeeded(self) -> bool:
        return not self.failures


class ActionFanoutExecutor:
    """Execute independent actions concurrently while preserving input order."""

    def __init__(self, *, max_workers: int = 4) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.max_workers = max_workers

    def preview(self, invocations: list[ActionInvocation]) -> tuple[ActionPreview, ...]:
        return tuple(invocation.adapter.preview(invocation.action) for invocation in invocations)

    def execute(self, invocations: list[ActionInvocation]) -> ActionFanoutReport:
        if not invocations:
            return ActionFanoutReport(items=())
        worker_count = min(self.max_workers, len(invocations))
        items: list[ActionFanoutItem | None] = [None] * len(invocations)
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="ledgerlens-action",
        ) as pool:
            future_to_index = {
                pool.submit(self._execute_one, index, invocation): index
                for index, invocation in enumerate(invocations)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                items[index] = future.result()
        return ActionFanoutReport(items=tuple(item for item in items if item is not None))

    @staticmethod
    def _execute_one(index: int, invocation: ActionInvocation) -> ActionFanoutItem:
        adapter_name = getattr(invocation.adapter, "name", "unknown")
        try:
            preview = invocation.adapter.preview(invocation.action)
            receipt = invocation.adapter.execute(
                invocation.action,
                invocation.authorization,
            )
            return ActionFanoutItem(
                index=index,
                adapter=adapter_name,
                preview=preview,
                receipt=receipt,
            )
        except Exception as exc:
            preview = None
            with suppress(Exception):
                preview = invocation.adapter.preview(invocation.action)
            return ActionFanoutItem(
                index=index,
                adapter=adapter_name,
                preview=preview,
                failure=_sanitized_failure(exc),
            )


def _sanitized_failure(exc: Exception) -> ActionFailure:
    if isinstance(exc, ActionError):
        return ActionFailure(
            error_type=type(exc).__name__,
            message=str(exc),
            retryable=bool(getattr(exc, "retryable", False)),
            outcome_unknown=bool(getattr(exc, "outcome_unknown", False)),
            http_status=getattr(exc, "status_code", None),
        )
    return ActionFailure(
        error_type=type(exc).__name__,
        message="unexpected action execution failure",
    )
