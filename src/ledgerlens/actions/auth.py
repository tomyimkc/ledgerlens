"""HMAC-signed, action-bound authorization objects."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pydantic import JsonValue

from .errors import ActionAuthorizationError
from .models import ActionPreview, canonical_json

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ActionAuthorization:
    """Typed authorization bound to one exact preview and expiry window.

    ``signature`` is intentionally omitted from ``repr``. The authorization is
    not a credential for a provider, but avoiding incidental logging still
    reduces replay opportunities.
    """

    authorization_id: str
    issuer: str
    subject: str
    adapter: str
    operation: str
    action_digest: str
    idempotency_key: str
    issued_at: datetime
    expires_at: datetime
    signature: str = field(repr=False)
    algorithm: str = "hmac-sha256-v1"

    def signing_claims(self) -> dict[str, JsonValue]:
        return {
            "algorithm": self.algorithm,
            "authorization_id": self.authorization_id,
            "issuer": self.issuer,
            "subject": self.subject,
            "adapter": self.adapter,
            "operation": self.operation,
            "action_digest": self.action_digest,
            "idempotency_key": self.idempotency_key,
            "issued_at": int(self.issued_at.timestamp()),
            "expires_at": int(self.expires_at.timestamp()),
        }


class ActionAuthorizer:
    """Issues and verifies short-lived HMAC authorizations.

    The signing secret belongs in trusted orchestration code, never in an LLM
    prompt or generated action payload.
    """

    def __init__(
        self,
        signing_secret: bytes | str,
        *,
        issuer: str = "ledgerlens",
        clock: Clock = utc_now,
        max_ttl: timedelta = timedelta(minutes=15),
        allowed_clock_skew: timedelta = timedelta(seconds=30),
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        secret_bytes = (
            signing_secret.encode("utf-8")
            if isinstance(signing_secret, str)
            else bytes(signing_secret)
        )
        if len(secret_bytes) < 32:
            raise ValueError("signing_secret must contain at least 32 bytes")
        if not issuer.strip():
            raise ValueError("issuer cannot be blank")
        if max_ttl <= timedelta(0):
            raise ValueError("max_ttl must be positive")
        self._secret = secret_bytes
        self.issuer = issuer.strip()
        self._clock = clock
        self._max_ttl = max_ttl
        self._allowed_clock_skew = allowed_clock_skew
        self._nonce_factory = nonce_factory or (lambda: secrets.token_urlsafe(18))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(issuer={self.issuer!r})"

    def issue(
        self,
        preview: ActionPreview,
        *,
        subject: str,
        ttl: timedelta = timedelta(minutes=5),
        authorization_id: str | None = None,
        now: datetime | None = None,
    ) -> ActionAuthorization:
        """Authorize exactly one typed preview for a bounded interval."""

        if not isinstance(preview, ActionPreview):
            raise TypeError("preview must be an ActionPreview")
        if not subject.strip():
            raise ValueError("subject cannot be blank")
        if ttl <= timedelta(0) or ttl > self._max_ttl:
            raise ValueError("authorization ttl is outside the configured bounds")
        issued_at = _aware_utc(now or self._clock())
        authorization = ActionAuthorization(
            authorization_id=authorization_id or self._nonce_factory(),
            issuer=self.issuer,
            subject=subject.strip(),
            adapter=preview.adapter,
            operation=preview.operation,
            action_digest=preview.action_digest,
            idempotency_key=preview.idempotency_key,
            issued_at=issued_at,
            expires_at=issued_at + ttl,
            signature="",
        )
        return ActionAuthorization(
            **{
                **authorization.__dict__,
                "signature": self._sign(authorization.signing_claims()),
            }
        )

    def verify(
        self,
        authorization: ActionAuthorization,
        preview: ActionPreview,
        *,
        now: datetime | None = None,
    ) -> None:
        """Fail closed unless the signed object matches the exact preview."""

        if not isinstance(authorization, ActionAuthorization):
            raise ActionAuthorizationError(
                "external actions require a typed ActionAuthorization object"
            )
        if not isinstance(preview, ActionPreview):
            raise TypeError("preview must be an ActionPreview")
        current = _aware_utc(now or self._clock())
        issued_at = _aware_utc(authorization.issued_at)
        expires_at = _aware_utc(authorization.expires_at)
        if authorization.algorithm != "hmac-sha256-v1":
            raise ActionAuthorizationError("unsupported authorization algorithm")
        if authorization.issuer != self.issuer:
            raise ActionAuthorizationError("authorization issuer does not match")
        if issued_at > current + self._allowed_clock_skew:
            raise ActionAuthorizationError("authorization is not active yet")
        if expires_at <= current:
            raise ActionAuthorizationError("authorization has expired")
        if expires_at - issued_at > self._max_ttl:
            raise ActionAuthorizationError("authorization ttl exceeds policy")
        expected_binding = (
            preview.adapter,
            preview.operation,
            preview.action_digest,
            preview.idempotency_key,
        )
        actual_binding = (
            authorization.adapter,
            authorization.operation,
            authorization.action_digest,
            authorization.idempotency_key,
        )
        if actual_binding != expected_binding:
            raise ActionAuthorizationError("authorization does not match this action")
        expected_signature = self._sign(authorization.signing_claims())
        if not hmac.compare_digest(authorization.signature, expected_signature):
            raise ActionAuthorizationError("authorization signature is invalid")

    def _sign(self, claims: dict[str, JsonValue]) -> str:
        digest = hmac.new(self._secret, canonical_json(claims), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("authorization timestamps must be timezone-aware")
    return value.astimezone(UTC)
