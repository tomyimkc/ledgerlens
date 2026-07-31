"""Regression tests for the non-video competition readiness gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_non_video_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_non_video_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
check_receipt = MODULE.check_receipt
evaluate_repository = MODULE.evaluate_repository


def test_repository_satisfies_non_video_readiness_contract() -> None:
    errors, deferred = evaluate_repository(ROOT)
    assert errors == []
    assert any("video URL" in blocker for blocker in deferred)
    assert any("v0.2.1" in blocker for blocker in deferred)
    assert any("Slack, PagerDuty, and Jira" in blocker for blocker in deferred)


def test_receipt_check_fails_closed_on_claim_drift(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "PASS",
                "candidateOnly": False,
                "canClaimAGI": True,
                "externalValidation": True,
            }
        ),
        encoding="utf-8",
    )
    errors: list[str] = []
    check_receipt(
        tmp_path,
        "receipt.json",
        {("status",): "PASS"},
        errors,
    )
    assert errors == [
        "receipt.json: candidateOnly must be true",
        "receipt.json: canClaimAGI must be false",
        "receipt.json: externalValidation must be false when present",
    ]


def test_receipt_check_rejects_empty_object(tmp_path: Path) -> None:
    (tmp_path / "receipt.json").write_text("{}\n", encoding="utf-8")
    errors: list[str] = []
    check_receipt(
        tmp_path,
        "receipt.json",
        {("status",): "PASS"},
        errors,
    )
    assert errors == [
        "receipt.json: status must be 'PASS', found None",
        "receipt.json: candidateOnly must be true",
        "receipt.json: canClaimAGI must be false",
    ]
