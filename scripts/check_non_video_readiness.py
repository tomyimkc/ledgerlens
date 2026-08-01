#!/usr/bin/env python3
"""Fail closed when LedgerLens non-video competition evidence or contracts drift."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFERRED_BLOCKERS = (
    "Public under-three-minute video URL.",
    "Final v0.2.1 tag and commit, cut only after the public video URL is recorded.",
    "Owner Devpost account/team review, final Submit action, and saved submission receipt.",
    "Two consented formative external reviews; no result is claimed before they exist.",
    "Live Slack, PagerDuty, and Jira receipts unless the owner supplies scoped credentials.",
    "Upstream DataHub MCP maintainer review/merge; PR #160 remains external to this repository.",
)


def _load_json(path: Path, root: Path, errors: list[str]) -> Mapping[str, Any] | None:
    label = path.relative_to(root)
    if not path.is_file():
        errors.append(f"missing required receipt: {label}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{label}: invalid JSON: {error}")
        return {}
    if not isinstance(payload, Mapping):
        errors.append(f"{label}: receipt root must be an object")
        return {}
    return payload


def _value_at(payload: Mapping[str, Any], path: Sequence[str]) -> object:
    value: object = payload
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def check_receipt(
    root: Path,
    relative: str,
    expectations: Mapping[tuple[str, ...], object],
    errors: list[str],
) -> None:
    """Validate one immutable evidence receipt and its claim ceiling."""

    payload = _load_json(root / relative, root, errors)
    if payload is None:
        return
    for key_path, expected in expectations.items():
        actual = _value_at(payload, key_path)
        if actual != expected:
            dotted = ".".join(key_path)
            errors.append(f"{relative}: {dotted} must be {expected!r}, found {actual!r}")
    if payload.get("candidateOnly") is not True:
        errors.append(f"{relative}: candidateOnly must be true")
    if payload.get("canClaimAGI") is not False:
        errors.append(f"{relative}: canClaimAGI must be false")
    if "externalValidation" in payload and payload.get("externalValidation") is not False:
        errors.append(f"{relative}: externalValidation must be false when present")


def _require_text(
    text: str,
    needles: Sequence[str],
    *,
    label: str,
    errors: list[str],
) -> None:
    for needle in needles:
        if needle not in text:
            errors.append(f"{label}: missing required contract text: {needle}")


def _has_six_core_rubric_drift(text: str) -> bool:
    return "six equally weighted" in text.casefold() or bool(
        re.search(r"(?im)^.*(?:total|score|criteria).*?(?:\d{1,2}|_+)\s*/\s*24\b.*$", text)
    )


def evaluate_repository(root: Path = ROOT) -> tuple[list[str], tuple[str, ...]]:
    """Return hard failures and explicitly deferred owner/external blockers."""

    errors: list[str] = []
    receipt_contracts: tuple[tuple[str, Mapping[tuple[str, ...], object]], ...] = (
        (
            "benchmarks/results/deterministic-fixture-2026-07-31.json",
            {("status",): "PASS", ("externalValidation",): False},
        ),
        (
            "benchmarks/incident_commander/context-ablation-receipt.json",
            {("status",): "PASS", ("externalValidation",): False},
        ),
        (
            "benchmarks/results/live-datahub-smoke-2026-07-31.json",
            {("status",): "PASS", ("externalValidation",): False},
        ),
        (
            "benchmarks/results/live-public-proof-2026-07-31.json",
            {
                ("status",): "PASS",
                ("externalValidation",): False,
                ("teardown", "status"): "complete",
                ("paidResourceProvisioned",): False,
            },
        ),
        (
            "benchmarks/incident_commander/ai-verification-receipt.json",
            {
                ("authorization", "authorized"): True,
                ("externalMutations",): False,
            },
        ),
        (
            "benchmarks/incident_commander/github-live-action-receipt.json",
            {
                ("providerReceipt", "status"): "executed",
                ("closure", "state"): "closed",
                ("externalMutation",): True,
            },
        ),
        (
            "benchmarks/incident_commander/datahub-live-writeback-receipt.json",
            {
                ("status",): "applied",
                ("result", "success"): True,
                ("nextAgentRetrieval", "retrieved"): True,
                ("externalMutation",): True,
            },
        ),
    )
    for relative, expectations in receipt_contracts:
        check_receipt(root, relative, expectations, errors)

    required_paths = (
        ".github/workflows/hosted-smoke.yml",
        "scripts/check_hosted_incident_demo.py",
        "docs/EVIDENCE_INDEX.md",
        "docs/WINNER_READINESS.md",
        "docs/LIVE_DATAHUB_PUBLIC.md",
        "docs/EXTERNAL_EVALUATION.md",
        "benchmarks/results/live-public-proof-2026-07-31.json",
    )
    for relative in required_paths:
        if not (root / relative).is_file():
            errors.append(f"missing non-video readiness file: {relative}")

    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    _require_text(
        ci,
        ("--extra datahub", "uv run mypy src/ledgerlens", "check_non_video_readiness.py"),
        label=".github/workflows/ci.yml",
        errors=errors,
    )

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    sync_ci = re.search(r"(?ms)^sync-ci:.*?(?=^[A-Za-z0-9_.-]+:|\Z)", makefile)
    check_target = re.search(r"(?m)^check:([^\n]+)", makefile)
    demo_ui = re.search(r"(?ms)^demo-ui:.*?(?=^[A-Za-z0-9_.-]+:|\Z)", makefile)
    if sync_ci is None or "--extra datahub" not in sync_ci.group(0):
        errors.append("Makefile: sync-ci must install the datahub extra")
    if check_target is None or "typecheck" not in check_target.group(1).split():
        errors.append("Makefile: check must include typecheck")
    if demo_ui is None or "--no-open-browser" in demo_ui.group(0):
        errors.append("Makefile: demo-ui must not use the unsupported --no-open-browser flag")
    if "non-video-readiness:" not in makefile:
        errors.append("Makefile: non-video-readiness target missing")

    hosted_workflow = (root / ".github/workflows/hosted-smoke.yml").read_text(encoding="utf-8")
    _require_text(
        hosted_workflow,
        (
            "schedule:",
            "workflow_dispatch:",
            "actions/setup-python@v6",
            'python-version: "3.12"',
            "python3 scripts/check_hosted_incident_demo.py",
        ),
        label=".github/workflows/hosted-smoke.yml",
        errors=errors,
    )
    if "secrets." in hosted_workflow:
        errors.append(".github/workflows/hosted-smoke.yml: public smoke must not require secrets")

    readme = (root / "README.md").read_text(encoding="utf-8")
    submission = (root / "docs/DEVPOST_SUBMISSION.md").read_text(encoding="utf-8")
    writeup = (root / "docs/DEVPOST_WRITEUP.md").read_text(encoding="utf-8")
    checklist = (root / "docs/DEVPOST_CHECKLIST.md").read_text(encoding="utf-8")
    scorecard = (root / "docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md").read_text(
        encoding="utf-8"
    )
    winner_readiness = (root / "docs/WINNER_READINESS.md").read_text(encoding="utf-8")

    _require_text(
        readme,
        (
            "docs/EVIDENCE_INDEX.md",
            "docs/WINNER_READINESS.md",
            "docs/LIVE_DATAHUB_PUBLIC.md",
            "docs/EXTERNAL_EVALUATION.md",
            "benchmarks/results/live-public-proof-2026-07-31.json",
        ),
        label="README.md",
        errors=errors,
    )
    _require_text(
        writeup,
        (
            "Autonomous Data Incident Commander",
            "deterministic authorization",
            "next-agent handoff",
            "DataHub write-back",
            "provider-family independence",
        ),
        label="docs/DEVPOST_WRITEUP.md",
        errors=errors,
    )
    if "Turn failure records into an evidence-grounded action queue" in writeup + checklist:
        errors.append("Devpost copy still contains the retired failure-ledger tagline")

    _require_text(
        submission,
        (
            "v0.2.1",
            "pending public video URL",
            "EVIDENCE_INDEX.md",
            "docs/WINNER_READINESS.md",
            "live-public-proof-2026-07-31.json",
            "EXTERNAL_EVALUATION.md",
            "PR #160 remains open",
        ),
        label="docs/DEVPOST_SUBMISSION.md",
        errors=errors,
    )
    if "- [x] Publish final release/tag" in submission:
        errors.append("docs/DEVPOST_SUBMISSION.md: final v0.2.1 release must remain unchecked")
    if "releases/tag/v0.2.1" in submission or "releases/tag/v0.2.1" in readme:
        errors.append("release docs must not claim that v0.2.1 already exists")

    for label, text in (
        ("README.md", readme),
        ("docs/DEVPOST_SUBMISSION.md", submission),
        ("docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md", scorecard),
        ("docs/WINNER_READINESS.md", winner_readiness),
    ):
        _require_text(
            text,
            ("bonus",),
            label=label,
            errors=errors,
        )
        if "five core" not in text.casefold() and "five-core" not in text.casefold():
            errors.append(f"{label}: missing required contract text: five core")
        if _has_six_core_rubric_drift(text):
            errors.append(f"{label}: public rubric must use five core criteria plus separate bonus")

    for label, text in (
        ("README.md", readme),
        ("docs/DEVPOST_SUBMISSION.md", submission),
        ("docs/DEVPOST_WRITEUP.md", writeup),
    ):
        if "TODO" in text:
            errors.append(f"{label}: unresolved TODO marker remains")
        if "candidateOnly: true" not in text or "canClaimAGI: false" not in text:
            errors.append(f"{label}: claim ceiling is incomplete")

    return errors, DEFERRED_BLOCKERS


def main() -> int:
    errors, deferred = evaluate_repository()
    if errors:
        print("Non-video readiness: FAIL")
        print("\n".join(f"  - {error}" for error in errors))
        return 1
    print("Non-video readiness: PASS")
    print("Deferred owner/video/external blockers:")
    print("\n".join(f"  - {item}" for item in deferred))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
