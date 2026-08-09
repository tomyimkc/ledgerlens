#!/usr/bin/env python3
"""Collect a short-window, repeated sample of the public hosted contract.

This wraps ``check_hosted_incident_demo.py`` several times and writes one sanitized
aggregate receipt. It deliberately does not call provider tools or claim an uptime SLO.
The purpose is narrower: replace a single screenshot/check with a repeatable, time-separated
sample over the deployed fixture, Seal Lab, and DataHub Context Cut.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts/check_hosted_incident_demo.py"
DEFAULT_BASE_URL = "https://tomyimkc-ledgerlens-incident-commander.hf.space"


def _now() -> datetime:
    return datetime.now(UTC)


def build_continuity_receipt(
    samples: list[dict[str, Any]],
    *,
    started_at: datetime,
    completed_at: datetime,
    base_url: str,
    source_commit: str | None,
    workflow_run_url: str | None,
) -> dict[str, Any]:
    """Build a fail-closed aggregate from already-sanitized smoke receipts."""

    pass_count = sum(sample.get("status") == "PASS" for sample in samples)
    all_passed = bool(samples) and pass_count == len(samples)
    observed = [sample.get("observedAtUtc") for sample in samples]
    return {
        "schemaVersion": "ledgerlens.hosted-continuity.v1",
        "status": "PASS" if all_passed else "FAIL",
        "baseUrl": base_url,
        "sourceCommit": source_commit,
        "workflowRunUrl": workflow_run_url,
        "startedAtUtc": started_at.isoformat(),
        "completedAtUtc": completed_at.isoformat(),
        "sampleCount": len(samples),
        "passingSampleCount": pass_count,
        "allSamplesPassed": all_passed,
        "observedAtUtc": observed,
        "samples": samples,
        "checks": {
            "fixtureContractRepeated": all_passed,
            "sealLabPlanDriftDeniedEverySample": all(
                (sample.get("checks") or {}).get("sealLabPlanDriftDecision") == "denied"
                for sample in samples
            ),
            "contextCutFullMapAuthorizedEverySample": all(
                (sample.get("checks") or {}).get("contextCutFullMapDecision") == "authorized"
                for sample in samples
            ),
            "contextCutOwnerRemovedDeniedEverySample": all(
                (sample.get("checks") or {}).get("contextCutOwnerRemovedDecision") == "denied"
                for sample in samples
            ),
            "externalMutations": False if all_passed else None,
            "providerToolsExecuted": False if all_passed else None,
        },
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "limitations": [
            "This is a short-window repeated sample, not an uptime SLO or reliability study.",
            "It checks a public deterministic fixture and policy labs, "
            "not live provider execution.",
            "Passing samples do not establish production readiness or independent validation.",
        ],
    }


def collect_samples(
    *,
    samples: int,
    interval_seconds: float,
    base_url: str,
    timeout: float,
    attempts: int,
    retry_delay: float,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Run the existing smoke checker repeatedly and retain sanitized receipts."""

    collected: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ledgerlens-hosted-continuity-") as tmp:
        directory = Path(tmp)
        for index in range(samples):
            output = directory / f"sample-{index + 1}.json"
            completed = runner(
                [
                    sys.executable,
                    str(SMOKE),
                    "--base-url",
                    base_url,
                    "--output",
                    str(output),
                    "--timeout",
                    str(timeout),
                    "--attempts",
                    str(attempts),
                    "--retry-delay",
                    str(retry_delay),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if output.exists():
                receipt = json.loads(output.read_text(encoding="utf-8"))
            else:
                receipt = {
                    "schemaVersion": "ledgerlens.hosted-smoke.v1",
                    "status": "FAIL",
                    "observedAtUtc": _now().isoformat(),
                    "baseUrl": base_url,
                    "checks": {},
                    "candidateOnly": True,
                    "canClaimAGI": False,
                    "errors": ["smoke checker did not write a receipt"],
                    "limitations": [],
                }
            receipt["sampleOrdinal"] = index + 1
            receipt["smokeExitCode"] = completed.returncode
            collected.append(receipt)
            print(
                f"sample {index + 1}/{samples}: {receipt.get('status', 'UNKNOWN')}",
                flush=True,
            )
            if index + 1 < samples and interval_seconds:
                sleeper(interval_seconds)
    return collected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=45.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 2 <= args.samples <= 12:
        print("--samples must be between 2 and 12", file=sys.stderr)
        return 2
    if not 0 <= args.interval_seconds <= 600:
        print("--interval-seconds must be between 0 and 600", file=sys.stderr)
        return 2

    started_at = _now()
    samples = collect_samples(
        samples=args.samples,
        interval_seconds=args.interval_seconds,
        base_url=args.base_url,
        timeout=args.timeout,
        attempts=args.attempts,
        retry_delay=args.retry_delay,
    )
    completed_at = _now()
    server_url = os.getenv("GITHUB_SERVER_URL")
    repository = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    workflow_run_url = (
        f"{server_url}/{repository}/actions/runs/{run_id}"
        if server_url and repository and run_id
        else None
    )
    receipt = build_continuity_receipt(
        samples,
        started_at=started_at,
        completed_at=completed_at,
        base_url=args.base_url,
        source_commit=os.getenv("GITHUB_SHA"),
        workflow_run_url=workflow_run_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"hosted continuity: {receipt['status']} "
        f"({receipt['passingSampleCount']}/{receipt['sampleCount']} samples)"
    )
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
