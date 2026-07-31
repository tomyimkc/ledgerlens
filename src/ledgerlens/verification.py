"""Independent verifier panel and deterministic fail-closed authorization gate."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from ledgerlens.incident_models import (
    ActionPlan,
    ActionRisk,
    ClaimBoundedModel,
    IncidentContext,
)


class VerifierAssessment(BaseModel):
    """Minimal structured response expected from an injected verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = Field(min_length=1)
    unverifiable_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    unverifiable_action_ids: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VerifierVerdict(ClaimBoundedModel):
    """A verifier assessment bound to one incident, plan, model, and family."""

    incident_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    verifier_id: str = Field(min_length=1)
    verifier_family: str = Field(min_length=1)
    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = Field(min_length=1)
    unverifiable_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    unverifiable_action_ids: tuple[str, ...] = Field(default_factory=tuple)
    error: str | None = Field(default=None, min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VerifierPanelConfig(BaseModel):
    """Quorum and confidence requirements for independent verifier families."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quorum: int = Field(default=2, ge=2)
    minimum_families: int = Field(default=2, ge=2)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    require_planner_independence: bool = True
    fail_on_verifier_error: bool = True


class VerificationPanelResult(ClaimBoundedModel):
    """Deterministic aggregate of all verifier-family votes."""

    incident_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    approved: bool
    quorum: int = Field(ge=2)
    approvals: int = Field(ge=0)
    minimum_families: int = Field(ge=2)
    participating_families: tuple[str, ...]
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    aggregate_confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[str, ...]
    verdicts: tuple[VerifierVerdict, ...]


@runtime_checkable
class PlanVerifier(Protocol):
    """Injected verifier interface; each implementation declares its model family."""

    verifier_id: str
    family: str

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierAssessment | VerifierVerdict | Mapping[str, object]:
        """Assess a plan without executing tools or mutating incident state."""


Verifier = PlanVerifier


class VerifierPanel:
    """Run independent verifier families and aggregate votes without model arbitration."""

    def __init__(
        self,
        verifiers: Sequence[PlanVerifier],
        *,
        config: VerifierPanelConfig | None = None,
    ) -> None:
        self.config = config or VerifierPanelConfig()
        self._verifiers = tuple(verifiers)
        families = tuple(_required_identity(verifier, "family") for verifier in self._verifiers)
        if len(families) < self.config.minimum_families:
            raise ValueError(
                f"verifier panel requires at least {self.config.minimum_families} families"
            )
        if len(families) != len(set(family.casefold() for family in families)):
            raise ValueError("verifier families must be unique and independent")
        if self.config.quorum > len(families):
            raise ValueError("verifier quorum cannot exceed the number of verifier families")

    def verify(self, context: IncidentContext, plan: ActionPlan) -> VerificationPanelResult:
        """Collect every configured vote and compute a deterministic quorum result."""

        families = tuple(_required_identity(verifier, "family") for verifier in self._verifiers)
        if self.config.require_planner_independence and plan.planner_family.casefold() in {
            family.casefold() for family in families
        }:
            return VerificationPanelResult(
                incident_id=context.incident.incident_id,
                plan_id=plan.plan_id,
                approved=False,
                quorum=self.config.quorum,
                approvals=0,
                minimum_families=self.config.minimum_families,
                participating_families=families,
                confidence_threshold=self.config.confidence_threshold,
                aggregate_confidence=0.0,
                reason_codes=("planner_verifier_family_overlap",),
                verdicts=(),
            )

        verdicts = tuple(
            self._run_verifier(verifier, context, plan) for verifier in self._verifiers
        )
        eligible = tuple(
            verdict
            for verdict in verdicts
            if verdict.approved
            and verdict.error is None
            and verdict.confidence >= self.config.confidence_threshold
            and not verdict.unverifiable_fact_ids
            and not verdict.unverifiable_action_ids
        )
        eligible_families = {verdict.verifier_family.casefold() for verdict in eligible}
        approvals = len(eligible_families)
        has_error = any(verdict.error is not None for verdict in verdicts)
        has_unverifiable = any(
            verdict.unverifiable_fact_ids or verdict.unverifiable_action_ids for verdict in verdicts
        )
        reason_codes: list[str] = []
        if has_error:
            reason_codes.append("verifier_error")
        if has_unverifiable:
            reason_codes.append("unverifiable_items")
        if approvals < self.config.quorum:
            reason_codes.append("quorum_not_met")
        if any(
            verdict.approved and verdict.confidence < self.config.confidence_threshold
            for verdict in verdicts
        ):
            reason_codes.append("confidence_below_threshold")
        approved = (
            approvals >= self.config.quorum
            and not has_unverifiable
            and not (self.config.fail_on_verifier_error and has_error)
        )
        aggregate_confidence = min(verdict.confidence for verdict in eligible) if eligible else 0.0
        if approved:
            reason_codes.append("quorum_approved")

        return VerificationPanelResult(
            incident_id=context.incident.incident_id,
            plan_id=plan.plan_id,
            approved=approved,
            quorum=self.config.quorum,
            approvals=approvals,
            minimum_families=self.config.minimum_families,
            participating_families=families,
            confidence_threshold=self.config.confidence_threshold,
            aggregate_confidence=aggregate_confidence,
            reason_codes=tuple(reason_codes),
            verdicts=verdicts,
        )

    evaluate = verify

    def _run_verifier(
        self,
        verifier: PlanVerifier,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierVerdict:
        verifier_id = _required_identity(verifier, "verifier_id")
        family = _required_identity(verifier, "family")
        try:
            raw = verifier.verify(context, plan)
            if isinstance(raw, VerifierVerdict):
                mismatches = []
                if raw.incident_id != context.incident.incident_id:
                    mismatches.append("incident_id")
                if raw.plan_id != plan.plan_id:
                    mismatches.append("plan_id")
                if raw.verifier_id != verifier_id:
                    mismatches.append("verifier_id")
                if raw.verifier_family.casefold() != family.casefold():
                    mismatches.append("verifier_family")
                if mismatches:
                    raise ValueError("verifier verdict identity mismatch: " + ", ".join(mismatches))
                return raw
            assessment = (
                raw
                if isinstance(raw, VerifierAssessment)
                else VerifierAssessment.model_validate(raw)
            )
            return VerifierVerdict(
                incident_id=context.incident.incident_id,
                plan_id=plan.plan_id,
                verifier_id=verifier_id,
                verifier_family=family,
                approved=assessment.approved,
                confidence=assessment.confidence,
                reasons=assessment.reasons,
                unverifiable_fact_ids=assessment.unverifiable_fact_ids,
                unverifiable_action_ids=assessment.unverifiable_action_ids,
                metadata=assessment.metadata,
            )
        except Exception as exc:  # Verifier failures are data, never authorization.
            return VerifierVerdict(
                incident_id=context.incident.incident_id,
                plan_id=plan.plan_id,
                verifier_id=verifier_id,
                verifier_family=family,
                approved=False,
                confidence=0.0,
                reasons=("verifier failed closed",),
                error=f"{type(exc).__name__}: {exc}",
            )


class ActionAllowance(BaseModel):
    """Exact allowlist entry for one automatable action type."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    action_type: str = Field(min_length=1)
    targets: frozenset[str] = Field(min_length=1)
    allowed_parameter_keys: frozenset[str] = Field(default_factory=frozenset)
    required_parameter_keys: frozenset[str] = Field(default_factory=frozenset)
    maximum_risk: ActionRisk = ActionRisk.LOW
    automatable: bool = True

    @model_validator(mode="after")
    def required_parameters_must_be_allowed(self) -> ActionAllowance:
        if not self.required_parameter_keys <= self.allowed_parameter_keys:
            raise ValueError("required parameter keys must be included in allowed parameter keys")
        return self


class PolicyConfig(BaseModel):
    """Deterministic authorization policy, independent of all model output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(default="1", min_length=1)
    allowances: tuple[ActionAllowance, ...] = Field(min_length=1)
    minimum_plan_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    minimum_verifier_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    required_quorum: int = Field(default=2, ge=2)
    minimum_verifier_families: int = Field(default=2, ge=2)
    max_actions: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def require_unique_allowances(self) -> PolicyConfig:
        action_types = [allowance.action_type for allowance in self.allowances]
        if len(action_types) != len(set(action_types)):
            raise ValueError("policy contains duplicate action-type allowances")
        return self


class AuthorizationDecision(ClaimBoundedModel):
    """Policy-gate result consumed by the orchestrator."""

    incident_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    evaluated_at: datetime
    authorized: bool
    reason_codes: tuple[str, ...]
    authorized_action_ids: tuple[str, ...]


class PolicyGate:
    """Authorize only grounded, allowlisted actions with verified quorum."""

    def __init__(
        self,
        config: PolicyConfig,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self._clock = clock or (lambda: datetime.now(UTC))
        self._allowances = {
            allowance.action_type: allowance for allowance in self.config.allowances
        }

    def authorize(
        self,
        context: IncidentContext,
        plan: ActionPlan,
        verification: VerificationPanelResult,
    ) -> AuthorizationDecision:
        """Evaluate all policy rules and deny when any required fact is unknown."""

        reasons: list[str] = []
        incident_id = context.incident.incident_id
        if plan.incident_id != incident_id:
            reasons.append("plan_incident_mismatch")
        if verification.incident_id != incident_id or verification.plan_id != plan.plan_id:
            reasons.append("verification_identity_mismatch")
        if context.incident.status.value in {"resolved", "closed"}:
            reasons.append("incident_not_actionable")
        if not plan.actions:
            reasons.append("empty_plan")
        if len(plan.actions) > self.config.max_actions:
            reasons.append("too_many_actions")
        if plan.confidence < self.config.minimum_plan_confidence:
            reasons.append("plan_confidence_below_threshold")

        eligible_votes = tuple(
            verdict
            for verdict in verification.verdicts
            if verdict.approved
            and verdict.error is None
            and verdict.confidence >= self.config.minimum_verifier_confidence
            and not verdict.unverifiable_fact_ids
            and not verdict.unverifiable_action_ids
            and verdict.incident_id == incident_id
            and verdict.plan_id == plan.plan_id
        )
        eligible_families = {verdict.verifier_family.casefold() for verdict in eligible_votes}
        participating_families = {
            verdict.verifier_family.casefold() for verdict in verification.verdicts
        }
        if not verification.approved:
            reasons.append("verification_not_approved")
        if len(participating_families) < self.config.minimum_verifier_families:
            reasons.append("insufficient_verifier_families")
        if len(eligible_families) < self.config.required_quorum:
            reasons.append("verifier_quorum_not_met")
        if any(verdict.error is not None for verdict in verification.verdicts):
            reasons.append("verifier_error")
        if any(
            verdict.unverifiable_fact_ids or verdict.unverifiable_action_ids
            for verdict in verification.verdicts
        ):
            reasons.append("verifier_reported_unverifiable_items")
        if plan.planner_family.casefold() in participating_families:
            reasons.append("planner_verifier_family_overlap")

        fact_ids = context.fact_ids
        for action in plan.actions:
            allowance = self._allowances.get(action.action_type)
            if allowance is None:
                reasons.append(f"action_not_allowlisted:{action.action_id}")
                continue
            if not allowance.automatable or action.requires_human_approval:
                reasons.append(f"action_not_automatable:{action.action_id}")
            if action.target not in allowance.targets:
                reasons.append(f"target_not_allowlisted:{action.action_id}")
            parameter_keys = frozenset(action.parameters)
            if not parameter_keys <= allowance.allowed_parameter_keys:
                reasons.append(f"parameter_not_allowlisted:{action.action_id}")
            if not allowance.required_parameter_keys <= parameter_keys:
                reasons.append(f"required_parameter_missing:{action.action_id}")
            if _RISK_ORDER[action.risk] > _RISK_ORDER[allowance.maximum_risk]:
                reasons.append(f"action_risk_exceeds_allowance:{action.action_id}")
            if not action.evidence_fact_ids:
                reasons.append(f"action_has_no_grounding:{action.action_id}")
            elif not frozenset(action.evidence_fact_ids) <= fact_ids:
                reasons.append(f"action_references_unknown_fact:{action.action_id}")

        reason_codes = tuple(dict.fromkeys(reasons))
        authorized = not reason_codes
        return AuthorizationDecision(
            incident_id=incident_id,
            plan_id=plan.plan_id,
            policy_version=self.config.version,
            evaluated_at=self._clock(),
            authorized=authorized,
            reason_codes=reason_codes or ("authorized",),
            authorized_action_ids=(
                tuple(action.action_id for action in plan.actions) if authorized else ()
            ),
        )


DeterministicPolicyGate = PolicyGate

_RISK_ORDER = {
    ActionRisk.LOW: 0,
    ActionRisk.MEDIUM: 1,
    ActionRisk.HIGH: 2,
    ActionRisk.CRITICAL: 3,
}


def _required_identity(value: object, attribute: str) -> str:
    identity = getattr(value, attribute, None)
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError(f"verifier {attribute} must be a non-empty string")
    return identity.strip()
