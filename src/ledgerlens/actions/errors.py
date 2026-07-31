"""Typed, deliberately non-sensitive failures for external actions."""

from __future__ import annotations


class ActionError(RuntimeError):
    """Base class for action failures whose messages are safe to surface."""


class ActionValidationError(ActionError):
    """Raised when an action cannot be represented safely for a provider."""


class ActionAuthorizationError(ActionError):
    """Raised when an authorization is missing, invalid, mismatched, or expired."""


class IdempotencyError(ActionError):
    """Base class for idempotency-state failures."""


class IdempotencyConflictError(IdempotencyError):
    """Raised when one idempotency key is reused for a different action."""


class ActionInProgressError(IdempotencyError):
    """Raised when the same action is already being executed."""


class ActionIndeterminateError(IdempotencyError):
    """Raised when a prior unsafe request may have reached the provider."""


class ActionTransportError(ActionError):
    """Raised for a transport failure after bounded retry handling."""

    def __init__(
        self,
        adapter: str,
        *,
        attempts: int,
        retryable: bool,
        outcome_unknown: bool = False,
    ) -> None:
        self.adapter = adapter
        self.attempts = attempts
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown
        qualifier = " with an unknown remote outcome" if outcome_unknown else ""
        super().__init__(f"{adapter} transport failed after {attempts} attempt(s){qualifier}")


class ActionOutcomeUnknownError(ActionTransportError):
    """Raised when retrying could duplicate an action without provider deduplication."""

    def __init__(self, adapter: str, *, attempts: int) -> None:
        super().__init__(
            adapter,
            attempts=attempts,
            retryable=False,
            outcome_unknown=True,
        )


class ActionHTTPError(ActionError):
    """Raised when a provider returns a non-success HTTP status."""

    def __init__(
        self,
        adapter: str,
        status_code: int,
        *,
        attempts: int,
        retryable: bool,
    ) -> None:
        self.adapter = adapter
        self.status_code = status_code
        self.attempts = attempts
        self.retryable = retryable
        self.outcome_unknown = False
        super().__init__(
            f"{adapter} action was rejected with HTTP {status_code} after {attempts} attempt(s)"
        )


class ActionProviderError(ActionError):
    """Raised for a sanitized provider-level rejection in a successful HTTP response."""

    def __init__(self, adapter: str, code: str = "provider_rejected") -> None:
        self.adapter = adapter
        self.code = code
        self.retryable = False
        self.outcome_unknown = False
        super().__init__(f"{adapter} action was rejected by the provider ({code})")
