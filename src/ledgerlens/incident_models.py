"""Typed, claim-bounded models for autonomous data-incident response."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)


class ClaimBoundedModel(BaseModel):
    """Base model that makes LedgerLens's claim ceiling impossible to raise."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    candidate_only: Literal[True] = Field(default=True, alias="candidateOnly")
    can_claim_agi: Literal[False] = Field(default=False, alias="canClaimAGI")


class IncidentSeverity(StrEnum):
    """Operational severity, not a statement about scientific validity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    """Conservative incident lifecycle states."""

    TRIGGERED = "triggered"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EvidenceKind(StrEnum):
    """Evidence-pointer types accepted as grounding for context facts."""

    DATAHUB_ENTITY = "datahub_entity"
    METRIC = "metric"
    QUERY_RESULT = "query_result"
    LOG = "log"
    RECEIPT = "receipt"
    SOURCE_RECORD = "source_record"


class ActionRisk(StrEnum):
    """Risk classification used by the deterministic policy gate."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionReceiptStatus(StrEnum):
    """Terminal status recorded for each authorized action attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


class IncidentTrigger(ClaimBoundedModel):
    """A deduplicated, externally observed signal that starts an incident run."""

    trigger_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    occurred_at: datetime
    idempotency_key: str = Field(min_length=1)
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_references: tuple[str, ...] = Field(default_factory=tuple)

    _normalize_occurred_at = field_validator("occurred_at")(_utc_datetime)

    @field_validator("evidence_references", mode="after")
    @classmethod
    def normalize_evidence_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonblank(values, field_name="evidence_references")


class Incident(ClaimBoundedModel):
    """The typed incident envelope passed through the commander."""

    incident_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.TRIGGERED
    detected_at: datetime
    trigger: IncidentTrigger
    affected_entities: tuple[str, ...] = Field(default_factory=tuple)

    _normalize_detected_at = field_validator("detected_at")(_utc_datetime)

    @field_validator("affected_entities", mode="after")
    @classmethod
    def normalize_affected_entities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonblank(values, field_name="affected_entities")


class EvidencePointer(BaseModel):
    """A stable pointer that lets a verifier inspect the basis for a fact."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    reference: str = Field(min_length=1)
    kind: EvidenceKind
    observed_at: datetime | None = None
    content_digest: str | None = Field(default=None, min_length=1)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        return _utc_datetime(value) if value is not None else None


class IncidentFact(BaseModel):
    """A context fact that is structurally grounded by one or more pointers."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fact_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence: tuple[EvidencePointer, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_evidence(self) -> IncidentFact:
        keys = [(item.kind, item.reference) for item in self.evidence]
        if len(keys) != len(set(keys)):
            raise ValueError(f"fact {self.fact_id!r} contains duplicate evidence pointers")
        return self


class IncidentContext(ClaimBoundedModel):
    """Grounded context assembled by an injected context provider."""

    context_id: str = Field(min_length=1)
    incident: Incident
    collected_at: datetime
    facts: tuple[IncidentFact, ...] = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _normalize_collected_at = field_validator("collected_at")(_utc_datetime)

    @model_validator(mode="after")
    def require_unique_fact_ids(self) -> IncidentContext:
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("incident context contains duplicate fact IDs")
        return self

    @property
    def fact_ids(self) -> frozenset[str]:
        return frozenset(fact.fact_id for fact in self.facts)


class PlannedAction(BaseModel):
    """A proposed tool action; execution remains impossible until authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    action_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)
    evidence_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    idempotency_key: str = Field(min_length=1)
    risk: ActionRisk = ActionRisk.LOW
    requires_human_approval: bool = False

    @field_validator("evidence_fact_ids", mode="after")
    @classmethod
    def normalize_evidence_fact_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonblank(values, field_name="evidence_fact_ids")


class ActionPlan(ClaimBoundedModel):
    """Planner output consumed by independent verifiers and deterministic policy."""

    plan_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    planner_id: str = Field(min_length=1)
    planner_family: str = Field(min_length=1)
    created_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    actions: tuple[PlannedAction, ...] = Field(default_factory=tuple)

    _normalize_created_at = field_validator("created_at")(_utc_datetime)

    @model_validator(mode="after")
    def require_unique_action_identity(self) -> ActionPlan:
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action plan contains duplicate action IDs")
        idempotency_keys = [action.idempotency_key for action in self.actions]
        if len(idempotency_keys) != len(set(idempotency_keys)):
            raise ValueError("action plan contains duplicate idempotency keys")
        return self

    @property
    def action_ids(self) -> frozenset[str]:
        return frozenset(action.action_id for action in self.actions)


class ActionReceipt(ClaimBoundedModel):
    """Immutable receipt created around an injected executor callback."""

    receipt_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    executor: str = Field(min_length=1)
    status: ActionReceiptStatus
    started_at: datetime
    completed_at: datetime
    message: str = Field(min_length=1)
    output_references: tuple[str, ...] = Field(default_factory=tuple)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    _normalize_started_at = field_validator("started_at")(_utc_datetime)
    _normalize_completed_at = field_validator("completed_at")(_utc_datetime)

    @field_validator("output_references", mode="after")
    @classmethod
    def normalize_output_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonblank(values, field_name="output_references")

    @model_validator(mode="after")
    def require_monotonic_timestamps(self) -> ActionReceipt:
        if self.completed_at < self.started_at:
            raise ValueError("action receipt completed_at cannot precede started_at")
        return self


@runtime_checkable
class IncidentPlanner(Protocol):
    """Injected planner interface; implementations may be AI-backed or deterministic."""

    planner_id: str
    family: str

    def plan(self, context: IncidentContext) -> ActionPlan:
        """Return a typed candidate plan without executing any action."""


Planner = IncidentPlanner


def _unique_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain blank values")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} cannot contain duplicate values")
    return normalized
