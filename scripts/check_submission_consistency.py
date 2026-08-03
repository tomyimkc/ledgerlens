#!/usr/bin/env python3
"""Fail closed when judge-facing values drift out of agreement with the artifacts.

This guards against exactly the kind of silent drift an overclaim audit caught by hand:
a produced-artifact date in prose that disagreed with the receipt's own timestamp. Where a
value has an artifact source of truth (a receipt/catalog), docs are checked against the
artifact; where it is a shared constant, every surface that states it must agree.

The "v0.2.1 not yet published" invariant is enforced by ``scripts/check_non_video_readiness.py``
and is deliberately not duplicated here.

Run: ``python scripts/check_submission_consistency.py`` (also wired into ``make judge-check``).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Judge-facing surfaces that must not disagree with each other or the artifacts.
DOCS = (
    "README.md",
    "docs/DEVPOST_SUBMISSION.md",
    "docs/EVIDENCE_INDEX.md",
    "docs/WINNER_READINESS.md",
    "docs/SUBMISSION_LEDGER.md",
)

SPACE_URL = "https://tomyimkc-ledgerlens-incident-commander.hf.space/"
SPACE_HOST = "tomyimkc-ledgerlens-incident-commander.hf.space"
E16_RECEIPT = "benchmarks/incident_commander/live-incident-rehearsal-receipt.json"
CATALOG = "fixtures/incident_commander/catalog.json"


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _check_e16_date_matches_receipt(root: Path, errors: list[str]) -> None:
    """Every doc that states an E-16 'Produced <date>' must use the receipt's own UTC date."""
    receipt = json.loads(_read(root, E16_RECEIPT))
    truth_date = str(receipt["authorization"]["evaluated_at"])[:10]  # YYYY-MM-DD
    pattern = re.compile(r"[Pp]roduced (\d{4}-\d{2}-\d{2})")
    for rel in DOCS:
        for stated in pattern.findall(_read(root, rel)):
            if stated != truth_date:
                errors.append(
                    f"{rel}: 'Produced {stated}' disagrees with the E-16 receipt date "
                    f"{truth_date} ({E16_RECEIPT} authorization.evaluated_at)"
                )


def _check_benchmark_counts(root: Path, errors: list[str]) -> None:
    """Asset/scenario counts stated in docs must match the checked-in catalog."""
    catalog = json.loads(_read(root, CATALOG))
    assets = len(catalog["assets"])
    scenarios = len(catalog["scenarios"])
    for rel in DOCS:
        text = _read(root, rel)
        for m in re.finditer(r"(\d+)[ -]asset", text):
            stated = int(m.group(1))
            if 50 <= stated <= 500 and stated != assets:
                errors.append(f"{rel}: states {stated} assets; catalog has {assets}")
        for m in re.finditer(r"(\d+)[ -]scenario", text):
            stated = int(m.group(1))
            if 5 <= stated <= 200 and stated != scenarios:
                errors.append(f"{rel}: states {stated} scenarios; catalog has {scenarios}")


def _check_shared_constants(root: Path, errors: list[str]) -> None:
    """The *current* five-core score and bonus must agree wherever stated as a canonical score.

    Only the canonical ``<phrase> <n.n> / 10`` form is matched, so historical mentions
    ("rated the five-core average at 7.8", "reset it to ~5.8") are ignored.
    """
    core_values: set[str] = set()
    bonus_values: set[str] = set()
    core_re = re.compile(r"[Ff]ive-core average[:*\s]{0,6}(\d\.\d)\s*/\s*10")
    bonus_re = re.compile(r"[Bb]onus[:*\s]{0,6}(\d\.\d)\s*/\s*10")
    for rel in DOCS:
        text = _read(root, rel)
        core_values.update(core_re.findall(text))
        bonus_values.update(bonus_re.findall(text))
    if len(core_values) > 1:
        errors.append(f"current five-core average disagrees across docs: {sorted(core_values)}")
    if len(bonus_values) > 1:
        errors.append(f"current bonus score disagrees across docs: {sorted(bonus_values)}")


def _check_space_url(root: Path, errors: list[str]) -> None:
    """Any doc referencing the Space host must use the canonical URL form."""
    for rel in DOCS:
        text = _read(root, rel)
        if SPACE_HOST in text and SPACE_URL.rstrip("/") not in text:
            errors.append(f"{rel}: references the Space host but not the canonical URL {SPACE_URL}")


MANIFEST = "docs/submission-manifest.json"


def _check_manifest(root: Path, errors: list[str]) -> None:
    """The machine-readable manifest must agree with the artifacts and the docs."""
    manifest = json.loads(_read(root, MANIFEST))
    receipt = json.loads(_read(root, E16_RECEIPT))
    catalog = json.loads(_read(root, CATALOG))
    truth_date = str(receipt["authorization"]["evaluated_at"])[:10]
    if manifest["producedLiveArtifacts"]["date"] != truth_date:
        errors.append(
            f"{MANIFEST}: producedLiveArtifacts.date "
            f"{manifest['producedLiveArtifacts']['date']} != E-16 receipt date {truth_date}"
        )
    if manifest["benchmark"]["syntheticCatalogAssets"] != len(catalog["assets"]):
        errors.append(f"{MANIFEST}: benchmark asset count != catalog ({len(catalog['assets'])})")
    if manifest["benchmark"]["syntheticCatalogScenarios"] != len(catalog["scenarios"]):
        errors.append(
            f"{MANIFEST}: benchmark scenario count != catalog ({len(catalog['scenarios'])})"
        )
    # The manifest's five-core score must match the canonical scorecard figure.
    scorecard = _read(root, "docs/WINNER_READINESS.md")
    match = re.search(r"[Ff]ive-core average[:*\s]{0,6}(\d\.\d)\s*/\s*10", scorecard)
    if match and str(manifest["readinessSnapshot"]["fiveCoreAverage"]) != match.group(1):
        errors.append(
            f"{MANIFEST}: readinessSnapshot.fiveCoreAverage "
            f"{manifest['readinessSnapshot']['fiveCoreAverage']} != scorecard {match.group(1)}"
        )


def evaluate(root: Path) -> list[str]:
    errors: list[str] = []
    _check_e16_date_matches_receipt(root, errors)
    _check_benchmark_counts(root, errors)
    _check_shared_constants(root, errors)
    _check_space_url(root, errors)
    _check_manifest(root, errors)
    return errors


def main() -> int:
    errors = evaluate(ROOT)
    if errors:
        print("Submission consistency check FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("Submission consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
