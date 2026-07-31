#!/usr/bin/env python3
"""Run the deterministic DataHub-context ON/OFF incident benchmark."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.incident_commander.benchmark import (  # noqa: E402
    BenchmarkValidationError,
    build_benchmark_receipt,
    write_receipt_atomic,
)
from benchmarks.incident_commander.catalog import (  # noqa: E402
    CatalogValidationError,
    load_catalog,
)

DEFAULT_CATALOG = ROOT / "fixtures/incident_commander/catalog.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare deterministic incident command with DataHub context ON versus OFF."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--seed",
        type=int,
        help="Benchmark/bootstrap seed; defaults to the catalog generator seed.",
    )
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        catalog = load_catalog(catalog_path)
        seed = args.seed if args.seed is not None else catalog["generator"]["seed"]
        receipt = build_benchmark_receipt(
            catalog,
            seed=seed,
            measured_iterations=args.iterations,
            warmup_iterations=args.warmup,
            bootstrap_samples=args.bootstrap_samples,
            catalog_path=catalog_path,
            command=[sys.executable, *sys.argv],
        )
        write_receipt_atomic(output, receipt)
    except (CatalogValidationError, BenchmarkValidationError) as exc:
        print(f"incident benchmark rejected: {exc}", file=sys.stderr)
        return 2

    on_metrics = receipt["modes"]["datahubContextOn"]["metrics"]
    off_metrics = receipt["modes"]["datahubContextOff"]["metrics"]
    print(f"Wrote incident benchmark receipt: {output}")
    print(
        "Context ON/OFF owner accuracy: "
        f"{on_metrics['ownerAccuracy']['mean']:.3f}/"
        f"{off_metrics['ownerAccuracy']['mean']:.3f}"
    )
    print(
        "Context ON/OFF blast-radius recall: "
        f"{on_metrics['blastRadiusRecall']['mean']:.3f}/"
        f"{off_metrics['blastRadiusRecall']['mean']:.3f}"
    )
    print(
        "Context ON/OFF unsupported-claim rate: "
        f"{on_metrics['unsupportedClaimRate']['mean']:.3f}/"
        f"{off_metrics['unsupportedClaimRate']['mean']:.3f}"
    )
    print(f"Status: {receipt['status']}; candidateOnly=true; canClaimAGI=false")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
