"""Unit tests for RetryingHttpExecutor: bounded retries, ambiguity handling, secret opacity."""

from __future__ import annotations

import pytest

from ledgerlens.actions.errors import ActionOutcomeUnknownError, ActionTransportError
from ledgerlens.actions.transport import (
    HttpRequest,
    HttpResponse,
    RetryingHttpExecutor,
    RetryPolicy,
    TransportConnectionFailure,
    TransportFailure,
    TransportTimeoutFailure,
)


class ScriptedTransport:
    """Yields a fixed sequence of ``HttpResponse`` values or raises a queued exception."""

    def __init__(self, *steps: HttpResponse | BaseException) -> None:
        self._steps = list(steps)
        self.calls = 0

    def request(self, request: HttpRequest) -> HttpResponse:
        del request
        self.calls += 1
        step = self._steps[self.calls - 1]
        if isinstance(step, BaseException):
            raise step
        return step


def _request() -> HttpRequest:
    return HttpRequest(
        adapter="github",
        method="POST",
        url="https://api.example.test/secret-path",
        headers={"authorization": "Bearer s3cret-token"},
        json_body={"title": "incident"},
    )


def _executor(
    transport: ScriptedTransport, *, max_attempts: int = 3
) -> tuple[RetryingHttpExecutor, list[float]]:
    sleeps: list[float] = []
    executor = RetryingHttpExecutor(
        transport,
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            initial_backoff=0.01,
            max_backoff=0.04,
            jitter_ratio=0.0,
        ),
        sleep=sleeps.append,
        random_source=lambda: 0.5,
    )
    return executor, sleeps


def test_success_on_first_attempt_does_not_retry() -> None:
    executor, sleeps = _executor(ScriptedTransport(HttpResponse(status_code=200)))

    result = executor.execute(_request(), retry_ambiguous_failures=False)

    assert result.attempts == 1
    assert result.response.status_code == 200
    assert sleeps == []


def test_retryable_status_is_retried_then_succeeds() -> None:
    executor, sleeps = _executor(
        ScriptedTransport(HttpResponse(status_code=503), HttpResponse(status_code=201))
    )

    result = executor.execute(_request(), retry_ambiguous_failures=False)

    assert result.attempts == 2
    assert result.response.status_code == 201
    assert len(sleeps) == 1


def test_persistent_retryable_status_returns_last_response_at_max_attempts() -> None:
    executor, sleeps = _executor(
        ScriptedTransport(
            HttpResponse(status_code=503),
            HttpResponse(status_code=503),
            HttpResponse(status_code=503),
        )
    )

    result = executor.execute(_request(), retry_ambiguous_failures=False)

    # The last attempt is not retried; the caller receives the final retryable response.
    assert result.attempts == 3
    assert result.response.status_code == 503
    assert len(sleeps) == 2


def test_retry_after_header_overrides_backoff() -> None:
    executor, sleeps = _executor(
        ScriptedTransport(
            HttpResponse(status_code=429, headers={"Retry-After": "1.5"}),
            HttpResponse(status_code=200),
        )
    )

    executor.execute(_request(), retry_ambiguous_failures=False)

    assert sleeps == [1.5]


def test_connection_failure_retries_then_raises_retryable_transport_error() -> None:
    executor, sleeps = _executor(
        ScriptedTransport(
            TransportConnectionFailure("down"),
            TransportConnectionFailure("down"),
            TransportConnectionFailure("down"),
        )
    )

    with pytest.raises(ActionTransportError) as excinfo:
        executor.execute(_request(), retry_ambiguous_failures=False)

    assert excinfo.value.retryable is True
    assert excinfo.value.outcome_unknown is False
    assert excinfo.value.attempts == 3
    assert excinfo.value.adapter == "github"
    assert len(sleeps) == 2


def test_connection_failure_then_success_recovers() -> None:
    executor, _ = _executor(
        ScriptedTransport(TransportConnectionFailure("down"), HttpResponse(status_code=200))
    )

    result = executor.execute(_request(), retry_ambiguous_failures=False)

    assert result.attempts == 2
    assert result.response.status_code == 200


def test_ambiguous_failure_is_not_retried_when_flag_false() -> None:
    executor, sleeps = _executor(ScriptedTransport(TransportTimeoutFailure("maybe sent")))

    with pytest.raises(ActionOutcomeUnknownError) as excinfo:
        executor.execute(_request(), retry_ambiguous_failures=False)

    # A timeout may have reached the provider; retrying could duplicate the action.
    assert excinfo.value.outcome_unknown is True
    assert excinfo.value.retryable is False
    assert excinfo.value.attempts == 1
    assert sleeps == []


def test_ambiguous_failure_is_retried_when_flag_true_then_raises_after_max() -> None:
    executor, sleeps = _executor(
        ScriptedTransport(
            TransportFailure("x"),
            TransportFailure("x"),
            TransportFailure("x"),
        )
    )

    with pytest.raises(ActionTransportError) as excinfo:
        executor.execute(_request(), retry_ambiguous_failures=True)

    assert excinfo.value.retryable is True
    assert excinfo.value.attempts == 3
    assert len(sleeps) == 2


def test_ambiguous_failure_is_retried_when_flag_true_then_succeeds() -> None:
    executor, _ = _executor(
        ScriptedTransport(TransportTimeoutFailure("x"), HttpResponse(status_code=204))
    )

    result = executor.execute(_request(), retry_ambiguous_failures=True)

    assert result.attempts == 2
    assert result.response.status_code == 204


def test_request_repr_never_exposes_url_headers_or_body() -> None:
    text = repr(_request())

    assert "s3cret-token" not in text
    assert "secret-path" not in text
    assert "Bearer" not in text
    assert "incident" not in text
    # The adapter and method are safe, non-sensitive identifiers and may appear.
    assert "github" in text
    assert "POST" in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_backoff": -1.0},
        {"max_backoff": -1.0},
        {"jitter_ratio": 1.5},
        {"jitter_ratio": -0.1},
    ],
)
def test_retry_policy_rejects_invalid_configuration(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)


def test_retry_after_parsing_edge_cases() -> None:
    parse = RetryingHttpExecutor._retry_after

    assert parse(HttpResponse(status_code=503)) is None
    assert parse(HttpResponse(status_code=503, headers={"retry-after": "not-a-number"})) is None
    assert parse(HttpResponse(status_code=503, headers={"retry-after": "-5"})) == 0.0
    assert parse(HttpResponse(status_code=503, headers={"Retry-After": "2"})) == 2.0
