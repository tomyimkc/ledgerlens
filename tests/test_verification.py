"""Network-free tests for verifier quorum and deterministic authorization."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

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
from ledgerlens.verification import (
    ActionAllowance,
    PolicyConfig,
    PolicyGate,
    VerifierAssessment,
    VerifierPanel,
    VerifierPanelConfig,
)

NOW = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)


def _context() -> IncidentContext:
    trigger = IncidentTrigger(
        trigger_id="trigger-1",
        source="datahub",
        kind="quality_assertion",
        occurred_at=NOW,
        idempotency_key="trigger-1-key",
    )
    incident = Incident(
        incident_id="incident-1",
        title="Orders quality assertion failed",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        trigger=trigger,
    )
    return IncidentContext(
        context_id="context-1",
        incident=incident,
        collected_at=NOW,
        facts=(
            IncidentFact(
                fact_id="fact-1",
                statement="The DataHub assertion is in a failed state.",
                evidence=(
                    EvidencePointer(
                        reference="urn:li:assertion:orders-quality",
                        kind=EvidenceKind.DATAHUB_ENTITY,
                        observed_at=NOW,
                    ),
                ),
            ),
        ),
    )


def _plan(
    *,
    action_type: str = "notify_owner",
    fact_ids: tuple[str, ...] = ("fact-1",),
    parameters: dict[str, Any] | None = None,
    planner_family: str = "planner-family",
) -> ActionPlan:
    return ActionPlan(
        plan_id="plan-1",
        incident_id="incident-1",
        planner_id="planner-1",
        planner_family=planner_family,
        created_at=NOW,
        confidence=0.94,
        summary="Notify the owner using only the grounded assertion state.",
        actions=(
            PlannedAction(
                action_id="action-1",
                action_type=action_type,
                target="urn:li:corpgroup:data-platform",
                parameters=parameters or {"channel": "incident-room"},
                rationale="The owner is allowlisted for this bounded notification.",
                evidence_fact_ids=fact_ids,
                idempotency_key="incident-1:action-1",
                risk=ActionRisk.LOW,
            ),
        ),
    )


class FakeVerifier:
    def __init__(
        self,
        verifier_id: str,
        family: str,
        *,
        approved: bool = True,
        confidence: float = 0.95,
        unverifiable_fact_ids: tuple[str, ...] = (),
        fail: bool = False,
    ) -> None:
        self.verifier_id = verifier_id
        self.family = family
        self.approved = approved
        self.confidence = confidence
        self.unverifiable_fact_ids = unverifiable_fact_ids
        self.fail = fail
        self.calls = 0

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierAssessment:
        self.calls += 1
        assert context.incident.incident_id == plan.incident_id
        if self.fail:
            raise RuntimeError("fixture verifier unavailable")
        return VerifierAssessment(
            approved=self.approved,
            confidence=self.confidence,
            reasons=("grounding and action scope checked",),
            unverifiable_fact_ids=self.unverifiable_fact_ids,
        )


def _panel(*verifiers: FakeVerifier, quorum: int = 2) -> VerifierPanel:
    return VerifierPanel(
        verifiers,
        config=VerifierPanelConfig(
            quorum=quorum,
            minimum_families=2,
            confidence_threshold=0.8,
        ),
    )


def _gate() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            allowances=(
                ActionAllowance(
                    action_type="notify_owner",
                    targets=frozenset({"urn:li:corpgroup:data-platform"}),
                    allowed_parameter_keys=frozenset({"channel"}),
                    required_parameter_keys=frozenset({"channel"}),
                    maximum_risk=ActionRisk.LOW,
                ),
            ),
            minimum_plan_confidence=0.8,
            minimum_verifier_confidence=0.8,
            required_quorum=2,
            minimum_verifier_families=2,
        ),
        clock=lambda: NOW,
    )


def test_panel_requires_two_distinct_verifier_families() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        _panel(FakeVerifier("v1", "family-a"))

    with pytest.raises(ValueError, match="unique"):
        _panel(
            FakeVerifier("v1", "family-a"),
            FakeVerifier("v2", "family-a"),
        )


def test_panel_enforces_quorum_and_confidence_by_unique_family() -> None:
    result = _panel(
        FakeVerifier("v1", "family-a", confidence=0.97),
        FakeVerifier("v2", "family-b", confidence=0.79),
        FakeVerifier("v3", "family-c", confidence=0.91),
    ).verify(_context(), _plan())

    assert result.approved is True
    assert result.approvals == 2
    assert result.aggregate_confidence == 0.91
    assert "quorum_approved" in result.reason_codes


def test_panel_fails_closed_on_errors_unverifiable_items_and_family_overlap() -> None:
    failed = _panel(
        FakeVerifier("v1", "family-a"),
        FakeVerifier("v2", "family-b", fail=True),
        FakeVerifier("v3", "family-c"),
    ).verify(_context(), _plan())
    assert failed.approved is False
    assert "verifier_error" in failed.reason_codes

    unverifiable = _panel(
        FakeVerifier("v1", "family-a", unverifiable_fact_ids=("fact-unknown",)),
        FakeVerifier("v2", "family-b"),
    ).verify(_context(), _plan())
    assert unverifiable.approved is False
    assert "unverifiable_items" in unverifiable.reason_codes

    verifier_a = FakeVerifier("v1", "family-a")
    verifier_b = FakeVerifier("v2", "family-b")
    overlap = _panel(verifier_a, verifier_b).verify(
        _context(),
        _plan(planner_family="family-a"),
    )
    assert overlap.approved is False
    assert overlap.reason_codes == ("planner_verifier_family_overlap",)
    assert verifier_a.calls == verifier_b.calls == 0


def test_policy_authorizes_only_grounded_exact_allowlist_matches() -> None:
    context = _context()
    plan = _plan()
    verification = _panel(
        FakeVerifier("v1", "family-a"),
        FakeVerifier("v2", "family-b"),
    ).verify(context, plan)

    decision = _gate().authorize(context, plan, verification)

    assert decision.authorized is True
    assert decision.reason_codes == ("authorized",)
    assert decision.authorized_action_ids == ("action-1",)
    assert decision.candidate_only is True
    assert decision.can_claim_agi is False


@pytest.mark.parametrize(
    ("plan", "expected_reason"),
    [
        (_plan(action_type="drop_table"), "action_not_allowlisted:action-1"),
        (_plan(fact_ids=("fact-invented",)), "action_references_unknown_fact:action-1"),
        (
            _plan(parameters={"channel": "incident-room", "shell": "rm -rf /"}),
            "parameter_not_allowlisted:action-1",
        ),
    ],
)
def test_policy_rejects_unallowlisted_or_unverifiable_actions(
    plan: ActionPlan,
    expected_reason: str,
) -> None:
    context = _context()
    verification = _panel(
        FakeVerifier("v1", "family-a"),
        FakeVerifier("v2", "family-b"),
    ).verify(context, plan)

    decision = _gate().authorize(context, plan, verification)

    assert decision.authorized is False
    assert expected_reason in decision.reason_codes
    assert decision.authorized_action_ids == ()
