"""End-to-end tests for the real IncidentOrchestrator dashboard backend."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi")

from ledgerlens.actions import (
    ActionAuthorizer,
    ActionExecutionStatus,
    ActionPreview,
)
from ledgerlens.actions import (
    ActionReceipt as ProviderReceipt,
)
from ledgerlens.incident_dashboard import CLAIM_BOUNDARY, create_incident_app
from ledgerlens.incident_integration import (
    ActionRegistryExecutor,
    OrchestratorIncidentBackend,
    UnsupportedPlannedAction,
)
from ledgerlens.incident_models import (
    ActionPlan,
    ActionRisk,
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentTrigger,
    PlannedAction,
)
from ledgerlens.orchestrator import ExecutionOutcome, WritebackOutcome
from ledgerlens.verification import (
    ActionAllowance,
    PolicyConfig,
    PolicyGate,
    VerifierAssessment,
    VerifierPanel,
)

TestClient = importlib.import_module("fastapi.testclient").TestClient
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _incident() -> Incident:
    return Incident(
        incident_id="INC-LIVE-1",
        title="Orders freshness threshold exceeded",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        affected_entities=(
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)",
            "urn:li:dashboard:(looker,orders-health)",
        ),
        trigger=IncidentTrigger(
            trigger_id="trigger-live-1",
            source="datahub-assertion",
            kind="freshness_slo",
            occurred_at=NOW,
            idempotency_key="trigger-live-1",
            payload={"signal": "Freshness is 23 minutes against a 15 minute SLO."},
        ),
    )


def _context(incident: Incident) -> IncidentContext:
    return IncidentContext(
        context_id="context-live-1",
        incident=incident,
        collected_at=NOW,
        facts=(
            IncidentFact(
                fact_id="root-asset",
                statement="The triggering asset is analytics.orders.",
                evidence=(
                    EvidencePointer(
                        reference=incident.affected_entities[0],
                        kind=EvidenceKind.DATAHUB_ENTITY,
                        observed_at=NOW,
                    ),
                ),
            ),
            IncidentFact(
                fact_id="primary-owner",
                statement="The recorded owner is data-platform.",
                evidence=(
                    EvidencePointer(
                        reference=f"{incident.affected_entities[0]}#ownership",
                        kind=EvidenceKind.DATAHUB_ENTITY,
                        observed_at=NOW,
                    ),
                ),
            ),
        ),
        metadata={
            "source": "test-datahub-mcp",
            "rootAsset": {
                "urn": incident.affected_entities[0],
                "name": "analytics.orders",
                "platform": "Snowflake",
                "domain": "Analytics",
                "tier": "Tier 1",
            },
            "owner": {"id": "data-platform", "displayName": "Data Platform"},
            "blastRadiusUrns": [incident.affected_entities[1]],
        },
    )


class Planner:
    planner_id = "020s:gpt-5.6-sol"
    family = "gpt-5.6-sol"

    def plan(self, context: IncidentContext) -> ActionPlan:
        return ActionPlan(
            plan_id="plan-live-1",
            incident_id=context.incident.incident_id,
            planner_id=self.planner_id,
            planner_family=self.family,
            created_at=NOW,
            confidence=0.97,
            summary="Open a bounded GitHub incident issue.",
            actions=(
                PlannedAction(
                    action_id="action-github",
                    action_type="github.issue.create",
                    target="tomyimkc/ledgerlens",
                    parameters={
                        "owner": "tomyimkc",
                        "repository": "ledgerlens",
                        "title": "INC-LIVE-1: orders freshness",
                        "body": "Evidence-bounded incident record.",
                        "labels": ["incident"],
                    },
                    rationale="Create an auditable work item for the recorded owner.",
                    evidence_fact_ids=("root-asset", "primary-owner"),
                    idempotency_key="INC-LIVE-1:github",
                    risk=ActionRisk.LOW,
                ),
            ),
        )


class Verifier:
    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierAssessment:
        assert context.fact_ids >= {"root-asset", "primary-owner"}
        assert plan.actions[0].action_type == "github.issue.create"
        return VerifierAssessment(
            approved=True,
            confidence=0.96,
            reasons=("The action is reversible, allowlisted, and grounded.",),
        )


def _policy() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            version="test/v1",
            allowances=(
                ActionAllowance(
                    action_type="github.issue.create",
                    targets=frozenset({"tomyimkc/ledgerlens"}),
                    allowed_parameter_keys=frozenset(
                        {"owner", "repository", "title", "body", "labels"}
                    ),
                    required_parameter_keys=frozenset({"owner", "repository", "title"}),
                    maximum_risk=ActionRisk.LOW,
                ),
            ),
            minimum_plan_confidence=0.9,
            minimum_verifier_confidence=0.9,
            required_quorum=2,
            minimum_verifier_families=2,
        ),
        clock=lambda: NOW,
    )


def test_autonomous_dashboard_executes_the_frozen_orchestrator_plan_once() -> None:
    calls = {"execute": 0, "writeback": 0}

    def execute(context: IncidentContext, action: PlannedAction) -> ExecutionOutcome:
        calls["execute"] += 1
        assert context.context_id == "context-live-1"
        return ExecutionOutcome(
            succeeded=True,
            executor="github:create_issue",
            message="GitHub accepted the bounded action",
            output_references=("https://github.com/tomyimkc/ledgerlens/issues/999",),
            details={"providerReceipt": {"remote_id": "999"}},
        )

    def writeback(result: Any) -> WritebackOutcome:
        calls["writeback"] += 1
        assert result.receipts[0].action_id == "action-github"
        return WritebackOutcome(
            succeeded=True,
            message="DataHub incident command receipt recorded",
            reference="datahub://writeback/receipt-1",
        )

    backend = OrchestratorIncidentBackend(
        incident_resolver=lambda payload: _incident(),
        context_provider=_context,
        planner=Planner(),
        verifier_panel=VerifierPanel(
            (
                Verifier("020s:gpt-5.6-terra", "gpt-5.6-terra"),
                Verifier("020s:gpt-5.5", "gpt-5.5"),
            )
        ),
        policy_gate=_policy(),
        executor=execute,
        writeback=writeback,
        clock=lambda: NOW,
    )
    client = TestClient(create_incident_app(backend=backend, autonomous_execution=True))

    response = client.post("/incident/api/trigger", json={"incident_id": "INC-LIVE-1"})

    assert response.status_code == 200
    state = response.json()["state"]
    assert state["mode"] == "live"
    assert state["verifier"]["approved"] is True
    assert "provider-family independence is not claimed" in (state["verifier"]["authority_note"])
    assert state["authorization"]["decision"] == "authorized"
    assert state["actions"][0]["status"] == "succeeded"
    assert state["actions"][0]["receipt"].endswith("/999")
    assert state["writeback"]["status"] == "recorded"
    assert state["memory"]["status"] == "ready"
    # Assert against the production constant, not a copy of its literal: this is exactly
    # the drift that silently broke CI when CLAIM_BOUNDARY gained its "asserts" field.
    assert state["claim_boundary"] == CLAIM_BOUNDARY
    assert calls == {"execute": 1, "writeback": 1}

    replay = client.post("/incident/api/execute")
    assert replay.status_code == 200
    assert calls == {"execute": 1, "writeback": 1}

    retriggered = client.post(
        "/incident/api/trigger",
        json={"incident_id": "INC-LIVE-1"},
    )
    assert retriggered.status_code == 200
    assert calls == {"execute": 1, "writeback": 1}


class RecordingGitHubAdapter:
    name = "github"
    operation = "create_issue"

    def __init__(self, authorizer: ActionAuthorizer) -> None:
        self.authorizer = authorizer
        self.actions: list[Any] = []

    def preview(self, action: Any) -> ActionPreview:
        self.actions.append(action)
        return ActionPreview(
            adapter=self.name,
            operation=self.operation,
            target=f"github:{action.owner}/{action.repository}",
            summary="Create issue",
            payload={
                "owner": action.owner,
                "repository": action.repository,
                "title": action.title,
                "body": action.body,
            },
            action_digest="sha256:" + "a" * 64,
            idempotency_key="user-sha256:" + "b" * 64,
        )

    def execute(self, action: Any, authorization: Any) -> ProviderReceipt:
        preview = self.preview(action)
        self.authorizer.verify(authorization, preview)
        return ProviderReceipt(
            receipt_id="provider-receipt-1",
            adapter=self.name,
            operation=self.operation,
            target=preview.target,
            action_digest=preview.action_digest,
            idempotency_key=preview.idempotency_key,
            status=ActionExecutionStatus.EXECUTED,
            http_status=201,
            attempts=1,
            remote_id="42",
            remote_url="https://github.com/tomyimkc/ledgerlens/issues/42",
            completed_at=NOW,
        )


def test_action_registry_binds_typed_provider_action_to_hmac_authorization() -> None:
    authorizer = ActionAuthorizer(
        b"ledgerlens-integration-test-secret-32-bytes",
        clock=lambda: NOW,
        nonce_factory=lambda: "nonce",
    )
    adapter = RecordingGitHubAdapter(authorizer)
    executor = ActionRegistryExecutor(
        {"github.issue.create": adapter},
        authorizer=authorizer,
    )
    action = Planner().plan(_context(_incident())).actions[0]

    outcome = executor(_context(_incident()), action)

    assert outcome.succeeded is True
    assert outcome.output_references[0].endswith("/42")
    assert outcome.details["providerReceipt"]["remote_id"] == "42"
    assert adapter.actions[0].owner == "tomyimkc"

    wrong_target = action.model_copy(update={"target": "someone/else"})
    with pytest.raises(UnsupportedPlannedAction, match="target"):
        executor(_context(_incident()), wrong_target)
