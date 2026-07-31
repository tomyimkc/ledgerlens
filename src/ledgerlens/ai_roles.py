"""AI planner and verifier roles backed by strict JSON model clients."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.incident_models import (
    ActionPlan,
    ActionRisk,
    IncidentContext,
    PlannedAction,
)
from ledgerlens.verification import VerifierAssessment


class JsonModel(Protocol):
    """Minimal model contract shared by hosted and deterministic test clients."""

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Return exactly one parsed JSON object."""


class _PlannerAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)
    evidence_fact_ids: tuple[str, ...] = Field(min_length=1)
    risk: ActionRisk = ActionRisk.LOW
    requires_human_approval: bool = False


class _PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    actions: tuple[_PlannerAction, ...] = Field(min_length=1, max_length=10)


class JsonIncidentPlanner:
    """Construct a typed action plan from model JSON without trusting identity fields."""

    def __init__(
        self,
        model: JsonModel,
        *,
        planner_id: str,
        family: str,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.model = model
        self.planner_id = planner_id
        self.family = family
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4()}")

    def plan(self, context: IncidentContext) -> ActionPlan:
        raw = self.model.complete_json(
            system=(
                "You are the planning component of a data-incident commander. "
                "Return JSON only. Use only supplied fact IDs. Never execute tools, "
                "invent owners, infer unsupported blast radius, or raise claim ceilings. "
                "Prefer reversible, idempotent operational actions. When "
                "incidentContext.metadata.automationPolicy is supplied, treat its "
                "requiredActions as an exact action-type, target, and parameter contract: "
                "include every required action exactly once and do not invent additional "
                "actions or targets."
            ),
            prompt=(
                "Create an action plan with exactly these top-level keys: confidence, "
                "summary, and actions. confidence MUST be a JSON number from 0.0 to 1.0 "
                "(never a word such as high). summary MUST be a string. actions MUST be "
                "an array. Each action requires action_type (string), target (string), "
                "parameters (object), rationale (string), evidence_fact_ids (array of "
                "supplied fact-ID strings), risk (one of low, medium, high, critical), "
                "and requires_human_approval (JSON boolean). "
                "Allowed action types and targets are enforced later by deterministic policy."
            ),
            context=context.model_dump(mode="json", by_alias=True),
            temperature=0.0,
        )
        candidate = _PlannerResponse.model_validate(raw)
        actions = tuple(
            PlannedAction(
                action_id=self._id_factory("action"),
                action_type=item.action_type,
                target=item.target,
                parameters=item.parameters,
                rationale=item.rationale,
                evidence_fact_ids=item.evidence_fact_ids,
                idempotency_key=self._id_factory("idempotency"),
                risk=item.risk,
                requires_human_approval=item.requires_human_approval,
            )
            for item in candidate.actions
        )
        return ActionPlan(
            plan_id=self._id_factory("plan"),
            incident_id=context.incident.incident_id,
            planner_id=self.planner_id,
            planner_family=self.family,
            created_at=self._clock(),
            confidence=candidate.confidence,
            summary=candidate.summary,
            actions=actions,
        )


class JsonPlanVerifier:
    """Independent model role that can only emit a verifier assessment."""

    def __init__(
        self,
        model: JsonModel,
        *,
        verifier_id: str,
        family: str,
    ) -> None:
        self.model = model
        self.verifier_id = verifier_id
        self.family = family

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierAssessment:
        raw = self.model.complete_json(
            system=(
                "You are an independent incident-action verifier. Return JSON only. "
                "Reject any action that lacks cited fact IDs, exceeds the evidence, "
                "contains an unsafe or irreversible target, or invents metadata. "
                "You cannot execute tools or change the plan. When automationPolicy is "
                "present, verify exact action-type, target, required-action completeness, "
                "parameter allowlists, and forbidden-action exclusions."
            ),
            prompt=(
                "Return exactly approved (JSON boolean), confidence (JSON number from "
                "0.0 to 1.0, never a word), reasons (non-empty array of strings), "
                "unverifiable_fact_ids (array of strings), unverifiable_action_ids "
                "(array of strings), and metadata (object). Approval requires every "
                "action and factual rationale to be independently supported by the "
                "supplied context."
            ),
            context={
                "incidentContext": context.model_dump(mode="json", by_alias=True),
                "candidatePlan": plan.model_dump(mode="json", by_alias=True),
            },
            temperature=0.0,
        )
        return VerifierAssessment.model_validate(raw)
