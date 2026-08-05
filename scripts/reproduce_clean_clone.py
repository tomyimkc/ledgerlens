#!/usr/bin/env python3
"""Regenerate the clean-clone reproduction receipt (E-17) with one command.

The committed receipt under ``benchmarks/results/`` was originally hand-authored. This
script makes it reproducible: it shallow-clones the public repository into a temporary
directory, runs only the documented ``make setup`` and ``make judge-check`` commands, and
writes a dated receipt recording the cloned commit, the environment, and per-step timing.

It clones and executes the project's own published code from a clean checkout — which is
exactly what a judge reproducing the submission does — so it is a deliberate, explicit
action and is not wired into CI.

Usage::

    uv run python scripts/reproduce_clean_clone.py \
        --output benchmarks/results/clean-clone-latest.json
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_URL = "https://github.com/tomyimkc/ledgerlens.git"
SCHEMA_VERSION = "ledgerlens.clean-clone-reproduction.v1"


def _run(command: list[str], *, cwd: Path, timeout: float) -> dict[str, object]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
        ok = proc.returncode == 0
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        ok, output = False, f"timed out after {timeout:.0f}s"
    return {
        "command": " ".join(command),
        "result": "OK" if ok else "FAILED",
        "durationSeconds": round(time.monotonic() - started, 2),
        "ok": ok,
        "_output": output,
    }


def _uv_version() -> str:
    out = subprocess.run(["uv", "--version"], capture_output=True, text=True, check=False)
    return out.stdout.strip() or "unknown"


def _cloned_commit(clone_dir: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def _largest_passed(output: str) -> int | None:
    counts = [int(match) for match in re.findall(r"(\d+) passed", output)]
    return max(counts) if counts else None


def reproduce(clone_dir: Path) -> tuple[list[dict[str, object]], str]:
    steps: list[dict[str, object]] = [
        _run(
            ["git", "clone", "--depth", "1", REPO_URL, str(clone_dir)], cwd=Path.cwd(), timeout=300
        )
    ]
    if not steps[-1]["ok"]:
        return steps, ""
    commit = _cloned_commit(clone_dir)
    steps.append(_run(["make", "setup"], cwd=clone_dir, timeout=900))
    if steps[-1]["ok"]:
        steps.append(_run(["make", "judge-check"], cwd=clone_dir, timeout=1800))
    return steps, commit


def build_receipt(steps: list[dict[str, object]], commit: str) -> dict[str, object]:
    status = "PASS" if steps and all(step["ok"] for step in steps) else "FAIL"
    judge = next((s for s in steps if s["command"] == "make judge-check"), None)
    deterministic_tests = _largest_passed(str(judge["_output"])) if judge else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "clean-clone-reproduction",
        "status": status,
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "performedAtUtc": datetime.now(UTC).isoformat(),
        "commit": commit,
        "method": (
            "Fresh shallow git clone of the public repository, then only the documented commands."
        ),
        "environment": {
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "hostPython": platform.python_version(),
            "uv": _uv_version(),
        },
        "steps": [{k: step[k] for k in ("command", "result", "durationSeconds")} for step in steps],
        "observed": {"deterministicTests": deterministic_tests},
        "requiredNoUndeclaredInputs": True,
        "requiredNoCredentials": True,
        "limitations": [
            "Reproduces the deterministic offline gates only; it does not exercise live "
            "DataHub, live providers, or the hosted Space.",
            "A pass validates that the published commands work from a clean clone; it does "
            "not establish production readiness or independent validation.",
            "Timing is local wall-clock on one machine and is diagnostic, not a performance claim.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/clean-clone-latest.json")
    )
    args = parser.parse_args()

    parent = Path(tempfile.mkdtemp(prefix="ledgerlens-clean-clone-"))
    clone_dir = parent / "ledgerlens"
    try:
        steps, commit = reproduce(clone_dir)
    finally:
        shutil.rmtree(parent, ignore_errors=True)

    receipt = build_receipt(steps, commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for step in steps:
        print(f"  [{str(step['result']):>6}] {step['command']}  ({step['durationSeconds']}s)")
    print(f"\n{receipt['status']} @ {commit[:8]}: receipt written to {args.output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
