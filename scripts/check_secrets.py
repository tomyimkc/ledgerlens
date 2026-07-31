#!/usr/bin/env python3
"""Offline high-confidence secret scan for the public repository."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "artifacts",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
}
ALLOW_MARKER = "pragma: allowlist secret"

PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "OpenAI-style key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "JWT": re.compile(rb"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    "assigned credential": re.compile(
        rb"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret|token)"
        rb"\s*[:=]\s*[\"']?([A-Za-z0-9+/=_-]{20,})[\"']?"
    ),
}


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", errors="surrogateescape")
        if any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file() and path.stat().st_size <= MAX_BYTES:
            paths.append(path)
    return sorted(paths)


def scan(path: Path) -> list[tuple[int, str]]:
    data = path.read_bytes()
    if b"\0" in data:
        return []
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(data.splitlines(), start=1):
        if ALLOW_MARKER.encode() in line:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append((line_number, label))
    return findings


def main() -> int:
    findings: list[str] = []
    for path in candidate_paths():
        for line_number, label in scan(path):
            relative = path.relative_to(ROOT)
            findings.append(f"{relative}:{line_number}: possible {label}")
    if findings:
        print("Secret scan failed:")
        print("\n".join(f"  {finding}" for finding in findings))
        print("Remove/rotate real credentials or annotate a test-only false positive.")
        return 1
    print(f"Secret scan passed ({len(candidate_paths())} public candidate files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
