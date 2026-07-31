#!/usr/bin/env python3
"""Create a claim-safe descriptive summary of LedgerLens external evaluations."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "ledgerlens.external-evaluation.v1"
ROLES = frozenset({"data_engineer", "incident_responder", "other"})
CRITERIA = {
    "datahubUseAndWriteback": "Meaningful Use of DataHub Tools and Write-Back",
    "technicalExecution": "Technical Execution and End-to-End Functionality",
    "originalityBeyondBuiltins": "Originality and Extension Beyond Built-ins",
    "realWorldUsefulness": "Real-World Usefulness",
    "submissionQualityAndReproducibility": "Submission Quality and Reproducibility",
    "openSourceContribution": "Open-Source Contribution Bonus",
}
TASKS = {
    "openedDemo": "Opened the public demo",
    "ranReplay": "Ran the replay",
    "foundDataHubContext": "Found meaningful DataHub context",
    "distinguishedFixtureReceipts": "Distinguished fixture receipts from live evidence",
    "foundClaimBoundary": "Found the claim boundary or explicit unknowns",
    "foundNextAgentHandoff": "Found the next-agent handoff",
}


class EvaluationError(ValueError):
    """Raised when a review record cannot be safely aggregated."""


def _require_mapping(value: Any, *, field: str, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationError(f"line {line_number}: {field} must be an object")
    return value


def _require_bool(value: Any, *, field: str, line_number: int) -> bool:
    if not isinstance(value, bool):
        raise EvaluationError(f"line {line_number}: {field} must be a Boolean")
    return value


def _validate_record(record: Any, *, line_number: int) -> dict[str, Any]:
    payload = _require_mapping(record, field="record", line_number=line_number)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise EvaluationError(f"line {line_number}: schemaVersion must be {SCHEMA_VERSION!r}")

    review_id = payload.get("reviewId")
    if not isinstance(review_id, str) or not review_id.strip():
        raise EvaluationError(f"line {line_number}: reviewId must be a non-empty string")

    role = payload.get("role")
    if role not in ROLES:
        allowed = ", ".join(sorted(ROLES))
        raise EvaluationError(f"line {line_number}: role must be one of {allowed}")

    completed = _require_bool(
        payload.get("completed"),
        field="completed",
        line_number=line_number,
    )
    duration = payload.get("durationMinutes")
    if isinstance(duration, bool) or not isinstance(duration, int | float):
        raise EvaluationError(f"line {line_number}: durationMinutes must be a number")
    if not 0 <= float(duration) <= 60:
        raise EvaluationError(f"line {line_number}: durationMinutes must be between 0 and 60")

    consent = _require_mapping(
        payload.get("consent"),
        field="consent",
        line_number=line_number,
    )
    for field in ("publicAggregate", "publicAnonymizedComments", "publicAttribution"):
        _require_bool(
            consent.get(field),
            field=f"consent.{field}",
            line_number=line_number,
        )

    tasks = _require_mapping(payload.get("tasks"), field="tasks", line_number=line_number)
    for task in TASKS:
        _require_bool(
            tasks.get(task),
            field=f"tasks.{task}",
            line_number=line_number,
        )

    if completed:
        scores = _require_mapping(
            payload.get("scores"),
            field="scores",
            line_number=line_number,
        )
        for criterion in CRITERIA:
            score = scores.get(criterion)
            if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 4:
                raise EvaluationError(
                    f"line {line_number}: scores.{criterion} must be an integer from 0 to 4"
                )

    return payload


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load and validate JSONL review records."""
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        record = _validate_record(raw, line_number=line_number)
        review_id = str(record["reviewId"])
        if review_id in seen_ids:
            raise EvaluationError(f"line {line_number}: duplicate reviewId {review_id!r}")
        seen_ids.add(review_id)
        records.append(record)
    return records


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _median_and_range(values: list[float]) -> tuple[str, str]:
    median = _format_number(float(statistics.median(values)))
    value_range = f"{_format_number(min(values))}–{_format_number(max(values))}"
    return median, value_range


def _role_label(role: str) -> str:
    return role.replace("_", " ")


