"""Shared action request, preview, and receipt models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class ActionExecutionStatus(StrEnum):
    """Terminal status represented by a sanitized action receipt."""

    EXECUTED = "executed"
    DEDUPLICATED = "deduplicated"


class BaseAction(BaseModel):
    """Base for typed provider actions.

    A caller-provided idempotency key is hashed before it reaches previews,
    authorization claims, stores, or receipts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("idempotency_key")
    @classmethod
    def reject_blank_idempotency_key(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("idempotency_key cannot be blank")
        return value


class ActionPreview(BaseModel):
    """Deterministic, credential-free representation of a proposed side effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    payload: dict[str, JsonValue]
    action_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^(action|user)-sha256:[0-9a-f]{64}$")
    requires_authorization: bool = True


class ActionReceipt(BaseModel):
    """Sanitized evidence that an external action executed or was deduplicated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    action_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^(action|user)-sha256:[0-9a-f]{64}$")
    status: ActionExecutionStatus
    http_status: int | None = Field(default=None, ge=100, le=599)
    attempts: int = Field(ge=0)
    remote_id: str | None = None
    remote_url: str | None = None
    completed_at: datetime
    details: dict[str, JsonValue] = Field(default_factory=dict)
    deduplicated_from: str | None = None

    @property
    def deduplicated(self) -> bool:
        return self.status is ActionExecutionStatus.DEDUPLICATED


def canonical_json(value: JsonValue | dict[str, JsonValue]) -> bytes:
    """Serialize JSON deterministically for signing and action digests."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def action_digest(
    *,
    adapter: str,
    operation: str,
    target: str,
    payload: dict[str, JsonValue],
) -> str:
    material: dict[str, JsonValue] = {
        "adapter": adapter,
        "operation": operation,
        "target": target,
        "payload": payload,
    }
    return "sha256:" + hashlib.sha256(canonical_json(material)).hexdigest()


def normalized_idempotency_key(raw_key: str | None, digest: str) -> str:
    if raw_key is None:
        return "action-sha256:" + digest.removeprefix("sha256:")
    return "user-sha256:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def sanitized_remote_url(value: str | None) -> str | None:
    """Keep a navigable URL while dropping credentials, query strings, and fragments."""

    if value is None:
        return None
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.casefold() not in {"http", "https"} or hostname is None:
        return None
    safe_host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{safe_host}:{port}" if port is not None else safe_host
    return urlunsplit((parts.scheme.casefold(), netloc, parts.path, "", ""))
