"""Deterministic, no-network tests for safety-gated action adapters."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

import pytest

from ledgerlens.actions import (
    ActionAuthorizationError,
    ActionAuthorizer,
    ActionExecutionStatus,
    ActionFanoutExecutor,
    ActionIndeterminateError,
    ActionInvocation,
    ActionOutcomeUnknownError,
    GitHubIssueAction,
    GitHubIssueAdapter,
    HttpRequest,
    HttpResponse,
    JiraIssueAction,
    JiraIssueAdapter,
    PagerDutyEventAction,
    PagerDutyEventsAdapter,
    PagerDutySeverity,
    RetryPolicy,
    SlackAdapter,
    SlackMessageAction,
    SQLiteIdempotencyStore,
    TransportTimeoutFailure,
)

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
SIGNING_SECRET = b"ledgerlens-test-signing-secret-32-bytes!"


class FakeTransport:
    """Scripted transport that cannot make live calls."""

    def __init__(self, outcomes: Iterable[HttpResponse | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[HttpRequest] = []
        self._lock = Lock()

    def request(self, request: HttpRequest) -> HttpResponse:
        with self._lock:
            self.requests.append(request)
            if not self._outcomes:
                raise AssertionError("unexpected transport request")
            outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def authorizer() -> ActionAuthorizer:
    return ActionAuthorizer(
        SIGNING_SECRET,
        clock=lambda: NOW,
        nonce_factory=lambda: "auth-test-001",
    )


def _authorize(adapter: object, action: object, authorizer: ActionAuthorizer):
    preview = adapter.preview(action)  # type: ignore[attr-defined]
    return authorizer.issue(preview, subject="incident-commander")


def test_github_requires_typed_bound_authorization_and_deduplicates(
    authorizer: ActionAuthorizer,
) -> None:
    token = "github-secret-token"
    transport = FakeTransport(
        [
            HttpResponse(
                201,
                json_body={
                    "id": 9001,
                    "number": 42,
                    "state": "open",
                    "html_url": (
                        "https://bot:secret@github.test/acme/ops/issues/42"
                        "?access_token=must-not-leak#fragment"
                    ),
                },
            )
        ]
    )
    adapter = GitHubIssueAdapter(
        token,
        authorizer=authorizer,
        api_url="https://github.test/api/v3",
        transport=transport,
        clock=lambda: NOW,
    )
    action = GitHubIssueAction(
        owner="acme",
        repository="ops",
        title="Investigate F-042",
        body="Evidence-backed incident summary",
        labels=("incident", "incident"),
        idempotency_key="run-42",
    )
    preview = adapter.preview(action)
    assert preview.requires_authorization
    assert preview.idempotency_key.startswith("user-sha256:")
    assert "run-42" not in preview.model_dump_json()
    assert token not in preview.model_dump_json()

    with pytest.raises(ActionAuthorizationError, match="typed ActionAuthorization"):
        adapter.execute(action, "approve this")  # type: ignore[arg-type]

    authorization = authorizer.issue(preview, subject="on-call")
    receipt = adapter.execute(action, authorization)
    duplicate = adapter.execute(action, authorization)

    assert receipt.status is ActionExecutionStatus.EXECUTED
    assert receipt.remote_id == "42"
    assert receipt.remote_url == "https://github.test/acme/ops/issues/42"
    assert receipt.details == {"repository": "acme/ops", "number": 42, "state": "open"}
    assert duplicate.status is ActionExecutionStatus.DEDUPLICATED
    assert duplicate.attempts == 0
    assert duplicate.deduplicated_from == receipt.receipt_id
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.url.endswith("/repos/acme/ops/issues")
    assert request.headers["Authorization"] == f"Bearer {token}"
    assert token not in repr(request)
    assert token not in repr(adapter)
    assert token not in receipt.model_dump_json()
    assert authorization.signature not in repr(authorization)


def test_authorization_is_action_bound_signed_and_expiring(
    authorizer: ActionAuthorizer,
) -> None:
    transport = FakeTransport([])
    adapter = GitHubIssueAdapter(
        "token",
        authorizer=authorizer,
        transport=transport,
        clock=lambda: NOW,
    )
    action = GitHubIssueAction(owner="acme", repository="ops", title="First")
    other = GitHubIssueAction(owner="acme", repository="ops", title="Second")
    authorization = authorizer.issue(adapter.preview(action), subject="operator")

    with pytest.raises(ActionAuthorizationError, match="does not match"):
        adapter.execute(other, authorization)

    tampered = replace(authorization, signature="not-a-valid-signature")
    with pytest.raises(ActionAuthorizationError, match="signature"):
        adapter.execute(action, tampered)

    expired = authorizer.issue(
        adapter.preview(action),
        subject="operator",
        ttl=timedelta(seconds=1),
        now=NOW - timedelta(minutes=1),
    )
    with pytest.raises(ActionAuthorizationError, match="expired"):
        adapter.execute(action, expired)
    assert not transport.requests


def test_slack_webhook_and_api_payloads_never_leak_credentials(
    authorizer: ActionAuthorizer,
) -> None:
    webhook_secret = "https://hooks.slack.test/services/T000/B000/SECRET"
    webhook_transport = FakeTransport([HttpResponse(200, text="ok")])
    webhook = SlackAdapter(
        authorizer=authorizer,
        webhook_url=webhook_secret,
        transport=webhook_transport,
        clock=lambda: NOW,
    )
    webhook_action = SlackMessageAction(text="Incident F-007 needs review")
    webhook_receipt = webhook.execute(
        webhook_action,
        _authorize(webhook, webhook_action, authorizer),
    )
    assert webhook_receipt.details == {"mode": "webhook", "delivery": "accepted"}
    assert webhook_secret not in webhook_receipt.model_dump_json()
    assert webhook_secret not in repr(webhook_transport.requests[0])

    bot_token = "xoxb-super-secret"
    api_transport = FakeTransport(
        [HttpResponse(200, json_body={"ok": True, "channel": "C123", "ts": "1.234"})]
    )
    api = SlackAdapter(
        authorizer=authorizer,
        bot_token=bot_token,
        transport=api_transport,
        clock=lambda: NOW,
    )
    api_action = SlackMessageAction(
        text="Incident F-008",
        channel="C123",
        idempotency_key="slack-F-008",
    )
    api_receipt = api.execute(api_action, _authorize(api, api_action, authorizer))
    request = api_transport.requests[0]
    assert request.headers["Authorization"] == f"Bearer {bot_token}"
    assert request.json_body is not None
    assert request.json_body["client_msg_id"]
    assert api_receipt.remote_id == "1.234"
    assert bot_token not in api_receipt.model_dump_json()


def test_pagerduty_retries_with_stable_provider_dedup_key(
    authorizer: ActionAuthorizer,
) -> None:
    routing_key = "pagerduty-routing-secret"
    transport = FakeTransport(
        [
            HttpResponse(503, headers={"Retry-After": "0"}),
            HttpResponse(202, json_body={"status": "success", "dedup_key": "remote-dedup"}),
        ]
    )
    sleeps: list[float] = []
    adapter = PagerDutyEventsAdapter(
        routing_key,
        authorizer=authorizer,
        transport=transport,
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_backoff=0,
            max_backoff=0,
            jitter_ratio=0,
        ),
        sleep=sleeps.append,
        random_source=lambda: 0.5,
        clock=lambda: NOW,
    )
    action = PagerDutyEventAction(
        summary="Database unavailable",
        source="ledgerlens",
        severity=PagerDutySeverity.CRITICAL,
        custom_details={"finding_id": "F-009"},
    )
    preview = adapter.preview(action)
    assert routing_key not in preview.model_dump_json()
    receipt = adapter.execute(action, authorizer.issue(preview, subject="on-call"))

    assert receipt.attempts == 2
    assert receipt.remote_id == "remote-dedup"
    assert sleeps == [0.0]
    assert len(transport.requests) == 2
    bodies = [request.json_body for request in transport.requests]
    assert bodies[0] == bodies[1]
    assert bodies[0] is not None
    assert bodies[0]["routing_key"] == routing_key
    assert bodies[0]["dedup_key"] == preview.idempotency_key
    assert routing_key not in receipt.model_dump_json()


def test_non_idempotent_timeout_is_quarantined_instead_of_retried(
    authorizer: ActionAuthorizer,
) -> None:
    transport = FakeTransport([TransportTimeoutFailure("read timed out")])
    adapter = GitHubIssueAdapter(
        "token",
        authorizer=authorizer,
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=3),
        clock=lambda: NOW,
    )
    action = GitHubIssueAction(owner="acme", repository="ops", title="Ambiguous")
    authorization = _authorize(adapter, action, authorizer)

    with pytest.raises(ActionOutcomeUnknownError):
        adapter.execute(action, authorization)
    assert len(transport.requests) == 1

    with pytest.raises(ActionIndeterminateError, match="reconcile"):
        adapter.execute(action, authorization)
    assert len(transport.requests) == 1


def test_jira_builds_adf_and_sqlite_store_persists_deduplication(
    authorizer: ActionAuthorizer,
    tmp_path: Path,
) -> None:
    token = "jira-api-secret"
    first_transport = FakeTransport(
        [
            HttpResponse(
                201,
                json_body={
                    "id": "10001",
                    "key": "OPS-17",
                    "self": "https://jira.test/rest/api/3/issue/10001",
                },
            )
        ]
    )
    action = JiraIssueAction(
        project_key="OPS",
        summary="Review F-017",
        description="First line\nSecond line",
        labels=("ledgerlens",),
    )
    database = tmp_path / "actions.sqlite3"
    with SQLiteIdempotencyStore(database) as store:
        adapter = JiraIssueAdapter(
            "https://jira.test",
            authorizer=authorizer,
            email="bot@example.test",
            api_token=token,
            transport=first_transport,
            idempotency_store=store,
            clock=lambda: NOW,
        )
        receipt = adapter.execute(action, _authorize(adapter, action, authorizer))
        assert receipt.remote_id == "OPS-17"
        request = first_transport.requests[0]
        assert request.json_body is not None
        fields = request.json_body["fields"]
        assert isinstance(fields, dict)
        assert fields["description"]["type"] == "doc"  # type: ignore[index]
        assert token not in repr(request)
        assert token not in receipt.model_dump_json()

    second_transport = FakeTransport([])
    with SQLiteIdempotencyStore(database) as store:
        adapter = JiraIssueAdapter(
            "https://jira.test",
            authorizer=authorizer,
            bearer_token="different-secret",
            transport=second_transport,
            idempotency_store=store,
            clock=lambda: NOW,
        )
        duplicate = adapter.execute(action, _authorize(adapter, action, authorizer))
        assert duplicate.status is ActionExecutionStatus.DEDUPLICATED
        assert not second_transport.requests


def test_fanout_preserves_order_and_sanitizes_failures(
    authorizer: ActionAuthorizer,
) -> None:
    github_transport = FakeTransport(
        [HttpResponse(201, json_body={"number": 1, "html_url": "https://github.test/1"})]
    )
    slack_transport = FakeTransport(
        [HttpResponse(200, json_body={"ok": False, "error": "invalid_auth"})]
    )
    github = GitHubIssueAdapter(
        "gh-secret",
        authorizer=authorizer,
        transport=github_transport,
        clock=lambda: NOW,
    )
    slack = SlackAdapter(
        authorizer=authorizer,
        bot_token="slack-secret",
        transport=slack_transport,
        clock=lambda: NOW,
    )
    github_action = GitHubIssueAction(owner="acme", repository="ops", title="Fanout")
    slack_action = SlackMessageAction(text="Fanout", channel="C123")
    invocations = [
        ActionInvocation(
            github,
            github_action,
            _authorize(github, github_action, authorizer),
        ),
        ActionInvocation(
            slack,
            slack_action,
            _authorize(slack, slack_action, authorizer),
        ),
    ]

    report = ActionFanoutExecutor(max_workers=2).execute(invocations)

    assert [item.adapter for item in report.items] == ["github", "slack"]
    assert report.items[0].receipt is not None
    assert report.items[1].failure is not None
    assert report.items[1].failure.error_type == "ActionProviderError"
    serialized = report.model_dump_json()
    assert "gh-secret" not in serialized
    assert "slack-secret" not in serialized
    assert "invalid_auth" in serialized
