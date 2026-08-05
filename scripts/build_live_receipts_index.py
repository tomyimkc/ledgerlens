#!/usr/bin/env python3
"""Publish real-run receipts into the demo's per-incident real-receipt map.

Reads the committed live-run receipts (one per demo scenario, produced by
``run_all_incidents_live.py``) and writes a compact
``src/ledgerlens/static/live-receipts.json`` that the demo serves. A scenario that has a
real, executed run shows its real GitHub / Slack / PagerDuty / Jira receipts (with links
where clickable) and is marked "backed by a real run"; scenarios without one keep their
clearly-labelled simulated fixture receipts.

The existing E-16 run (``live-incident-rehearsal-receipt.json``) was a
``downstream_availability`` incident, so it seeds the demo's **deploy** scenario unless a
dedicated ``live-runs/deploy.json`` is present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCENARIOS = ["freshness", "schema", "volume", "access", "deploy", "ingest"]
LIVE_RUNS_DIR = Path("benchmarks/incident_commander/live-runs")
E16_RECEIPT = Path("benchmarks/incident_commander/live-incident-rehearsal-receipt.json")
OUTPUT = Path("src/ledgerlens/static/live-receipts.json")


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _entry(receipt: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a compact, link-bearing entry from a full run receipt, or None."""

    if receipt.get("status") != "executed" or not receipt.get("externalMutations"):
        return None
    state = receipt.get("dashboardState") or {}
    actions_in = state.get("actions") or []
    actions: list[dict[str, Any]] = []
    for action in actions_in:
        if not isinstance(action, dict):
            continue
        rid = action.get("receipt")
        if not rid or action.get("status") != "succeeded":
            continue
        url = rid if isinstance(rid, str) and rid.startswith("http") else None
        actions.append(
            {
                "provider": action.get("provider"),
                "receipt": rid,
                "url": url,
                "status": action.get("status"),
            }
        )
    if not actions:
        return None
    incident = receipt.get("incident") or {}
    writeback = state.get("writeback") or {}
    memory = state.get("memory") or {}
    return {
        "incidentId": incident.get("incident_id") or incident.get("id"),
        "status": "executed",
        "actions": actions,
        "writeback": writeback.get("receipt"),
        "memory": memory.get("memory_id"),
    }


def build_index() -> dict[str, Any]:
    index: dict[str, Any] = {}
    for scenario in SCENARIOS:
        receipt = _load(LIVE_RUNS_DIR / f"{scenario}.json")
        if receipt is None and scenario == "deploy":
            receipt = _load(E16_RECEIPT)  # E-16 was a downstream_availability run
        if receipt is None:
            continue
        entry = _entry(receipt)
        if entry is not None:
            index[scenario] = entry
    return index


def main() -> int:
    index = build_index()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if index:
        print(f"wrote {OUTPUT} with real runs for: {', '.join(sorted(index))}")
    else:
        print(f"wrote {OUTPUT} (no executed real runs found yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
