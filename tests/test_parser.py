"""Tests for the conservative Sophia-style Markdown ledger parser."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ledgerlens.models import LedgerParseError, StatusClassification
from ledgerlens.parser import parse_ledger, parse_ledger_file

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sophia_failure_ledger_sanitized.md"


def _by_id(result_id: str, findings: list) -> list:
    return [finding for finding in findings if finding.id == result_id]


def test_public_fixture_covers_valid_and_malformed_cases() -> None:
    result = parse_ledger_file(FIXTURE)

    assert len(result.findings) == 10
    assert len(result.valid_findings) == 6
    assert len(result.malformed_findings) == 4
    assert {diagnostic.code for diagnostic in result.errors} == {
        "duplicate_id",
        "unsafe_unescaped_pipe",
        "unbalanced_backticks",
        "column_count",
    }


def test_duplicate_ids_mark_every_occurrence_malformed() -> None:
    result = parse_ledger_file(FIXTURE)
    duplicates = _by_id("duplicate-fixture-id-2026-07-25", result.findings)

    assert len(duplicates) == 2
    assert all(finding.is_malformed for finding in duplicates)
    assert all(
        "duplicate_id" in {diagnostic.code for diagnostic in finding.parse_diagnostics}
        for finding in duplicates
    )


def test_escaped_and_balanced_code_span_pipes_stay_in_one_cell() -> None:
    result = parse_ledger_file(FIXTURE)
    finding = _by_id("safe-pipes-2026-07-24", result.findings)[0]

    assert not finding.is_malformed
    assert finding.claim_impact is not None
    assert "|delta|" in finding.claim_impact
    assert "`left | right`" in finding.claim_impact
    assert finding.kind == "instrument"


def test_compact_absolute_value_notation_is_a_documented_safe_pipe_pair() -> None:
    text = """
| ID | Status | Claim impact | Required response | Kind |
|---|---|---|---|---|
| math-bars-2026-07-30 | OPEN | The measured |Delta| is below MDE. | Keep open. | measurement |
"""
    result = parse_ledger(text, strict=True)

    assert result.findings[0].claim_impact == "The measured |Delta| is below MDE."


def test_unescaped_pipe_preserves_middle_instead_of_guessing_columns() -> None:
    result = parse_ledger_file(FIXTURE)
    finding = _by_id("unsafe-unescaped-pipe-2026-07-26", result.findings)[0]

    assert finding.status is None
    assert finding.claim_impact is None
    assert finding.required_response is None
    assert finding.kind == "instrument"
    assert finding.raw_middle is not None
    assert "alpha | beta" in finding.raw_middle
    assert "Owner: parser-team" in finding.raw_middle
    assert finding.status_classification is StatusClassification.MALFORMED


def test_unbalanced_backticks_do_not_invent_kind_or_middle_boundaries() -> None:
    result = parse_ledger_file(FIXTURE)
    finding = _by_id("unbalanced-backticks-2026-07-27", result.findings)[0]

    assert finding.kind is None
    assert finding.status is None
    assert finding.raw_middle is not None
    assert "`alpha | beta but never closes" in finding.raw_middle
    assert {diagnostic.code for diagnostic in finding.parse_diagnostics} == {
        "unbalanced_backticks",
        "column_count",
    }


def test_parser_extracts_conservative_metadata() -> None:
    result = parse_ledger_file(FIXTURE)
    normal = _by_id("cache-receipt-missing-2026-07-20", result.findings)[0]
    replacement = _by_id("cache-rule-v2-2026-07-22", result.findings)[0]
    resolved = _by_id("schema-check-resolved-2026-07-21", result.findings)[0]

    assert normal.owners == ["platform-team"]
    assert normal.recorded_on == date(2026, 7, 20)
    assert normal.created_at == datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
    assert [item.reference for item in normal.evidence_references] == [
        "https://example.org/evidence/cache-refresh.json"
    ]

    assert replacement.owners == ["platform-team", "governance-team"]
    assert replacement.supersedes_ids == ["stale-cache-rule-2026-07-18"]
    assert resolved.status_classification is StatusClassification.RESOLVED
    assert resolved.resolved_at == datetime(2026, 7, 21, tzinfo=UTC)
    assert resolved.updated_at == datetime(2026, 7, 21, 14, 5, tzinfo=UTC)


def test_open_status_is_not_flipped_by_resolved_substrings() -> None:
    row = (
        "| status-trap-2026-07-30 | OPEN — prior issue was resolved elsewhere "
        "| No closure here. | Keep open. | instrument |"
    )
    text = "\n".join(
        [
            "| ID | Status | Claim impact | Required response | Kind |",
            "|---|---|---|---|---|",
            row,
        ]
    )
    result = parse_ledger(text, strict=True)

    assert result.findings[0].status_classification is StatusClassification.OPEN


def test_strict_mode_reports_all_fixture_defects() -> None:
    with pytest.raises(LedgerParseError) as exc_info:
        parse_ledger_file(FIXTURE, strict=True)

    assert {diagnostic.code for diagnostic in exc_info.value.result.errors} == {
        "duplicate_id",
        "unsafe_unescaped_pipe",
        "unbalanced_backticks",
        "column_count",
    }


def test_unrelated_markdown_tables_are_ignored() -> None:
    text = """
| Name | Value |
|---|---|
| ignored | row |

| ID | Status | Claim impact | Required response | Kind |
|---|---|---|---|---|
| one-2026-07-30 | OPEN | Impact. | Response. | instrument |
"""
    result = parse_ledger(text, strict=True)

    assert [finding.id for finding in result.findings] == ["one-2026-07-30"]


def test_sophia_failure_id_header_alias_is_supported() -> None:
    text = """
| Failure ID | Status | Claim impact | Required response | Kind |
|---|---|---|---|---|
| alias-2026-07-30 | OPEN | Impact. | Response. | instrument |
"""
    result = parse_ledger(text, strict=True)

    assert [finding.id for finding in result.findings] == ["alias-2026-07-30"]


def test_missing_ledger_table_fails_loudly() -> None:
    result = parse_ledger("# no table")

    assert result.is_valid is False
    assert [diagnostic.code for diagnostic in result.errors] == ["table_not_found"]
    with pytest.raises(LedgerParseError):
        parse_ledger("# no table", strict=True)
