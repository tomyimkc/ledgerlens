#!/usr/bin/env python3
"""Run the DataHub context ON/OFF ablation through the REAL LedgerLens pipeline.

Unlike ``run_incident_commander_benchmark.py`` (scripted responders), this exercises the
production ``VerifierPanel`` and ``PolicyGate`` end to end and writes a deterministic
receipt. See ``benchmarks/incident_commander/real_pipeline_ablation.py`` for the design
and its explicit limitations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from benchmarks.incident_commander.catalog import (  # noqa: E402
    CatalogValidationError,
    load_catalog,
)
from benchmarks.incident_commander.real_pipeline_ablation import (  # noqa: E402
    RealPipelineAblationError,
    build_ablation_receipt,
    write_receipt_atomic,
)

DEFAULT_CATALOG = ROOT / "fixtures/incident_commander/catalog.json"
DEFAULT_OUTPUT = ROOT / "benchmarks/incident_commander/real-pipeline-ablation-receipt.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the DataHub context ON/OFF ablation through the real planner-independent "
            "VerifierPanel and PolicyGate."
        )
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        catalog = load_catalog(catalog_path)
        receipt = build_ablation_receipt(catalog)
        write_receipt_atomic(output, receipt)
    except (CatalogValidationError, RealPipelineAblationError) as exc:
        print(f"Real-pipeline ablation failed: {exc}", file=sys.stderr)
        return 1

    on = receipt["arms"]["datahub-context-on"]["metrics"]
    off = receipt["arms"]["datahub-context-off"]["metrics"]
    print(f"Wrote real-pipeline ablation receipt: {output}")
    print(
        "Plan authorization rate ON/OFF: "
        f"{on['planAuthorizationRate']:.3f}/{off['planAuthorizationRate']:.3f}"
    )
    print(
        "Action grounding rate ON/OFF: "
        f"{on['actionGroundingRate']:.3f}/{off['actionGroundingRate']:.3f}"
    )
    print(f"OFF block reasons: {receipt['arms']['datahub-context-off']['blockReasonDistribution']}")
    print(f"Status: {receipt['status']}; candidateOnly=True; canClaimAGI=False")
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
