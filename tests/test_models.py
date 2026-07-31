"""Deterministic tests for normalized LedgerLens models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ledgerlens.models import (
    DiagnosticSeverity,
    EvidenceKind,
    EvidenceReference,
    Finding,
    ParseDiagnostic,
    StatusClassification,
    classify_status,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("OPEN — follow-up pending", StatusClassification.OPEN),
        ("Partial", StatusClassification.OPEN),
        ("UNVERIFIED", StatusClassification.OPEN),
        ("RESOLVED 2026-07-21", StatusClassification.RESOLVED),
        ("Fixed after rerun", StatusClassification.RESOLVED),
        ("SUPERSEDED by newer-id", StatusClassification.SUPERSEDED),
        ("Not resolved despite prior text", StatusClassification.UNKNOWN),
        (None, StatusClassification.UNKNOWN),
    ],
)
def test_classify_status_uses_leading_authored_status(
    status: str | None, expected: StatusClassification
) -> None:
    assert classify_status(status) is expected


def test_finding_defaults_are_candidate_only_and_not_agi_claimable() -> None:
    finding = Finding(id="fixture-finding", status="OPEN")

    assert finding.candidate_only is True
    assert finding.can_claim_agi is False
    assert finding.status_classification is StatusClassification.OPEN
    assert finding.model_dump(by_alias=True)["candidateOnly"] is True
    assert finding.model_dump(by_alias=True)["canClaimAGI"] is False


def test_error_diagnostic_forces_malformed_classification() -> None:
    finding = Finding(
        id="unsafe-row",
        status="OPEN",
        parse_diagnostics=[
            ParseDiagnostic(
                code="unsafe_unescaped_pipe",
                severity=DiagnosticSeverity.ERROR,
                message="ambiguous columns",
                line_number=12,
            )
        ],
    )

    assert finding.is_malformed
    assert finding.status_classification is StatusClassification.MALFORMED


def test_finding_deduplicates_normalized_lists_without_reordering() -> None:
    evidence = EvidenceReference(
        reference="https://example.org/receipt.json",
        kind=EvidenceKind.URL,
    )
    finding = Finding(
        id="dedupe",
        owners=["team-a", "team-a", "team-b"],
        supersedes_ids=["old-a", "old-a", "old-b"],
        evidence_references=[evidence, evidence],
    )

    assert finding.owners == ["team-a", "team-b"]
    assert finding.supersedes_ids == ["old-a", "old-b"]
    assert finding.evidence_references == [evidence]


def test_finding_preserves_timestamps_and_raw_ambiguous_text() -> None:
    timestamp = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
    finding = Finding(
        id="timestamped-2026-07-20",
        created_at=timestamp,
        raw_middle="OPEN | ambiguous | middle",
    )

    assert finding.created_at == timestamp
    assert finding.raw_middle == "OPEN | ambiguous | middle"


@pytest.mark.parametrize("finding_id", ["", "bad|id", "bad\nid"])
def test_finding_rejects_unsafe_ids(finding_id: str) -> None:
    with pytest.raises(ValidationError):
        Finding(id=finding_id)
