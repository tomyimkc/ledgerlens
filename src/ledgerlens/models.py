"""Normalized, fail-closed models for Sophia-style failure-ledger findings."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DiagnosticSeverity(StrEnum):
    """Severity levels emitted while parsing a ledger."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class StatusClassification(StrEnum):
    """Small, intentionally conservative status vocabulary."""

    OPEN = "open"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"
    MALFORMED = "malformed"


class EvidenceKind(StrEnum):
    """Kinds of external evidence references preserved from a finding."""

    URL = "url"
    PATH = "path"
    IDENTIFIER = "identifier"


class ParseDiagnostic(BaseModel):
    """A machine-readable parser diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: DiagnosticSeverity
    message: str = Field(min_length=1)
    line_number: int | None = Field(default=None, ge=1)
    raw_segment: str | None = None


class EvidenceReference(BaseModel):
    """A normalized evidence URL, repository path, or opaque receipt identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: str = Field(min_length=1)
    kind: EvidenceKind
    label: str | None = None

    @field_validator("reference")
    @classmethod
    def strip_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("evidence reference cannot be blank")
        return value


def classify_status(status: str | None) -> StatusClassification:
    """Classify an authored status without inferring more than its leading token."""

    if not status:
        return StatusClassification.UNKNOWN

    normalized = status.strip().casefold()
    if normalized.startswith(("open", "partial", "pending", "blocked", "candidate", "unverified")):
        return StatusClassification.OPEN
    if normalized.startswith(("resolved", "fixed", "closed", "complete", "done")):
        return StatusClassification.RESOLVED
    if normalized.startswith(("superseded", "obsolete", "deprecated", "replaced")):
        return StatusClassification.SUPERSEDED
    return StatusClassification.UNKNOWN


class Finding(BaseModel):
    """A normalized failure-ledger finding.

    Fields that cannot be assigned safely on a malformed Markdown row remain ``None``.
    ``raw_middle`` retains the ambiguous source text so no content is silently discarded.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(min_length=1)
    status: str | None = None
    status_classification: StatusClassification = StatusClassification.UNKNOWN
    claim_impact: str | None = None
    required_response: str | None = None
    kind: str | None = None

    candidate_only: bool = Field(default=True, alias="candidateOnly")
    can_claim_agi: bool = Field(default=False, alias="canClaimAGI")

    owners: list[str] = Field(default_factory=list)
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    supersedes_ids: list[str] = Field(default_factory=list)

    recorded_on: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None

    source: str | None = None
    source_line: int | None = Field(default=None, ge=1)
    raw_row: str | None = None
    raw_middle: str | None = None
    parse_diagnostics: list[ParseDiagnostic] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("finding id cannot be blank")
        if "\n" in value or "\r" in value or "|" in value:
            raise ValueError("finding id cannot contain newlines or pipes")
        return value

    @field_validator("owners", "supersedes_ids", mode="after")
    @classmethod
    def deduplicate_strings(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @field_validator("evidence_references", mode="after")
    @classmethod
    def deduplicate_evidence(cls, values: list[EvidenceReference]) -> list[EvidenceReference]:
        seen: set[tuple[str, EvidenceKind]] = set()
        result: list[EvidenceReference] = []
        for value in values:
            key = (value.reference, value.kind)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @model_validator(mode="after")
    def derive_status_classification(self) -> Self:
        if any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.parse_diagnostics
        ):
            object.__setattr__(self, "status_classification", StatusClassification.MALFORMED)
        elif self.status_classification is StatusClassification.UNKNOWN:
            object.__setattr__(self, "status_classification", classify_status(self.status))
        return self

    @property
    def is_malformed(self) -> bool:
        return self.status_classification is StatusClassification.MALFORMED

    @property
    def has_owner(self) -> bool:
        return bool(self.owners)

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_references)


class LedgerParseResult(BaseModel):
    """All parsed findings plus ledger-level diagnostics."""

    model_config = ConfigDict(extra="forbid")

    source: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = Field(default_factory=list)

    @property
    def errors(self) -> list[ParseDiagnostic]:
        return [
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.ERROR
        ]

    @property
    def valid_findings(self) -> list[Finding]:
        return [finding for finding in self.findings if not finding.is_malformed]

    @property
    def malformed_findings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.is_malformed]

    @property
    def is_valid(self) -> bool:
        return not self.errors


class LedgerParseError(ValueError):
    """Raised when strict parsing encounters any error-level diagnostic."""

    def __init__(self, result: LedgerParseResult):
        self.result = result
        codes = sorted({diagnostic.code for diagnostic in result.errors})
        detail = ", ".join(codes) if codes else "unknown parse error"
        super().__init__(f"failure ledger is malformed: {detail}")
