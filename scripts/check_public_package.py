#!/usr/bin/env python3
"""Validate LedgerLens's public contest package without external services."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "ARCHITECTURE.md",
    "DISCLOSURE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "Makefile",
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/hosted-smoke.yml",
    "scripts/check_hosted_incident_demo.py",
    "scripts/check_non_video_readiness.py",
    "docs/EVIDENCE_INDEX.md",
    "docs/WINNER_READINESS.md",
    "docs/BENCHMARKS.md",
    "docs/DATAHUB_QUICKSTART.md",
    "docs/DEVPOST_CHECKLIST.md",
    "docs/DEVPOST_SUBMISSION.md",
    "docs/DEVPOST_WRITEUP.md",
    "docs/EXTERNAL_EVALUATION.md",
    "docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md",
    "docs/LIVE_DATAHUB_PUBLIC.md",
    "docs/demo/DEMO_SCRIPT.md",
    "docs/demo/STORYBOARD.md",
    "docs/demo/RECORDING.md",
    "docs/fixtures/failure-ledger-demo.md",
    "docs/fixtures/failure-ledger-malformed.md",
    "docs/results/deterministic-fixture-template.json",
    "docs/results/live-datahub-smoke-template.json",
)

CLAIM_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "DISCLOSURE.md",
    "docs/DEVPOST_WRITEUP.md",
    "docs/BENCHMARKS.md",
)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_json_templates(errors: list[str]) -> None:
    expected = {
        "deterministic-fixture-template.json": ("deterministic-fixture", False),
        "live-datahub-smoke-template.json": ("live-datahub-smoke", True),
    }
    result_root = ROOT / "docs/results"
    for name, (kind, live) in expected.items():
        payload = json.loads((result_root / name).read_text(encoding="utf-8"))
        require(payload.get("benchmarkKind") == kind, f"{name}: wrong kind", errors)
        require(payload.get("status") == "NOT_RUN", f"{name}: template must be NOT_RUN", errors)
        require(payload.get("liveDataHub") is live, f"{name}: wrong liveDataHub", errors)
        require(payload.get("candidateOnly") is True, f"{name}: candidateOnly must be true", errors)
        require(payload.get("canClaimAGI") is False, f"{name}: canClaimAGI must be false", errors)
        require(
            payload.get("externalValidation") is False,
            f"{name}: externalValidation must be false",
            errors,
        )


def check_shell(errors: list[str]) -> None:
    scripts = sorted((ROOT / "scripts").rglob("*.sh"))
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        if result.returncode:
            errors.append(f"{script.relative_to(ROOT)}: bash -n failed: {result.stderr.strip()}")


def _read_required_text(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        errors.append(f"{relative}: unable to read required file: {error}")
        return ""


def _has_six_core_rubric_drift(text: str) -> bool:
    return "six equally weighted" in text.casefold() or bool(
        re.search(r"(?im)^.*(?:total|score|criteria).*?(?:\d{1,2}|_+)\s*/\s*24\b.*$", text)
    )


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        require((ROOT / relative).is_file(), f"missing required file: {relative}", errors)

    for relative in CLAIM_FILES:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        require(
            "candidateOnly" in text and "true" in text,
            f"{relative}: candidateOnly missing",
            errors,
        )
        require(
            "canClaimAGI" in text and "false" in text,
            f"{relative}: canClaimAGI missing",
            errors,
        )
        require(
            "working prototype" in text.casefold(),
            f"{relative}: working-prototype framing missing",
            errors,
        )
        require(
            "independent validation" in text.casefold(),
            f"{relative}: independent-validation boundary missing",
            errors,
        )

    readme = _read_required_text("README.md", errors)
    require("Apache License 2.0" in readme, "README: Apache-2.0 disclosure missing", errors)
    require("Agents That Do Real Work" in readme, "README: category missing", errors)
    require("make demo" in readme, "README: deterministic demo command missing", errors)
    require("docs/EVIDENCE_INDEX.md" in readme, "README: evidence index link missing", errors)
    require("docs/WINNER_READINESS.md" in readme, "README: winner-readiness link missing", errors)

    submission = _read_required_text("docs/DEVPOST_SUBMISSION.md", errors)
    require(
        "EVIDENCE_INDEX.md" in submission, "Devpost submission: evidence index link missing", errors
    )
    require(
        "docs/WINNER_READINESS.md" in submission,
        "Devpost submission: winner-readiness link missing",
        errors,
    )

    for relative, text in (
        ("README.md", readme),
        ("docs/DEVPOST_SUBMISSION.md", submission),
        ("docs/EXTERNAL_EVALUATION.md", _read_required_text("docs/EXTERNAL_EVALUATION.md", errors)),
        (
            "docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md",
            _read_required_text("docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md", errors),
        ),
        ("docs/WINNER_READINESS.md", _read_required_text("docs/WINNER_READINESS.md", errors)),
    ):
        folded = text.casefold()
        require(
            "five core" in folded or "five-core" in folded,
            f"{relative}: five-core rubric framing missing",
            errors,
        )
        require("bonus" in folded, f"{relative}: bonus framing missing", errors)
        require(
            "six equally weighted" not in folded and not _has_six_core_rubric_drift(text),
            f"{relative}: public rubric must use five core criteria plus separate bonus",
            errors,
        )

    disclosure = (ROOT / "DISCLOSURE.md").read_text(encoding="utf-8").casefold()
    require("sophia-agi" in disclosure, "DISCLOSURE: Sophia-AGI not named", errors)
    require("newly built" in disclosure, "DISCLOSURE: contest-period work boundary missing", errors)
    require(
        "no prior datahub ledger adapter implementation is imported" in disclosure,
        "DISCLOSURE: no-reused-adapter statement missing",
        errors,
    )

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    require(
        "Apache License" in license_text and "Version 2.0" in license_text,
        "LICENSE is not recognizably Apache-2.0",
        errors,
    )

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    require('"3.11"' in workflow and '"3.12"' in workflow, "CI Python matrix incomplete", errors)
    for gate in (
        "ruff check",
        "mypy",
        "pytest",
        "uv build",
        "check_secrets",
        "check_public_package",
        "check_non_video_readiness",
    ):
        require(gate in workflow, f"CI gate missing: {gate}", errors)
    require("--extra datahub" in workflow, "CI DataHub dependency bootstrap missing", errors)
    workflow_root = ROOT / ".github/workflows"
    workflow_paths = sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])
    require(bool(workflow_paths), "no GitHub workflow files found", errors)
    expected_actions = {
        "actions/checkout@": "actions/checkout@v6",
        "actions/setup-python@": "actions/setup-python@v6",
        "actions/upload-artifact@": "actions/upload-artifact@v7",
        "astral-sh/setup-uv@": "astral-sh/setup-uv@v9.0.0",
    }
    for path in workflow_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- uses:"):
                stripped = stripped.removeprefix("- ").strip()
            if not stripped.startswith("uses:"):
                continue
            action_ref = stripped.removeprefix("uses:").strip()
            for action_prefix, expected in expected_actions.items():
                if action_ref.startswith(action_prefix):
                    require(
                        action_ref == expected,
                        f"{path.relative_to(ROOT)}: expected {expected}, found {action_ref}",
                        errors,
                    )

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    require("USER ledgerlens" in dockerfile, "Dockerfile must use non-root user", errors)
    require("HEALTHCHECK" in dockerfile, "Dockerfile health check missing", errors)

    check_json_templates(errors)
    check_shell(errors)

    if errors:
        print("Public-package check failed:")
        print("\n".join(f"  - {error}" for error in errors))
        return 1
    print(f"Public-package check passed ({len(REQUIRED_FILES)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
