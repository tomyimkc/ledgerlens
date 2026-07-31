#!/usr/bin/env python3
"""Build or emit the 120-asset incident catalog as DataHub MCPs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ledgerlens.catalog_runtime import load_incident_catalog
from ledgerlens.datahub_catalog import build_incident_catalog_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    bundle = build_incident_catalog_bundle(load_incident_catalog())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    emitted = 0
    if args.execute:
        try:
            from datahub.emitter.rest_emitter import DatahubRestEmitter
            from datahub.metadata.schema_classes import (
                ChangeTypeClass,
                GenericAspectClass,
                MetadataChangeProposalClass,
            )
        except ImportError:
            print("DataHub extra is required for --execute", file=sys.stderr)
            return 2
        url = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
        token = os.getenv("DATAHUB_GMS_TOKEN") or os.getenv("DATAHUB_TOKEN")
        emitter = DatahubRestEmitter(url, token=token, timeout_sec=12)
        try:
            for proposal in bundle["mcps"]:
                aspect = proposal["aspect"]
                emitter.emit_mcp(
                    MetadataChangeProposalClass(
                        entityType=proposal["entityType"],
                        entityUrn=proposal["entityUrn"],
                        changeType=ChangeTypeClass.UPSERT,
                        aspectName=proposal["aspectName"],
                        aspect=GenericAspectClass(
                            contentType=aspect["contentType"],
                            value=json.dumps(
                                aspect["value"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode(),
                        ),
                    )
                )
                emitted += 1
        finally:
            close = getattr(emitter, "close", None)
            if callable(close):
                close()
    print(
        json.dumps(
            {
                "assetCount": bundle["assetCount"],
                "entityCount": bundle["entityCount"],
                "proposalCount": len(bundle["mcps"]),
                "proposalsEmitted": emitted,
                "mutated": args.execute,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
