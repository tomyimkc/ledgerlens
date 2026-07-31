#!/usr/bin/env python3
"""Build the deterministic synthetic DataHub incident catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.incident_commander.catalog import (  # noqa: E402
    DEFAULT_CATALOG_SEED,
    CatalogValidationError,
    generate_catalog,
    validate_catalog,
    write_catalog_atomic,
)

DEFAULT_OUTPUT = ROOT / "fixtures/incident_commander/catalog.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and validate the deterministic incident catalog."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_CATALOG_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        catalog = generate_catalog(args.seed)
        summary = validate_catalog(catalog)
        write_catalog_atomic(output, catalog)
    except CatalogValidationError as exc:
        print(f"incident catalog rejected: {exc}", file=sys.stderr)
        return 2
    print(
        "Wrote synthetic incident catalog: "
        f"{output} ({summary['assetCount']} assets, "
        f"{summary['lineageEdgeCount']} lineage edges, "
        f"{summary['incidentCount']} incidents, "
        f"{summary['scenarioCount']} scenarios, seed={args.seed})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
