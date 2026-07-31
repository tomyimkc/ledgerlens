"""Tests for the typed Autonomous Data Incident Commander models."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ledgerlens.incident_models import (
    ActionPlan,
    ActionReceipt,
    ActionReceiptStatus,
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

NOW = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)


def _trigger() -> IncidentTrigger:
    return IncidentTrigger(
        trigger_id="trigger-1",
        source="datahub",
        kind="freshness_regression",
        occurred_at=NOW,
        idempotency_key="trigger:warehouse.orders:2026-07-31T08",
        evidence_references=("urn:li:dataset:orders",),
    )


def _incident() -> Incident:
    return Incident(
        incident_id="incident-1",
        title="Orders table is stale",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        trigger=_trigger(),
        affected_entities=("urn:li:dataset:orders",),
    )


def _fact() -> IncidentFact:
    return IncidentFact(
        fact_id="fact-freshness",
        statement="The orders freshness assertion exceeded its threshold.",
        evidence=(
            EvidencePointer(
                reference="urn:li:assertion:orders-freshness",
                kind=EvidenceKind.DATAHUB_ENTITY,
                observed_at=NOW,
                content_digest="sha256:fixture",
            ),
        ),
    )


def _action() -> PlannedAction:
    return PlannedAction(
        action_id="notify-owner",
        action_type="notify_owner",
        target="urn:li:corpgroup:data-platform",
        parameters={"channel": "incident-room"},
        rationale="The accountable owner must receive the grounded freshness alert.",
        evidence_fact_ids=("fact-freshness",),
        idempotency_key="incident-1:notify-owner",
        risk=ActionRisk.LOW,
    )


def test_claim_ceiling_is_preserved_by_incident_plan_context_and_receipt() -> None:
    context = IncidentContext(
        context_id="context-1",
        incident=_incident(),
        collected_at=NOW,
        facts=(_fact(),),
    )
    plan = ActionPlan(
        plan_id="plan-1",
        incident_id="incident-1",
        planner_id="planner-a",
        planner_family="planner-family",
        created_at=NOW,
        confidence=0.93,
        summary="Notify the owner with the grounded assertion receipt.",
        actions=(_action(),),
    )
    receipt = ActionReceipt(
        receipt_id="receipt-1",
        run_id="run-1",
        incident_id="incident-1",
        plan_id="plan-1",
        action_id="notify-owner",
        idempotency_key="incident-1:notify-owner",
        executor="fixture-executor",
        status=ActionReceiptStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
        message="notification accepted",
    )

    for model in (context.incident, context, plan, receipt):
        payload = model.model_dump(by_alias=True)
        assert payload["candidateOnly"] is True
        assert payload["canClaimAGI"] is False


@pytest.mark.parametrize(
    "unsafe",
    [
        {"candidateOnly": False},
        {"canClaimAGI": True},
    ],
)
def test_claim_ceiling_cannot_be_overridden(unsafe: dict[str, bool]) -> None:
    with pytest.raises(ValidationError):
        Incident(
            incident_id="incident-unsafe",
            title="Unsafe claim mutation",
            severity=IncidentSeverity.LOW,
            detected_at=NOW,
            trigger=_trigger(),
            **unsafe,
        )


def test_context_facts_require_evidence_and_unique_ids() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        IncidentFact(
            fact_id="unverifiable",
            statement="An unsupported assertion.",
            evidence=(),
        )

    with pytest.raises(ValidationError, match="duplicate fact IDs"):
        IncidentContext(
            context_id="duplicate-context",
            incident=_incident(),
            collected_at=NOW,
            facts=(_fact(), _fact()),
        )


def test_plan_rejects_duplicate_action_and_idempotency_identity() -> None:
    duplicate_key = _action().model_copy(update={"action_id": "notify-owner-again"})
    with pytest.raises(ValidationError, match="duplicate idempotency keys"):
        ActionPlan(
            plan_id="plan-duplicate",
            incident_id="incident-1",
            planner_id="planner-a",
            planner_family="planner-family",
            created_at=NOW,
            confidence=0.95,
            summary="Unsafe duplicate execution keys.",
            actions=(_action(), duplicate_key),
        )


def test_receipt_requires_monotonic_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ActionReceipt(
            receipt_id="receipt-naive",
            run_id="run-1",
            incident_id="incident-1",
            plan_id="plan-1",
            action_id="notify-owner",
            idempotency_key="incident-1:notify-owner",
            executor="fixture-executor",
            status=ActionReceiptStatus.SUCCEEDED,
            started_at=datetime(2026, 7, 31, 8, 0),
            completed_at=NOW,
            message="invalid timestamp",
        )

    with pytest.raises(ValidationError, match="cannot precede"):
        ActionReceipt(
            receipt_id="receipt-reversed",
            run_id="run-1",
            incident_id="incident-1",
            plan_id="plan-1",
            action_id="notify-owner",
            idempotency_key="incident-1:notify-owner",
            executor="fixture-executor",
            status=ActionReceiptStatus.SUCCEEDED,
            started_at=NOW,
            completed_at=NOW - timedelta(seconds=1),
            message="invalid ordering",
        )
