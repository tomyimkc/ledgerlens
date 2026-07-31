#!/usr/bin/env python3
"""Run a command and write a claim-bounded benchmark receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def public_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), "", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind",
        required=True,
        choices=("deterministic-fixture", "live-datahub-smoke"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--datahub-version", default=os.getenv("DATAHUB_VERSION"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    started_at = utc_now()
    started = time.monotonic()
    result = subprocess.run(
        args.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=dict(os.environ),
    )
    duration = time.monotonic() - started
    finished_at = utc_now()

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    dirty_output = git_value("status", "--porcelain")
    live = args.kind == "live-datahub-smoke"
    limitations = [
        "LedgerLens is a working prototype, not independent validation.",
        "This receipt cannot establish AGI, validated uplift, or source-finding truth.",
    ]
    if live:
        limitations.extend(
            [
                "A smoke pass establishes compatibility with the recorded deployment only.",
                "DataHub ingestion timestamps are not finding-validation timestamps.",
            ]
        )
    else:
        limitations.extend(
            [
                "DataHub was not contacted.",
                "Fixture checks do not establish live DataHub compatibility.",
            ]
        )

    stdout_digest = hashlib.sha256(result.stdout.encode()).hexdigest()
    stderr_digest = hashlib.sha256(result.stderr.encode()).hexdigest()
    receipt: dict[str, Any] = {
        "schemaVersion": "1.0",
        "benchmarkKind": args.kind,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "liveDataHub": live,
        "llmEnabled": os.getenv("LEDGERLENS_LLM_ENABLED", "false").lower() == "true",
        "startedAtUtc": started_at,
        "finishedAtUtc": finished_at,
        "durationSeconds": round(duration, 6),
        "gitCommit": git_value("rev-parse", "HEAD"),
        "gitDirty": bool(dirty_output),
        "command": args.command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "datahubOssVersion": args.datahub_version if live else None,
            "datahubCliVersion": package_version("acryl-datahub") if live else None,
            "mcpPackageVersion": package_version("mcp-server-datahub") if live else None,
            "mcpTransport": (
                "http" if live and os.getenv("DATAHUB_MCP_URL") else "stdio" if live else None
            ),
            "gmsUrl": public_url(os.getenv("DATAHUB_GMS_URL")) if live else None,
            "frontendUrl": public_url(os.getenv("DATAHUB_FRONTEND_URL")) if live else None,
        },
        "checks": [
            {
                "name": "commandExitZero",
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "exitCode": result.returncode,
            },
            {
                "name": "liveModeSelected",
                "status": "PASS" if live else "NOT_APPLICABLE",
                "value": live,
            },
        ],
        "capturedOutput": {
            "stdoutSha256": stdout_digest,
            "stderrSha256": stderr_digest,
            "stdoutBytes": len(result.stdout.encode()),
            "stderrBytes": len(result.stderr.encode()),
        },
        "artifacts": [],
        "limitations": limitations,
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote benchmark receipt: {output}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
