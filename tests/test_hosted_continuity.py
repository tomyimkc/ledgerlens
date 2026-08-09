"""Pure tests for the short-window hosted continuity receipt."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_hosted_continuity.py"
SPEC = importlib.util.spec_from_file_location("check_hosted_continuity", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

START = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
END = datetime(2026, 8, 9, 12, 4, tzinfo=UTC)


def _sample(index: int) -> dict[str, object]:
    return {
        "schemaVersion": "ledgerlens.hosted-smoke.v1",
        "status": "PASS",
        "observedAtUtc": f"2026-08-09T12:0{index}:00+00:00",
        "checks": {
            "sealLabPlanDriftDecision": "denied",
            "contextCutFullMapDecision": "authorized",
            "contextCutOwnerRemovedDecision": "denied",
        },
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def test_continuity_receipt_requires_every_sample_to_pass() -> None:
    receipt = MODULE.build_continuity_receipt(
        [_sample(0), _sample(1), _sample(2)],
        started_at=START,
        completed_at=END,
        base_url="https://example.test",
        source_commit="abc123",
        workflow_run_url="https://github.test/run/1",
    )

    assert receipt["status"] == "PASS"
    assert receipt["sampleCount"] == 3
    assert receipt["passingSampleCount"] == 3
    assert receipt["checks"]["externalMutations"] is False
    assert receipt["checks"]["providerToolsExecuted"] is False
    assert receipt["candidateOnly"] is True
    assert receipt["canClaimAGI"] is False
    assert any("not an uptime SLO" in item for item in receipt["limitations"])


def test_continuity_receipt_fails_closed_without_hiding_failed_sample() -> None:
    failed = deepcopy(_sample(1))
    failed["status"] = "FAIL"
    failed["errors"] = ["owner-cut unexpectedly authorized"]
    receipt = MODULE.build_continuity_receipt(
        [_sample(0), failed],
        started_at=START,
        completed_at=END,
        base_url="https://example.test",
        source_commit=None,
        workflow_run_url=None,
    )

    assert receipt["status"] == "FAIL"
    assert receipt["passingSampleCount"] == 1
    assert receipt["checks"]["externalMutations"] is None
    assert receipt["samples"][1]["errors"] == ["owner-cut unexpectedly authorized"]
