"""Tests for strict JSON planner and verifier role adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ledgerlens.ai_roles import JsonIncidentPlanner, JsonPlanVerifier
from ledgerlens.incident_models import (
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentTrigger,
)

NOW = datetime(2026, 7, 31, tzinfo=UTC)


class FakeModel:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def _context() -> IncidentContext:
    trigger = IncidentTrigger(
        trigger_id="trigger-1",
        source="datahub",
        kind="schema_change",
        occurred_at=NOW,
        idempotency_key="schema-change-1",
        payload={"assetUrn": "urn:li:dataset:orders"},
    )
    incident = Incident(
        incident_id="incident-1",
        title="orders schema changed",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        trigger=trigger,
        affected_entities=("urn:li:dataset:orders",),
    )
    return IncidentContext(
        context_id="context-1",
        incident=incident,
        collected_at=NOW,
        facts=(
            IncidentFact(
                fact_id="fact-owner",
                statement="The recorded owner is analytics-platform.",
                evidence=(
                    EvidencePointer(
                        reference="urn:li:dataset:orders#ownership",
                        kind=EvidenceKind.DATAHUB_ENTITY,
                    ),
                ),
            ),
        ),
    )


def test_planner_builds_identity_and_ids_outside_model_output() -> None:
    model = FakeModel(
        {
            "confidence": 0.93,
            "summary": "Notify the recorded owner.",
            "actions": [
                {
                    "action_type": "github.issue.create",
                    "target": "tomyimkc/ledgerlens",
                    "parameters": {"title": "Investigate orders schema change"},
                    "rationale": "The owner must investigate the recorded schema change.",
                    "evidence_fact_ids": ["fact-owner"],
                    "risk": "low",
                    "requires_human_approval": False,
                }
            ],
        }
    )
    ids = iter(("action-1", "idempotency-1", "plan-1"))
    planner = JsonIncidentPlanner(
        model,
        planner_id="planner-sol",
        family="gpt-5.6-sol",
        clock=lambda: NOW,
        id_factory=lambda prefix: next(ids),
    )

    plan = planner.plan(_context())

    assert plan.plan_id == "plan-1"
    assert plan.planner_id == "planner-sol"
    assert plan.planner_family == "gpt-5.6-sol"
    assert plan.actions[0].action_id == "action-1"
    assert plan.actions[0].idempotency_key == "idempotency-1"
    assert model.calls[0]["temperature"] == 0.0


def test_verifier_returns_only_typed_assessment() -> None:
    model = FakeModel(
        {
            "approved": True,
            "confidence": 0.91,
            "reasons": ["All actions cite supplied evidence."],
            "unverifiable_fact_ids": [],
            "unverifiable_action_ids": [],
            "metadata": {"check": "grounding"},
        }
    )
    planner_model = FakeModel(
        {
            "confidence": 0.9,
            "summary": "Notify owner.",
            "actions": [
                {
                    "action_type": "github.issue.create",
                    "target": "tomyimkc/ledgerlens",
                    "parameters": {"title": "Investigate"},
                    "rationale": "Recorded owner should investigate.",
                    "evidence_fact_ids": ["fact-owner"],
                    "risk": "low",
                    "requires_human_approval": False,
                }
            ],
        }
    )
    ids = iter(("action-1", "key-1", "plan-1"))
    plan = JsonIncidentPlanner(
        planner_model,
        planner_id="planner",
        family="gpt-5.6-sol",
        clock=lambda: NOW,
        id_factory=lambda prefix: next(ids),
    ).plan(_context())
    verifier = JsonPlanVerifier(
        model,
        verifier_id="verifier-terra",
        family="gpt-5.6-terra",
    )

    assessment = verifier.verify(_context(), plan)

    assert assessment.approved is True
    assert assessment.confidence == 0.91
    assert model.calls[0]["context"]["candidatePlan"]["plan_id"] == "plan-1"
