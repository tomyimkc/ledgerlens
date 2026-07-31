"""Conservative parser for Sophia-style Markdown failure-ledger tables."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from ledgerlens.models import (
    DiagnosticSeverity,
    EvidenceKind,
    EvidenceReference,
    Finding,
    LedgerParseError,
    LedgerParseResult,
    ParseDiagnostic,
    StatusClassification,
)

EXPECTED_COLUMNS = ("id", "status", "claim impact", "required response", "kind")

_ALIGNMENT_CELL_RE = re.compile(r"^:?-{3,}:?$")
_ABSOLUTE_VALUE_TOKEN_RE = re.compile(r"[A-Za-zΑ-ω][A-Za-z0-9_.+-]{0,23}")
_URL_RE = re.compile(r"https?://[^\s<>()`\]]+")
_OWNER_RE = re.compile(
    r"(?:^|[;(]\s*|\s)(?:owners?|responsible)\s*[:=]\s*([^;\n)]+)",
    flags=re.IGNORECASE,
)
_EVIDENCE_LABEL_RE = re.compile(
    r"\b(evidence|receipt|artifact)\s*[:=]\s*"
    r"(`[^`\n]+`|https?://[^\s;,)]+|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.@%+~#=-]+)+)",
    flags=re.IGNORECASE,
)
_SUPERSEDES_RE = re.compile(
    r"\bsupersedes?\b\s*[:=]?\s*"
    r"((?:`[A-Za-z0-9][A-Za-z0-9._:/-]*`|[A-Za-z0-9][A-Za-z0-9._:/-]*)"
    r"(?:\s*,\s*(?:`[A-Za-z0-9][A-Za-z0-9._:/-]*`|[A-Za-z0-9][A-Za-z0-9._:/-]*))*)",
    flags=re.IGNORECASE,
)
_METADATA_TIMESTAMP_RE = re.compile(
    r"\b(createdAt|created_at|created at|updatedAt|updated_at|updated at|"
    r"resolvedAt|resolved_at|resolved at)\s*[:=]\s*"
    r"(\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-]+Z?)?)",
    flags=re.IGNORECASE,
)
_ID_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})$")
_RESOLVED_DATE_RE = re.compile(
    r"^\s*(?:resolved|fixed|closed|completed?)\b[^0-9]*(\d{4}-\d{2}-\d{2})",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class _ScannedRow:
    body: str
    cells: tuple[str, ...]
    raw_cells: tuple[str, ...]
    divider_positions: tuple[int, ...]
    unbalanced_backticks: bool
    has_outer_delimiters: bool

    @property
    def raw_middle(self) -> str:
        if not self.divider_positions:
            return self.body.strip()
        first = self.divider_positions[0]
        if self.unbalanced_backticks or len(self.divider_positions) < 2:
            return self.body[first + 1 :].strip()
        last = self.divider_positions[-1]
        return self.body[first + 1 : last].strip()


def _strip_outer_delimiters(line: str) -> tuple[str, bool]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return stripped, False

    # Markdown tables in this corpus use both outer delimiters. A final escaped
    # pipe is content, not a delimiter, so leave it in place and mark the row.
    trailing_backslashes = 0
    index = len(stripped) - 2
    while index >= 0 and stripped[index] == "\\":
        trailing_backslashes += 1
        index -= 1
    has_trailing_delimiter = stripped.endswith("|") and trailing_backslashes % 2 == 0
    if has_trailing_delimiter:
        return stripped[1:-1], True
    return stripped[1:], False


def _scan_markdown_row(line: str) -> _ScannedRow:
    """Split only on pipes proven to be outside balanced code spans and escapes."""

    body, has_outer_delimiters = _strip_outer_delimiters(line)
    cells: list[str] = []
    raw_cells: list[str] = []
    divider_positions: list[int] = []
    value: list[str] = []
    cell_start = 0
    code_delimiter_length: int | None = None
    index = 0

    while index < len(body):
        char = body[index]

        if char == "\\":
            run_end = index
            while run_end < len(body) and body[run_end] == "\\":
                run_end += 1
            run_length = run_end - index
            next_char = body[run_end] if run_end < len(body) else None
            if next_char in {"|", "`"}:
                value.extend("\\" * (run_length // 2))
                if run_length % 2:
                    value.append(next_char)
                    index = run_end + 1
                    continue
                index = run_end
                continue
            value.extend("\\" * run_length)
            index = run_end
            continue

        if char == "`":
            run_end = index
            while run_end < len(body) and body[run_end] == "`":
                run_end += 1
            run_length = run_end - index
            value.append(body[index:run_end])
            if code_delimiter_length is None:
                code_delimiter_length = run_length
            elif code_delimiter_length == run_length:
                code_delimiter_length = None
            index = run_end
            continue

        if char == "|" and code_delimiter_length is None:
            closing_bar = body.find("|", index + 1)
            if closing_bar != -1 and _ABSOLUTE_VALUE_TOKEN_RE.fullmatch(
                body[index + 1 : closing_bar]
            ):
                value.append(body[index : closing_bar + 1])
                index = closing_bar + 1
                continue

            cells.append("".join(value).strip())
            raw_cells.append(body[cell_start:index])
            divider_positions.append(index)
            value = []
            index += 1
            cell_start = index
            continue

        value.append(char)
        index += 1

    cells.append("".join(value).strip())
    raw_cells.append(body[cell_start:])
    return _ScannedRow(
        body=body,
        cells=tuple(cells),
        raw_cells=tuple(raw_cells),
        divider_positions=tuple(divider_positions),
        unbalanced_backticks=code_delimiter_length is not None,
        has_outer_delimiters=has_outer_delimiters,
    )


def _normalize_header(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    compact = re.sub(r"[^a-z]", "", normalized)
    aliases = {
        "id": "id",
        "failureid": "id",
        "status": "status",
        "claimimpact": "claim impact",
        "requiredresponse": "required response",
        "kind": "kind",
    }
    return aliases.get(compact, normalized)


def _is_expected_header(row: _ScannedRow) -> bool:
    return (
        not row.unbalanced_backticks
        and len(row.cells) == len(EXPECTED_COLUMNS)
        and tuple(_normalize_header(cell) for cell in row.cells) == EXPECTED_COLUMNS
    )


def _is_alignment_row(row: _ScannedRow) -> bool:
    return len(row.cells) == len(EXPECTED_COLUMNS) and all(
        _ALIGNMENT_CELL_RE.fullmatch(cell.replace(" ", "")) for cell in row.cells
    )


def _optional_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _parse_iso_datetime(value: str) -> datetime | None:
    normalized = value.strip().replace(" ", "T")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        normalized = f"{normalized}T00:00:00+00:00"
    elif normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _extract_timestamps(
    finding_id: str, status: str | None, combined_text: str
) -> tuple[date | None, datetime | None, datetime | None, datetime | None]:
    id_date_match = _ID_DATE_RE.search(finding_id)
    recorded_on = date.fromisoformat(id_date_match.group(1)) if id_date_match else None

    timestamps: dict[str, datetime] = {}
    for match in _METADATA_TIMESTAMP_RE.finditer(combined_text):
        parsed = _parse_iso_datetime(match.group(2))
        if parsed is not None:
            key = match.group(1).casefold().replace("_", " ").replace(" ", "")
            timestamps[key] = parsed

    resolved_at = timestamps.get("resolvedat")
    if resolved_at is None and status:
        resolved_match = _RESOLVED_DATE_RE.search(status)
        if resolved_match:
            resolved_at = _parse_iso_datetime(resolved_match.group(1))

    return (
        recorded_on,
        timestamps.get("createdat"),
        timestamps.get("updatedat"),
        resolved_at,
    )


def _split_owner_values(value: str) -> Iterable[str]:
    for owner in re.split(r"\s*(?:,|&|\band\b)\s*", value):
        owner = owner.strip(" `[]")
        if not owner:
            continue
        # Parenthesized action lists such as "Owner: (1) check..." are not
        # identities and must not become DataHub owners.
        if re.match(r"^\(?\d+\)", owner):
            continue
        yield owner


def _extract_owners(combined_text: str) -> list[str]:
    owners: list[str] = []
    for match in _OWNER_RE.finditer(combined_text):
        owners.extend(_split_owner_values(match.group(1)))
    return list(dict.fromkeys(owners))


def _evidence_kind(reference: str) -> EvidenceKind:
    if reference.startswith(("http://", "https://")):
        return EvidenceKind.URL
    if "/" in reference:
        return EvidenceKind.PATH
    return EvidenceKind.IDENTIFIER


def _clean_reference(reference: str) -> str:
    return reference.strip().strip("`").rstrip(".,;)")


def _extract_evidence(combined_text: str) -> list[EvidenceReference]:
    references: list[EvidenceReference] = []

    for match in _URL_RE.finditer(combined_text):
        reference = _clean_reference(match.group(0))
        references.append(EvidenceReference(reference=reference, kind=EvidenceKind.URL))

    for match in _EVIDENCE_LABEL_RE.finditer(combined_text):
        reference = _clean_reference(match.group(2))
        references.append(
            EvidenceReference(
                reference=reference,
                kind=_evidence_kind(reference),
                label=match.group(1).casefold(),
            )
        )

    return list(
        {(reference.reference, reference.kind): reference for reference in references}.values()
    )


def _extract_supersedes(combined_text: str) -> list[str]:
    supersedes: list[str] = []
    for match in _SUPERSEDES_RE.finditer(combined_text):
        for value in match.group(1).split(","):
            cleaned = value.strip().strip("`")
            if cleaned:
                supersedes.append(cleaned)
    return list(dict.fromkeys(supersedes))


def _row_diagnostic(
    *,
    code: str,
    message: str,
    line_number: int,
    raw_segment: str,
) -> ParseDiagnostic:
    return ParseDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        line_number=line_number,
        raw_segment=raw_segment,
    )


def _finding_from_valid_row(
    row: _ScannedRow,
    *,
    line: str,
    line_number: int,
    source: str | None,
) -> Finding:
    finding_id, status, claim_impact, required_response, kind = row.cells
    combined_text = " ".join(value for value in (status, claim_impact, required_response) if value)
    recorded_on, created_at, updated_at, resolved_at = _extract_timestamps(
        finding_id, status, combined_text
    )
    return Finding(
        id=finding_id,
        status=_optional_text(status),
        claim_impact=_optional_text(claim_impact),
        required_response=_optional_text(required_response),
        kind=_optional_text(kind),
        owners=_extract_owners(combined_text),
        evidence_references=_extract_evidence(combined_text),
        supersedes_ids=_extract_supersedes(combined_text),
        recorded_on=recorded_on,
        created_at=created_at,
        updated_at=updated_at,
        resolved_at=resolved_at,
        source=source,
        source_line=line_number,
        raw_row=line,
    )


def _finding_from_malformed_row(
    row: _ScannedRow,
    *,
    line: str,
    line_number: int,
    source: str | None,
    diagnostic: ParseDiagnostic,
) -> Finding:
    safe_id = row.cells[0].strip() if row.cells and row.cells[0].strip() else None
    if safe_id is None or "|" in safe_id or "\n" in safe_id:
        safe_id = f"malformed-row-{line_number}"

    # With balanced backticks and too many cells, the last outside-code cell is
    # still a provably safe Kind boundary. With unbalanced backticks it is not.
    safe_kind = (
        _optional_text(row.cells[-1])
        if not row.unbalanced_backticks and len(row.cells) > len(EXPECTED_COLUMNS)
        else None
    )
    return Finding(
        id=safe_id,
        status=None,
        status_classification=StatusClassification.MALFORMED,
        claim_impact=None,
        required_response=None,
        kind=safe_kind,
        source=source,
        source_line=line_number,
        raw_row=line,
        raw_middle=row.raw_middle,
        parse_diagnostics=[diagnostic],
    )


def _parse_data_row(
    line: str, *, line_number: int, source: str | None
) -> tuple[Finding, list[ParseDiagnostic]]:
    row = _scan_markdown_row(line)
    diagnostics: list[ParseDiagnostic] = []

    if not row.has_outer_delimiters:
        diagnostics.append(
            _row_diagnostic(
                code="missing_outer_delimiter",
                message="ledger row must start and end with an unescaped pipe delimiter",
                line_number=line_number,
                raw_segment=line,
            )
        )
    if row.unbalanced_backticks:
        diagnostics.append(
            _row_diagnostic(
                code="unbalanced_backticks",
                message="ledger row contains an unclosed Markdown code span",
                line_number=line_number,
                raw_segment=line,
            )
        )
    if len(row.cells) > len(EXPECTED_COLUMNS):
        diagnostics.append(
            _row_diagnostic(
                code="unsafe_unescaped_pipe",
                message=(
                    f"ledger row has {len(row.cells)} cells; expected "
                    f"{len(EXPECTED_COLUMNS)}. Ambiguous middle text was not assigned."
                ),
                line_number=line_number,
                raw_segment=row.raw_middle,
            )
        )
    elif len(row.cells) < len(EXPECTED_COLUMNS):
        diagnostics.append(
            _row_diagnostic(
                code="column_count",
                message=(
                    f"ledger row has {len(row.cells)} cells; expected {len(EXPECTED_COLUMNS)}"
                ),
                line_number=line_number,
                raw_segment=row.raw_middle,
            )
        )

    if diagnostics:
        # One finding carries every row diagnostic, while the first diagnostic
        # supplies the conservative malformed-row construction.
        finding = _finding_from_malformed_row(
            row,
            line=line,
            line_number=line_number,
            source=source,
            diagnostic=diagnostics[0],
        )
        if len(diagnostics) > 1:
            finding.parse_diagnostics.extend(diagnostics[1:])
        return finding, diagnostics

    try:
        finding = _finding_from_valid_row(row, line=line, line_number=line_number, source=source)
    except ValueError as error:
        diagnostic = _row_diagnostic(
            code="invalid_finding",
            message=str(error),
            line_number=line_number,
            raw_segment=line,
        )
        finding = _finding_from_malformed_row(
            row,
            line=line,
            line_number=line_number,
            source=source,
            diagnostic=diagnostic,
        )
        diagnostics.append(diagnostic)
    return finding, diagnostics


def _mark_duplicate_ids(
    findings: list[Finding], diagnostics: list[ParseDiagnostic]
) -> list[Finding]:
    positions: dict[str, list[int]] = {}
    for index, finding in enumerate(findings):
        positions.setdefault(finding.id, []).append(index)

    result = list(findings)
    for finding_id, indexes in positions.items():
        if len(indexes) < 2:
            continue
        line_numbers = [findings[index].source_line for index in indexes]
        for index in indexes:
            finding = result[index]
            diagnostic = ParseDiagnostic(
                code="duplicate_id",
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"finding id {finding_id!r} occurs {len(indexes)} times at lines {line_numbers}"
                ),
                line_number=finding.source_line,
                raw_segment=finding.raw_row,
            )
            diagnostics.append(diagnostic)
            result[index] = finding.model_copy(
                update={
                    "status_classification": StatusClassification.MALFORMED,
                    "parse_diagnostics": [*finding.parse_diagnostics, diagnostic],
                }
            )
    return result


def parse_ledger(
    text: str,
    *,
    source: str | None = None,
    strict: bool = False,
) -> LedgerParseResult:
    """Parse every matching Sophia-style failure-ledger table in ``text``.

    Non-strict mode returns malformed findings with diagnostics. Strict mode
    raises :class:`LedgerParseError` after parsing the complete ledger, so the
    caller receives all detected defects rather than only the first one.
    """

    findings: list[Finding] = []
    diagnostics: list[ParseDiagnostic] = []
    in_ledger_table = False
    saw_header = False
    awaiting_alignment = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        if stripped.startswith("|"):
            scanned = _scan_markdown_row(line)
            if _is_expected_header(scanned):
                saw_header = True
                in_ledger_table = True
                awaiting_alignment = True
                continue

            if in_ledger_table and awaiting_alignment and _is_alignment_row(scanned):
                awaiting_alignment = False
                continue

            if in_ledger_table:
                awaiting_alignment = False
                finding, row_diagnostics = _parse_data_row(
                    line, line_number=line_number, source=source
                )
                findings.append(finding)
                diagnostics.extend(row_diagnostics)
                continue

        if in_ledger_table and stripped:
            in_ledger_table = False
            awaiting_alignment = False

    if not saw_header:
        diagnostics.append(
            ParseDiagnostic(
                code="table_not_found",
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "no Markdown table with columns "
                    "ID/Status/Claim impact/Required response/Kind was found"
                ),
            )
        )

    findings = _mark_duplicate_ids(findings, diagnostics)
    result = LedgerParseResult(
        source=source,
        findings=findings,
        diagnostics=diagnostics,
    )
    if strict and not result.is_valid:
        raise LedgerParseError(result)
    return result


def parse_ledger_file(
    path: str | Path,
    *,
    strict: bool = False,
    encoding: str = "utf-8",
) -> LedgerParseResult:
    """Parse a failure-ledger file and retain its path as source provenance."""

    source_path = Path(path)
    return parse_ledger(
        source_path.read_text(encoding=encoding),
        source=str(source_path),
        strict=strict,
    )


# Explicit aliases make the public purpose clear for callers and demos.
parse_failure_ledger = parse_ledger
parse_failure_ledger_file = parse_ledger_file
