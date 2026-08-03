"""Tests for the submission consistency checker.

Confirms the repo currently passes, and — critically — that the checker actually *catches*
each class of drift it exists to prevent (a checker that can never fail is worthless).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_submission_consistency as checker  # noqa: E402


def _repo_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        dest,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "artifacts", "build", "dist", "node_modules"
        ),
    )
    return dest


def test_repository_is_consistent() -> None:
    assert checker.evaluate(ROOT) == []


def test_catches_e16_date_drift(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    index = repo / "docs/EVIDENCE_INDEX.md"
    text = index.read_text(encoding="utf-8")
    # The real produced date is 2026-08-03; inject a wrong one.
    assert "Produced 2026-08-03" in text
    index.write_text(text.replace("Produced 2026-08-03", "Produced 2026-08-09"), encoding="utf-8")
    errors = checker.evaluate(repo)
    assert any("disagrees with the E-16 receipt date" in e for e in errors)


def test_catches_benchmark_count_drift(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    ledger = repo / "docs/SUBMISSION_LEDGER.md"
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text + "\n\nThe catalog has 150-asset coverage.\n", encoding="utf-8")
    errors = checker.evaluate(repo)
    assert any("150 assets" in e for e in errors)


def test_catches_score_disagreement(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    ledger = repo / "docs/SUBMISSION_LEDGER.md"
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text + "\n\nFive-core average **9.9 / 10**.\n", encoding="utf-8")
    errors = checker.evaluate(repo)
    assert any("five-core average disagrees" in e for e in errors)
