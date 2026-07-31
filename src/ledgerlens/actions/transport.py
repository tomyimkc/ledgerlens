"""Secret-opaque HTTP transport with bounded retries and injectable timing."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from pydantic import JsonValue

from .errors import ActionOutcomeUnknownError, ActionTransportError

_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HttpRequest:
    """HTTP request whose repr never exposes URL credentials, headers, or body."""

    adapter: str
    method: str
    url: str = field(repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    json_body: dict[str, JsonValue] | None = field(default=None, repr=False)
    timeout: float = 8.0


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    json_body: JsonValue = field(default=None, repr=False)
    text: str = field(default="", repr=False)

    def header(self, name: str) -> str | None:
        wanted = name.casefold()
        return next(
            (value for key, value in self.headers.items() if key.casefold() == wanted),
            None,
        )


class TransportConnectionFailure(OSError):
    """Connection could not be established; the action was not sent."""


class TransportTimeoutFailure(TimeoutError):
    """The request timed out and may have reached the provider."""


class TransportFailure(OSError):
    """Other transport failure with an unknown provider outcome."""


class HttpTransport(Protocol):
    def request(self, request: HttpRequest) -> HttpResponse: ...


class HttpxTransport:
    """Production synchronous transport backed by ``httpx.Client``."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request(self, request: HttpRequest) -> HttpResponse:
        try:
            response = self._client.request(
                request.method,
                request.url,
                headers=request.headers,
                json=request.json_body,
                timeout=request.timeout,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise TransportConnectionFailure("connection failed") from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise TransportTimeoutFailure("request timed out") from exc
        except httpx.PoolTimeout as exc:
            raise TransportConnectionFailure("connection pool timed out") from exc
        except httpx.HTTPError as exc:
            raise TransportFailure("HTTP transport failed") from exc
        try:
            json_body: JsonValue = response.json()
        except ValueError:
            json_body = None
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            json_body=json_body,
            text=response.text,
        )


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff policy."""

    max_attempts: int = 3
    initial_backoff: float = 0.25
    max_backoff: float = 2.0
    jitter_ratio: float = 0.1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff < 0 or self.max_backoff < 0:
            raise ValueError("backoff values cannot be negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")


@dataclass(frozen=True)
class TransportResult:
    response: HttpResponse
    attempts: int


class RetryingHttpExecutor:
    """Executes requests without ever formatting secret-bearing request values."""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        self.transport = transport
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._random = random_source

    def execute(
        self,
        request: HttpRequest,
        *,
        retry_ambiguous_failures: bool,
    ) -> TransportResult:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = self.transport.request(request)
            except TransportConnectionFailure as exc:
                if attempt >= self.retry_policy.max_attempts:
                    raise ActionTransportError(
                        request.adapter,
                        attempts=attempt,
                        retryable=True,
                    ) from exc
                self._sleep(self._delay(attempt))
                continue
            except (TransportTimeoutFailure, TransportFailure) as exc:
                if not retry_ambiguous_failures:
                    raise ActionOutcomeUnknownError(
                        request.adapter,
                        attempts=attempt,
                    ) from exc
                if attempt >= self.retry_policy.max_attempts:
                    raise ActionTransportError(
                        request.adapter,
                        attempts=attempt,
                        retryable=True,
                    ) from exc
                self._sleep(self._delay(attempt))
                continue

            if (
                response.status_code in _RETRYABLE_STATUSES
                and attempt < self.retry_policy.max_attempts
            ):
                self._sleep(self._retry_after(response) or self._delay(attempt))
                continue
            return TransportResult(response=response, attempts=attempt)

        raise AssertionError("retry loop terminated unexpectedly")

    def _delay(self, attempt: int) -> float:
        base = min(
            self.retry_policy.max_backoff,
            self.retry_policy.initial_backoff * (2 ** (attempt - 1)),
        )
        spread = self.retry_policy.jitter_ratio * ((2 * self._random()) - 1)
        return float(max(0.0, base * (1 + spread)))

    @staticmethod
    def _retry_after(response: HttpResponse) -> float | None:
        value = response.header("retry-after")
        if value is None:
            return None
        try:
            delay = float(value)
        except ValueError:
            return None
        return max(0.0, delay)
