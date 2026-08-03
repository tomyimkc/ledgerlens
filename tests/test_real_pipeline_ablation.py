"""Tests for the real-pipeline DataHub context ablation.

These assert the ablation exercises the *production* PolicyGate and VerifierPanel — not a
scripted responder — and that the honest ON/OFF separation holds: grounded plans are
authorized, ungrounded plans are refused with the gate's own reason codes.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.incident_commander.catalog import generate_catalog, load_catalog  # noqa: E402
from benchmarks.incident_commander.real_pipeline_ablation import (  # noqa: E402
    MODE_OFF,
    MODE_ON,
    DeterministicIncidentPlanner,
    GroundingLintVerifier,
    PolicyShapeVerifier,
    build_ablation_receipt,
)
from ledgerlens.verification import PolicyGate, VerifierPanel  # noqa: E402

FIXTURE_CATALOG = ROOT / "fixtures/incident_commander/catalog.json"


@pytest.fixture(scope="module")
def catalog() -> dict:
    return load_catalog(FIXTURE_CATALOG)


@pytest.fixture(scope="module")
def receipt(catalog: dict) -> dict:
    return build_ablation_receipt(catalog)


def test_context_on_authorizes_every_grounded_scenario(receipt: dict) -> None:
    on = receipt["arms"][MODE_ON]
    assert on["metrics"]["planAuthorizationRate"] == 1.0
    assert on["metrics"]["verifierApprovalRate"] == 1.0
    assert on["metrics"]["actionGroundingRate"] == 1.0
    assert on["blockReasonDistribution"] == {"authorized": on["scenarioCount"]}
    assert all(scenario["authorized"] for scenario in on["scenarios"])


def test_context_off_refuses_every_ungrounded_scenario(receipt: dict) -> None:
    off = receipt["arms"][MODE_OFF]
    assert off["metrics"]["planAuthorizationRate"] == 0.0
    assert off["metrics"]["verifierApprovalRate"] == 0.0
    # Only the three root-asset-grounded actions of six survive the grounding check.
    assert off["metrics"]["actionGroundingRate"] == 0.5
    assert not any(scenario["authorized"] for scenario in off["scenarios"])


def test_off_arm_surfaces_the_real_gate_reason_codes(receipt: dict) -> None:
    distribution = receipt["arms"][MODE_OFF]["blockReasonDistribution"]
    # These reason codes are produced by the production PolicyGate/VerifierPanel, not a
    # scripted branch — proving the refusal is real policy, not a hand-written label.
    assert "action_references_unknown_fact" in distribution
    assert "verification_not_approved" in distribution
    assert "verifier_quorum_not_met" in distribution
    # Three ungrounded actions (owner, blast-radius, runbook) across every scenario.
    n = receipt["arms"][MODE_OFF]["scenarioCount"]
    assert distribution["action_references_unknown_fact"] == 3 * n


def test_ablation_uses_production_pipeline_classes() -> None:
    # The gate the benchmark builds is the production PolicyGate; the panel is the
    # production VerifierPanel. Guards against a future refactor quietly reintroducing a
    # scripted stand-in.
    from benchmarks.incident_commander import real_pipeline_ablation as mod

    epoch = datetime(2026, 7, 31, tzinfo=UTC)
    assert isinstance(mod._build_gate(epoch), PolicyGate)
    assert isinstance(mod._build_panel(), VerifierPanel)


def test_planner_proposes_identical_plan_regardless_of_context(catalog: dict) -> None:
    """The only difference between arms must be the context, never the planner."""
    from benchmarks.incident_commander.real_pipeline_ablation import (
        _context_off,
        _context_on,
        _incident,
    )

    planner = DeterministicIncidentPlanner()
    record = catalog["incidents"][0]
    scenario = next(s for s in catalog["scenarios"] if s["incidentId"] == record["id"])
    owner = scenario["expected"]["ownerIds"][0]
    blast = tuple(scenario["expected"]["blastRadiusUrns"])
    clock = datetime(2026, 7, 31, tzinfo=UTC)

    incident = _incident(record, clock)
    on_plan = planner.plan(_context_on(incident, record, owner, blast, clock))
    off_plan = planner.plan(_context_off(incident, record, clock))

    # Same actions, same evidence citations — the planner never inspects which facts exist.
    assert [a.action_type for a in on_plan.actions] == [a.action_type for a in off_plan.actions]
    assert [a.evidence_fact_ids for a in on_plan.actions] == [
        a.evidence_fact_ids for a in off_plan.actions
    ]


def test_grounding_verifier_is_context_sensitive_and_shape_verifier_is_not(catalog: dict) -> None:
    from benchmarks.incident_commander.real_pipeline_ablation import (
        _context_off,
        _context_on,
        _incident,
    )

    planner = DeterministicIncidentPlanner()
    record = catalog["incidents"][0]
    scenario = next(s for s in catalog["scenarios"] if s["incidentId"] == record["id"])
    owner = scenario["expected"]["ownerIds"][0]
    blast = tuple(scenario["expected"]["blastRadiusUrns"])
    clock = datetime(2026, 7, 31, tzinfo=UTC)
    incident = _incident(record, clock)

    on_ctx = _context_on(incident, record, owner, blast, clock)
    off_ctx = _context_off(incident, record, clock)
    on_plan = planner.plan(on_ctx)
    off_plan = planner.plan(off_ctx)

    grounding = GroundingLintVerifier("g", "grounding-lint")
    shape = PolicyShapeVerifier("s", "policy-shape")

    assert grounding.verify(on_ctx, on_plan).approved is True
    assert grounding.verify(off_ctx, off_plan).approved is False
    # Shape verifier is context-independent: the plan is well-formed either way.
    assert shape.verify(on_ctx, on_plan).approved is True
    assert shape.verify(off_ctx, off_plan).approved is True


def test_receipt_is_deterministic(catalog: dict) -> None:
    first = build_ablation_receipt(catalog)
    second = build_ablation_receipt(catalog)
    assert first["contentDigest"] == second["contentDigest"]
    assert first["status"] == "PASS"


def test_ablation_holds_on_a_freshly_generated_catalog() -> None:
    """The ON/OFF separation is a property of the pipeline, not the checked-in fixture."""
    fresh = generate_catalog()
    receipt = build_ablation_receipt(fresh)
    assert receipt["status"] == "PASS"
    assert receipt["arms"][MODE_ON]["metrics"]["planAuthorizationRate"] == 1.0
    assert receipt["arms"][MODE_OFF]["metrics"]["planAuthorizationRate"] == 0.0


def test_receipt_keeps_claim_ceiling_and_honest_framing(receipt: dict) -> None:
    assert receipt["candidateOnly"] is True
    assert receipt["canClaimAGI"] is False
    assert receipt["externalValidation"] is False
    joined = " ".join(receipt["limitations"]).lower()
    assert "does not measure model or system capability" in joined
    assert "uplift" in joined
