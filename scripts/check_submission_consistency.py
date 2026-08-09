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

import hashlib
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
E07_RECEIPT = "benchmarks/incident_commander/datahub-live-writeback-receipt.json"
E08_RECEIPT = "benchmarks/incident_commander/ai-verification-receipt.json"
LADDER = "benchmarks/incident_commander/live-evidence-ladder.json"
PUBLIC_DERIVATIVES = {
    "benchmarks/incident_commander/public-ai-verification-receipt.json": E08_RECEIPT,
    "benchmarks/incident_commander/public-live-incident-rehearsal-receipt.json": E16_RECEIPT,
    "benchmarks/incident_commander/public-datahub-live-writeback-receipt.json": E07_RECEIPT,
}
CATALOG = "fixtures/incident_commander/catalog.json"


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _sha256(root: Path, rel: str) -> str:
    return "sha256:" + hashlib.sha256((root / rel).read_bytes()).hexdigest()


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


def _check_public_evidence_derivatives(root: Path, errors: list[str]) -> None:
    """Public receipt views must remain bound to their committed raw evidence."""
    forbidden = re.compile(r"api\.020s\.com|\b020s:|\bautonomous\b", re.IGNORECASE)
    for derivative_rel, source_rel in PUBLIC_DERIVATIVES.items():
        derivative = json.loads(_read(root, derivative_rel))
        expected_digest = _sha256(root, source_rel)
        if derivative.get("publicDerivative") is not True:
            errors.append(f"{derivative_rel}: publicDerivative must be true")
        if derivative.get("sourceReceipt") != source_rel:
            errors.append(
                f"{derivative_rel}: sourceReceipt must be {source_rel}, "
                f"found {derivative.get('sourceReceipt')!r}"
            )
        if derivative.get("sourceReceiptDigest") != expected_digest:
            errors.append(f"{derivative_rel}: sourceReceiptDigest does not match {source_rel}")
        if derivative.get("candidateOnly") is not True:
            errors.append(f"{derivative_rel}: candidateOnly must be true")
        if derivative.get("canClaimAGI") is not False:
            errors.append(f"{derivative_rel}: canClaimAGI must be false")
        if forbidden.search(_read(root, derivative_rel)):
            errors.append(f"{derivative_rel}: stale public presentation wording remains")


def _check_live_evidence_ladder(root: Path, errors: list[str]) -> None:
    ladder = json.loads(_read(root, LADDER))
    layers = ladder.get("layers")
    evidence_ids = (
        [layer.get("evidenceId") for layer in layers if isinstance(layer, dict)]
        if isinstance(layers, list)
        else []
    )
    if evidence_ids != ["E-16", "E-07", "E-21"]:
        errors.append(f"{LADDER}: evidence ladder order must be E-16, E-07, E-21")
    checks = ladder.get("crossReceiptChecks")
    if not isinstance(checks, dict):
        errors.append(f"{LADDER}: crossReceiptChecks must be an object")
        return
    if checks.get("e16SourceDigest") != _sha256(root, E16_RECEIPT):
        errors.append(f"{LADDER}: E-16 source digest drifted")
    if checks.get("e07SourceDigest") != _sha256(root, E07_RECEIPT):
        errors.append(f"{LADDER}: E-07 source digest drifted")
    if checks.get("integratedSameProcessRun") is not False:
        errors.append(f"{LADDER}: must disclose that E-16 and E-07 were separate runs")
    if ladder.get("candidateOnly") is not True or ladder.get("canClaimAGI") is not False:
        errors.append(f"{LADDER}: claim boundary drifted")
    static_ladder = json.loads(_read(root, "src/ledgerlens/static/live-evidence-ladder.json"))
    if static_ladder != ladder:
        errors.append(f"{LADDER}: packaged static copy is stale")


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
    _check_public_evidence_derivatives(root, errors)
    _check_live_evidence_ladder(root, errors)
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
