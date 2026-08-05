#!/usr/bin/env python3
"""Independently reproduce the checks behind upstream DataHub MCP PR #160.

The open-source bonus evidence (E-11) links to Issue #159 and PR #160 in
``acryldata/mcp-server-datahub``. This script turns that link into a *checkable*
receipt: it clones the public fork branch at a pinned commit and runs the same
lint/type/test gates the PR claims pass, recording each result.

It proves nothing about acceptance. PR #160 is an OPEN contribution with no upstream
CI badge; this receipt records only that the pinned commit's own checks reproduce on a
fresh clone. It is deliberately NOT wired into ``make judge-check`` or CI because it
clones an external, mutable branch over the network.

Usage::

    uv run python scripts/reproduce_upstream_mcp_pr.py \
        --output benchmarks/upstream_mcp_contribution/pr-160-reproduction-receipt.json
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

FORK_URL = "https://github.com/tomyimkc/mcp-server-datahub.git"
BRANCH = "feat/get-entities-audit-context"
PINNED_COMMIT = "fe49bac7aac3f226ca680f88167e0bb48a7ba651"
UPSTREAM_REPO = "acryldata/mcp-server-datahub"
PR_NUMBER = 160
ISSUE_NUMBER = 159

# The two files PR #160 actually touches — scope the format check to these so the
# receipt is not polluted by the upstream repo's unrelated pre-existing formatting.
TOUCHED_SOURCE = "src/mcp_server_datahub/tools/entities.py"
TOUCHED_TEST = "tests/test_mcp/test_get_entities_audit_context.py"
PR_TESTS = ["tests/test_mcp/test_get_entities.py", TOUCHED_TEST]

SCHEMA_VERSION = "ledgerlens.upstream-pr-reproduction.v1"


def _run(
    command: list[str], *, cwd: Path | None = None, timeout: float = 900.0
) -> dict[str, object]:
    """Run one command and return a receipt step. Never raises on non-zero exit."""

    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        ok = proc.returncode == 0
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
        detail = tail[0][:200]
    except subprocess.TimeoutExpired:
        ok = False
        detail = f"timed out after {timeout:.0f}s"
    except FileNotFoundError as exc:
        ok = False
        detail = f"command not found: {exc}"
    return {
        "command": " ".join(command),
        "result": "OK" if ok else "FAILED",
        "detail": detail,
        "durationSeconds": round(time.monotonic() - started, 2),
        "ok": ok,
    }


def _uv_version() -> str:
    try:
        out = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=False, timeout=30
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - diagnostic only
        return "unknown"


def _verify_remote_head() -> dict[str, object]:
    """Fail closed if the fork branch HEAD no longer matches the pinned commit."""

    step = _run(["git", "ls-remote", FORK_URL, BRANCH], timeout=60)
    remote_head = ""
    try:
        out = subprocess.run(
            ["git", "ls-remote", FORK_URL, BRANCH],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        remote_head = out.stdout.split()[0] if out.stdout.split() else ""
    except Exception:  # noqa: BLE001
        remote_head = ""
    matches = remote_head == PINNED_COMMIT
    step["result"] = "OK" if matches else "FAILED"
    step["ok"] = matches
    step["detail"] = (
        f"branch HEAD {remote_head[:12]} matches pinned commit"
        if matches
        else f"branch HEAD {remote_head[:12]!r} != pinned {PINNED_COMMIT[:12]} (force-pushed?)"
    )
    return step


def reproduce(clone_dir: Path) -> list[dict[str, object]]:
    steps: list[dict[str, object]] = []

    head_check = _verify_remote_head()
    steps.append(head_check)
    if not head_check["ok"]:
        return steps

    steps.append(
        _run(
            ["git", "clone", "--branch", BRANCH, "--depth", "1", FORK_URL, str(clone_dir)],
            timeout=300,
        )
    )
    steps.append(_run(["git", "-C", str(clone_dir), "rev-parse", "HEAD"], timeout=30))
    # Confirm the cloned HEAD is exactly the pinned commit.
    head = subprocess.run(
        ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    steps[-1]["detail"] = head[:12]
    steps[-1]["ok"] = head == PINNED_COMMIT
    steps[-1]["result"] = "OK" if head == PINNED_COMMIT else "FAILED"
    if not steps[-1]["ok"]:
        return steps

    steps.append(_run(["uv", "sync", "--dev"], cwd=clone_dir, timeout=900))
    steps.append(_run(["uv", "run", "pytest", "-q", *PR_TESTS], cwd=clone_dir, timeout=600))
    steps.append(_run(["uv", "run", "ruff", "check"], cwd=clone_dir, timeout=180))
    steps.append(
        _run(
            ["uv", "run", "ruff", "format", "--check", TOUCHED_SOURCE, TOUCHED_TEST],
            cwd=clone_dir,
            timeout=120,
        )
    )
    steps.append(_run(["uv", "run", "mypy", TOUCHED_SOURCE], cwd=clone_dir, timeout=300))
    return steps


def build_receipt(steps: list[dict[str, object]]) -> dict[str, object]:
    status = "PASS" if steps and all(step["ok"] for step in steps) else "FAIL"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "upstream-mcp-pr-reproduction",
        "status": status,
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "performedAtUtc": datetime.now(UTC).isoformat(),
        "upstream": {
            "repo": UPSTREAM_REPO,
            "issue": ISSUE_NUMBER,
            "pullRequest": PR_NUMBER,
            "pullRequestState": "open",
            "fork": FORK_URL,
            "branch": BRANCH,
            "pinnedCommit": PINNED_COMMIT,
        },
        "environment": {
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "hostPython": platform.python_version(),
            "uv": _uv_version(),
        },
        "steps": [
            {k: step[k] for k in ("command", "result", "detail", "durationSeconds")}
            for step in steps
        ],
        "scope": (
            "Local reproduction of a public fork commit's own lint/type/test gates. This is "
            "NOT upstream CI, NOT maintainer review, and NOT a merge or acceptance claim. "
            "PR #160 remains open and unmerged."
        ),
        "limitations": [
            "Reproduces only the pinned commit's checks on a fresh clone at reproduction time.",
            "The fork branch is mutable; re-run to refresh if PR #160 is updated.",
            "No upstream maintainer has reviewed, approved, or merged the contribution.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/upstream_mcp_contribution/pr-160-reproduction-receipt.json"),
    )
    args = parser.parse_args()

    clone_parent = Path(tempfile.mkdtemp(prefix="ledgerlens-upstream-pr-"))
    clone_dir = clone_parent / "mcp-server-datahub"
    try:
        steps = reproduce(clone_dir)
    finally:
        shutil.rmtree(clone_parent, ignore_errors=True)

    receipt = build_receipt(steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for step in steps:
        print(f"  [{str(step['result']):>6}] {step['command']}  ({step['durationSeconds']}s)")
    print(f"\n{receipt['status']}: receipt written to {args.output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
