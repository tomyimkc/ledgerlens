"""Benchmark receipt integrity tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_receipt_does_not_self_hash(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_benchmark.py"),
            "--kind",
            "deterministic-fixture",
            "--output",
            str(output),
            "--",
            sys.executable,
            "-c",
            "print('benchmark-ok')",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["artifacts"] == []
    assert payload["checks"][1] == {
        "name": "liveModeSelected",
        "status": "NOT_APPLICABLE",
        "value": False,
    }
