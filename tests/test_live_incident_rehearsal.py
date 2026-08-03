"""Offline tests for the live incident rehearsal script.

These prove the real four-provider fanout is wired correctly — using fake transports, so
no network call and no real credential is ever needed — and that the script fails closed
when credentials are absent. The live run itself still requires the owner's credentials and
``--confirm-live``; this suite verifies everything up to the network boundary.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ledgerlens.actions import ActionAuthorizer, HttpResponse  # noqa: E402
from ledgerlens.actions.transport import HttpRequest  # noqa: E402
from ledgerlens.incident_models import (  # noqa: E402
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentStatus,
    IncidentTrigger,
    PlannedAction,
)

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
SIGNING_SECRET = b"ledgerlens-test-signing-secret-32-bytes!"


def _load_script() -> Any:
    path = ROOT / "scripts" / "run_live_incident_rehearsal.py"
    spec = importlib.util.spec_from_file_location("run_live_incident_rehearsal", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass annotation resolution can find the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


class FakeTransport:
    """Scripted transport that cannot make live calls."""

    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
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


def _credentials() -> Any:
    return SCRIPT.ProviderCredentials(
        github_token="gh-token",
        slack_webhook_url="https://hooks.slack.test/services/T/B/SECRET",
        pagerduty_routing_key="pd-routing-key",
        jira_site_url="https://ledgerlens.atlassian.test",
        jira_email="rehearsal@example.test",
        jira_api_token="jira-token",
    )


def _fake_transports() -> dict[str, FakeTransport]:
    return {
        "github.issue.create": FakeTransport(
            [
                HttpResponse(
                    201,
                    json_body={
                        "id": 9001,
                        "number": 42,
                        "state": "open",
                        "html_url": "https://github.test/tomyimkc/ledgerlens/issues/42",
                    },
                )
            ]
        ),
        "slack.message.post": FakeTransport([HttpResponse(200, text="ok")]),
        "pagerduty.event.trigger": FakeTransport(
            [HttpResponse(202, json_body={"status": "success", "dedup_key": "remote-dedup"})]
        ),
        "jira.issue.create": FakeTransport(
            [
                HttpResponse(
                    201,
                    json_body={
                        "id": "10001",
                        "key": "DATAOPS-17",
                        "self": "https://jira.test/rest/api/3/issue/10001",
                    },
                )
            ]
        ),
    }


def _context() -> IncidentContext:
    incident = Incident(
        incident_id="inc-rehearsal-01",
        title="Rehearsal incident",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIGGERED,
        detected_at=NOW,
        trigger=IncidentTrigger(
            trigger_id="t1",
            source="datahub",
            kind="freshness_assertion",
            occurred_at=NOW,
            idempotency_key="t1",
        ),
        affected_entities=("urn:li:dataset:root",),
    )
    return IncidentContext(
        context_id="ctx-1",
        incident=incident,
        collected_at=NOW,
        facts=(
            IncidentFact(
                fact_id="root-asset",
                statement="root",
                evidence=(
                    EvidencePointer(
                        reference="urn:li:dataset:root", kind=EvidenceKind.DATAHUB_ENTITY
                    ),
                ),
            ),
        ),
    )


def _actions() -> list[PlannedAction]:
    return [
        PlannedAction(
            action_id="a-github",
            action_type="github.issue.create",
            target="tomyimkc/ledgerlens",
            parameters={
                "owner": "tomyimkc",
                "repository": "ledgerlens",
                "title": "inc-rehearsal-01: record",
                "body": "bounded rehearsal record",
            },
            rationale="record the incident",
            evidence_fact_ids=("root-asset",),
            idempotency_key="inc-rehearsal-01:a-github",
        ),
        PlannedAction(
            action_id="a-slack",
            action_type="slack.message.post",
            target="#inc-data-platform",
            parameters={"channel": "#inc-data-platform", "text": "rehearsal status"},
            rationale="notify channel",
            evidence_fact_ids=("root-asset",),
            idempotency_key="inc-rehearsal-01:a-slack",
        ),
        PlannedAction(
            action_id="a-pagerduty",
            action_type="pagerduty.event.trigger",
            target="pagerduty:events-v2",
            parameters={
                "summary": "inc-rehearsal-01: page",
                "source": "ledgerlens",
                "severity": "critical",
            },
            rationale="page on-call",
            evidence_fact_ids=("root-asset",),
            idempotency_key="inc-rehearsal-01:a-pagerduty",
        ),
        PlannedAction(
            action_id="a-jira",
            action_type="jira.issue.create",
            target="DATAOPS",
            parameters={"project_key": "DATAOPS", "summary": "inc-rehearsal-01: verify recovery"},
            rationale="track recovery",
            evidence_fact_ids=("root-asset",),
            idempotency_key="inc-rehearsal-01:a-jira",
        ),
    ]


from ledgerlens.incident_integration import OrchestratorIncidentBackend  # noqa: E402
from ledgerlens.incident_models import ActionPlan  # noqa: E402
from ledgerlens.runtime_factory import build_policy_gate  # noqa: E402
from ledgerlens.verification import VerifierAssessment, VerifierPanel  # noqa: E402


class _DeterministicPlanner:
    planner_id = "deterministic:live-rehearsal"
    family = "live-rehearsal-planner"

    def plan(self, context: IncidentContext) -> ActionPlan:
        return ActionPlan(
            plan_id=f"{context.incident.incident_id}:plan",
            incident_id=context.incident.incident_id,
            planner_id=self.planner_id,
            planner_family=self.family,
            created_at=NOW,
            confidence=0.9,
            summary="four bounded collaboration actions",
            actions=tuple(_actions()),
        )


class _ApprovingVerifier:
    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    def verify(self, context: IncidentContext, plan: ActionPlan) -> VerifierAssessment:
        del context, plan
        return VerifierAssessment(approved=True, confidence=0.95, reasons=("ok",))


def test_backend_trigger_execute_runs_full_fanout_offline() -> None:
    """The full real backend path (trigger -> authorize -> execute) fans out to all four
    providers offline. This guards the plan_hash the execute() grant must carry: passing the
    wrong value fails closed and never touches a provider."""
    context = _context()
    authorizer = ActionAuthorizer(SIGNING_SECRET, clock=lambda: NOW, nonce_factory=lambda: "n1")
    transports = _fake_transports()
    executor = SCRIPT.build_action_executor(
        _credentials(), authorizer, transports=transports, timeout=5.0
    )
    backend = OrchestratorIncidentBackend(
        incident_resolver=lambda payload: context.incident,
        context_provider=lambda incident: context,
        planner=_DeterministicPlanner(),
        verifier_panel=VerifierPanel(
            (
                _ApprovingVerifier("v1", "grounding-lint"),
                _ApprovingVerifier("v2", "policy-shape"),
            )
        ),
        policy_gate=build_policy_gate(
            SCRIPT.POLICY_TARGETS,
            minimum_plan_confidence=0.8,
            minimum_verifier_confidence=0.85,
            quorum=2,
        ),
        executor=executor,
        writeback=lambda run: None,
        clock=lambda: NOW,
    )

    prepared, result, state, executed = SCRIPT.run_backend(backend, context.incident.incident_id)

    assert prepared.authorization.authorized is True
    assert executed is True
    assert result is not None
    # Every provider was actually called exactly once — the fanout really executed.
    for transport in transports.values():
        assert len(transport.requests) == 1


class _DisapprovingVerifier:
    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    def verify(self, context: IncidentContext, plan: ActionPlan) -> VerifierAssessment:
        del context, plan
        return VerifierAssessment(
            approved=False, confidence=0.99, reasons=("withholding approval for this test",)
        )


def test_backend_denied_plan_executes_no_provider_action() -> None:
    """A plan the panel does not approve must reach ZERO providers — fail-closed end to end.

    This is the authority-boundary guarantee: no provider is contacted unless the deterministic
    gate authorizes the exact reviewed plan.
    """
    context = _context()
    authorizer = ActionAuthorizer(SIGNING_SECRET, clock=lambda: NOW, nonce_factory=lambda: "n1")
    transports = _fake_transports()
    executor = SCRIPT.build_action_executor(
        _credentials(), authorizer, transports=transports, timeout=5.0
    )
    backend = OrchestratorIncidentBackend(
        incident_resolver=lambda payload: context.incident,
        context_provider=lambda incident: context,
        planner=_DeterministicPlanner(),
        verifier_panel=VerifierPanel(
            (
                _DisapprovingVerifier("v1", "grounding-lint"),
                _ApprovingVerifier("v2", "policy-shape"),
            )
        ),
        policy_gate=build_policy_gate(
            SCRIPT.POLICY_TARGETS,
            minimum_plan_confidence=0.8,
            minimum_verifier_confidence=0.85,
            quorum=2,
        ),
        executor=executor,
        writeback=lambda run: None,
        clock=lambda: NOW,
    )

    prepared, result, state, executed = SCRIPT.run_backend(backend, context.incident.incident_id)

    assert prepared.authorization.authorized is False
    assert executed is False
    assert result is None
    # Not a single provider was contacted.
    for transport in transports.values():
        assert transport.requests == []


def test_real_executor_fans_out_to_all_four_providers_offline() -> None:
    authorizer = ActionAuthorizer(SIGNING_SECRET, clock=lambda: NOW, nonce_factory=lambda: "n1")
    transports = _fake_transports()
    executor = SCRIPT.build_action_executor(
        _credentials(), authorizer, transports=transports, timeout=5.0
    )
    context = _context()

    outcomes = {action.action_type: executor(context, action) for action in _actions()}

    assert set(outcomes) == set(SCRIPT.POLICY_TARGETS)
    for outcome in outcomes.values():
        assert outcome.succeeded is True
        assert "providerReceipt" in outcome.details
    # Each adapter made exactly one real (faked) provider call.
    for transport in transports.values():
        assert len(transport.requests) == 1
    # The GitHub receipt carries the real issue URL from the faked response.
    assert any("issues/42" in ref for ref in outcomes["github.issue.create"].output_references)


def test_provider_receipts_never_leak_credentials() -> None:
    authorizer = ActionAuthorizer(SIGNING_SECRET, clock=lambda: NOW, nonce_factory=lambda: "n1")
    creds = _credentials()
    executor = SCRIPT.build_action_executor(
        creds, authorizer, transports=_fake_transports(), timeout=5.0
    )
    context = _context()
    for action in _actions():
        outcome = executor(context, action)
        serialized = str(outcome.details)
        assert creds.github_token not in serialized
        assert creds.slack_webhook_url not in serialized
        assert creds.pagerduty_routing_key not in serialized
        assert creds.jira_api_token not in serialized


def test_credentials_from_env_fails_closed_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in (
        "GITHUB_TOKEN",
        "LEDGERLENS_SLACK_WEBHOOK_URL",
        "LEDGERLENS_PAGERDUTY_ROUTING_KEY",
        "LEDGERLENS_JIRA_SITE_URL",
        "LEDGERLENS_JIRA_EMAIL",
        "LEDGERLENS_JIRA_API_TOKEN",
    ):
        monkeypatch.delenv(env_name, raising=False)
    credentials, missing = SCRIPT.ProviderCredentials.from_env()
    assert credentials is None
    assert "GITHUB_TOKEN" in missing
    assert "LEDGERLENS_JIRA_API_TOKEN" in missing


def test_main_requires_confirm_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["run_live_incident_rehearsal.py"])
    assert SCRIPT.main() == 2


def test_assemble_receipt_marks_external_mutations_and_keeps_claim_ceiling() -> None:
    authorizer = ActionAuthorizer(SIGNING_SECRET, clock=lambda: NOW, nonce_factory=lambda: "n1")
    executor = SCRIPT.build_action_executor(
        _credentials(), authorizer, transports=_fake_transports(), timeout=5.0
    )
    context = _context()

    class _Prepared:
        pass

    prepared = _Prepared()
    prepared.context = context
    prepared.incident = context.incident
    prepared.plan = _FakePlan()
    prepared.verification = _FakeDumpable()
    prepared.authorization = _FakeAuth()

    receipt = SCRIPT.assemble_receipt(
        prepared=prepared,
        result=None,
        state={"mode": "live"},
        settings=_FakeSettings(),
        executed=True,
    )
    assert receipt["externalMutations"] is True
    assert receipt["status"] == "executed"
    assert receipt["candidateOnly"] is True
    assert receipt["canClaimAGI"] is False
    joined = " ".join(receipt["limitations"]).lower()
    assert "provider-family independence is not claimed" in joined
    assert "no incident causality" in joined
    # Executor is constructed but not called in this assembly test.
    assert executor is not None


class _FakeDumpable:
    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {}


class _FakePlan(_FakeDumpable):
    summary = "bounded plan"


class _FakeAuth(_FakeDumpable):
    authorized = True
    plan_id = "plan-1"


class _FakeSettings:
    planner_model = "gpt-5.6-sol"
    verifier_model_ids = ("gpt-5.6-terra", "gpt-5.5")
    llm_base_url = "https://api.020s.test/v1"
