#!/usr/bin/env python3
"""Render deterministic and live benchmark receipts without conflating them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ORDER = ("deterministic-fixture", "live-datahub-smoke")


def load_receipts(root: Path) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return receipts
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        kind = payload.get("benchmarkKind")
        if kind in ORDER:
            payload["_path"] = str(path)
            receipts[str(kind)] = payload
    return receipts


def render(receipts: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# LedgerLens benchmark summary",
        "",
        "> Working prototype results only; not independent validation.",
        "",
        "| Result class | Status | Duration | Live DataHub | External validation | Receipt |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for kind in ORDER:
        payload = receipts.get(kind)
        if payload is None:
            lines.append(
                f"| `{kind}` | NOT_RUN | — | "
                f"{'yes' if kind.startswith('live') else 'no'} | no | — |"
            )
            continue
        duration = payload.get("durationSeconds")
        duration_text = f"{duration:.3f}s" if isinstance(duration, (int, float)) else "—"
        lines.append(
            "| `{}` | {} | {} | {} | {} | `{}` |".format(
                kind,
                payload.get("status", "UNKNOWN"),
                duration_text,
                "yes" if payload.get("liveDataHub") else "no",
                "yes" if payload.get("externalValidation") else "no",
                payload.get("_path", ""),
            )
        )
    lines.extend(
        [
            "",
            "```yaml",
            "candidateOnly: true",
            "canClaimAGI: false",
            "```",
            "",
            "Deterministic fixture success does not imply a live DataHub pass. A live smoke pass",
            "does not establish source truth, independent validation, or production readiness.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipts = load_receipts(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(receipts), encoding="utf-8")
    print(f"Wrote benchmark summary: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