def render_summary(
    records: list[dict[str, Any]],
    *,
    scope: str,
    expected_reviewers: int,
) -> str:
    """Render an anonymous aggregate without reviewer IDs or comments."""
    if scope == "public":
        eligible = [
            record
            for record in records
            if record["completed"] and record["consent"]["publicAggregate"]
        ]
        title = "# LedgerLens External Evaluation Summary"
        scope_line = (
            "- Scope: public anonymous aggregate of completed, explicitly consented reviews."
        )
    else:
        eligible = [record for record in records if record["completed"]]
        title = "# LedgerLens External Evaluation Summary — INTERNAL"
        scope_line = (
            "- Scope: INTERNAL ONLY; includes completed reviews without regard to public consent."
        )

    lines = [
        title,
        "",
        scope_line,
        (
            "> Claim boundary: This is a descriptive, small-sample formative usability review. "
            "It is not independent validation, production evidence, a reliability estimate, "
            "validated uplift, or an official competition score."
        ),
        "",
    ]

    if not eligible:
        if scope == "public":
            lines.extend(
                [
                    "**No public aggregate is available.** No completed review with explicit "
                    "public-aggregate consent was found.",
                    "",
                    "Do not publish numeric results or infer endorsement from participation.",
                ]
            )
        else:
            lines.append("**No completed evaluation is available for internal aggregation.**")
        return "\n".join(lines) + "\n"

    count = len(eligible)
    roles = Counter(str(record["role"]) for record in eligible)
    role_text = "; ".join(f"{_role_label(role)}: {roles[role]}" for role in sorted(roles))
    durations = [float(record["durationMinutes"]) for record in eligible]
    duration_median, duration_range = _median_and_range(durations)
    reached = count >= expected_reviewers
    sample_status = "reached" if reached else "not reached"

    lines.extend(
        [
            f"- Completed evaluations in this scope: **{count}**",
            f"- Broad reviewer roles: {role_text}",
            f"- Duration in minutes: median **{duration_median}**, range **{duration_range}**",
            (
                f"- Planned reviewer target: **{expected_reviewers}**; target **{sample_status}**. "
                "Reaching the target does not make the sample representative."
            ),
            "",
            "## Task observations",
            "",
            "| Task | Completed |",
            "|---|---:|",
        ]
    )
    for task, label in TASKS.items():
        completed_count = sum(bool(record["tasks"][task]) for record in eligible)
        lines.append(f"| {label} | {completed_count}/{count} |")

    lines.extend(
        [
            "",
            "## Competition-aligned descriptive rubric",
            "",
            "| Criterion | n | Median (0–4) | Range |",
            "|---|---:|---:|---:|",
        ]
    )
    for criterion, label in CRITERIA.items():
        values = [float(record["scores"][criterion]) for record in eligible]
        median, value_range = _median_and_range(values)
        lines.append(f"| {label} | {count} | {median} | {value_range} |")

    totals = [
        float(sum(int(record["scores"][criterion]) for criterion in CRITERIA))
        for record in eligible
    ]
    total_median, total_range = _median_and_range(totals)
    lines.extend(
        [
            "",
            (
                f"**Overall descriptive total:** median **{total_median}/24**, "
                f"range **{total_range} / 24**."
            ),
            "",
            (
                "This total summarizes reviewer perception across six equally weighted criteria. "
                "It must not be presented as an official judge score or evidence of production "
                "performance."
            ),
            "",
            "Free-text comments, reviewer IDs, relationships, and attribution are intentionally "
            "omitted. Publish an exact comment only after separate excerpt-level consent.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Private JSONL evaluation file")
    parser.add_argument(
        "--scope",
        choices=("public", "internal"),
        default="public",
        help="Public consent-filtered output or private internal output",
    )
    parser.add_argument(
        "--expected-reviewers",
        type=int,
        default=2,
        help="Planned reviewer target used only for a sample-status note",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.expected_reviewers < 1:
        print("error: --expected-reviewers must be at least 1", file=sys.stderr)
        return 2
    try:
        records = load_records(args.input)
    except (OSError, EvaluationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        render_summary(
            records,
            scope=args.scope,
            expected_reviewers=args.expected_reviewers,
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
