"""Tests for consent-filtered external-evaluation summaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/summarize_external_evaluations.py"
CRITERIA = (
    "datahubUseAndWriteback",
    "technicalExecution",
    "originalityBeyondBuiltins",
    "realWorldUsefulness",
    "submissionQualityAndReproducibility",
    "openSourceContribution",
)
TASKS = (
    "openedDemo",
    "ranReplay",
    "foundDataHubContext",
    "distinguishedFixtureReceipts",
    "foundClaimBoundary",
    "foundNextAgentHandoff",
)


def _record(
    review_id: str,
    *,
    role: str,
    score: int,
    public_aggregate: bool,
    completed: bool = True,
) -> dict[str, Any]:
    return {
        "schemaVersion": "ledgerlens.external-evaluation.v1",
        "reviewId": review_id,
        "role": role,
        "completed": completed,
        "durationMinutes": 8 if role == "data_engineer" else 9,
        "relationshipToProject": "none_disclosed",
        "consent": {
            "publicAggregate": public_aggregate,
            "publicAnonymizedComments": False,
            "publicAttribution": False,
        },
        "tasks": {task: True for task in TASKS},
        "scores": {criterion: score for criterion in CRITERIA},
        "comments": {
            "mostUseful": "private observation",
            "approvedPublicExcerpt": "",
        },
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record)}\n" for record in records),
        encoding="utf-8",
    )


def _run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_public_summary_uses_only_completed_consenting_reviews(tmp_path: Path) -> None:
    input_path = tmp_path / "reviews.jsonl"
    incomplete = _record(
        "reviewer-incomplete",
        role="other",
        score=0,
        public_aggregate=True,
        completed=False,
    )
    incomplete.pop("scores")
    _write_jsonl(
        input_path,
        [
            _record(
                "reviewer-data",
                role="data_engineer",
                score=4,
                public_aggregate=True,
            ),
            _record(
                "reviewer-incident",
                role="incident_responder",
                score=2,
                public_aggregate=True,
            ),
            _record(
                "reviewer-private",
                role="other",
                score=0,
                public_aggregate=False,
            ),
            incomplete,
        ],
    )

    result = _run(input_path)

    assert result.returncode == 0
    assert "Completed evaluations in this scope: **2**" in result.stdout
    assert "data engineer: 1; incident responder: 1" in result.stdout
    assert "| Meaningful Use of DataHub Tools and Write-Back | 2 | 3 | 2–4 |" in result.stdout
    assert "median **18/24**, range **12–24 / 24**" in result.stdout
    assert "reviewer-data" not in result.stdout
    assert "private observation" not in result.stdout
    assert "other: 1" not in result.stdout


def test_internal_scope_is_prominently_marked_and_includes_private_reviews(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "reviews.jsonl"
    _write_jsonl(
        input_path,
        [
            _record(
                "reviewer-public",
                role="data_engineer",
                score=4,
                public_aggregate=True,
            ),
            _record(
                "reviewer-private",
                role="incident_responder",
                score=0,
                public_aggregate=False,
            ),
        ],
    )

    result = _run(input_path, "--scope", "internal")

    assert result.returncode == 0
    assert "INTERNAL" in result.stdout
    assert "without regard to public consent" in result.stdout
    assert "| Technical Execution and End-to-End Functionality | 2 | 2 | 0–4 |" in result.stdout


def test_public_summary_with_no_eligible_records_publishes_no_scores(tmp_path: Path) -> None:
    input_path = tmp_path / "reviews.jsonl"
    _write_jsonl(
        input_path,
        [
            _record(
                "reviewer-private",
                role="data_engineer",
                score=4,
                public_aggregate=False,
            )
        ],
    )

    result = _run(input_path)

    assert result.returncode == 0
    assert "No public aggregate is available" in result.stdout
    assert "24" not in result.stdout
    assert "infer endorsement" in result.stdout


def test_invalid_score_fails_closed_with_line_context(tmp_path: Path) -> None:
    input_path = tmp_path / "reviews.jsonl"
    record = _record(
        "reviewer-invalid",
        role="data_engineer",
        score=3,
        public_aggregate=True,
    )
    record["scores"]["technicalExecution"] = 5
    _write_jsonl(input_path, [record])

    result = _run(input_path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "line 1" in result.stderr
    assert "scores.technicalExecution must be an integer from 0 to 4" in result.stderr


def test_duplicate_review_ids_fail_instead_of_double_counting(tmp_path: Path) -> None:
    input_path = tmp_path / "reviews.jsonl"
    record = _record(
        "reviewer-duplicate",
        role="data_engineer",
        score=3,
        public_aggregate=True,
    )
    _write_jsonl(input_path, [record, record])

    result = _run(input_path)

    assert result.returncode == 2
    assert "duplicate reviewId" in result.stderr
