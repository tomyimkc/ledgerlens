#!/usr/bin/env python3
"""Back every demo incident with a real run by executing the live pipeline for each.

The public demo shows six incident types. This driver runs the SAME real pipeline that
produced E-16 — real LLM planner + verifier quorum + deterministic PolicyGate + real
provider adapters — once per incident type, writing one receipt per demo scenario. A judge
can then click through each incident's real GitHub / Slack / PagerDuty / Jira artifacts.

It is OWNER-run: it fires real, irreversible actions in your accounts (a GitHub issue in
the public repo, a Slack post, a PagerDuty event that may page on-call, and a Jira ticket
per incident) and needs your real credentials. It requires ``--confirm-live`` and is never
wired into CI.

Usage (from the repo root, with credentials in the environment / .env)::

    uv run python scripts/run_all_incidents_live.py --confirm-live

Then rebuild the demo's real-receipt index::

    uv run python scripts/build_live_receipts_index.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# One catalog incident per demo scenario id (kinds map to the six demo issues).
SCENARIO_INCIDENTS: list[tuple[str, str]] = [
    ("freshness", "inc-analytics-freshness_breach-01"),
    ("schema", "inc-analytics-schema_drift-01"),
    ("volume", "inc-analytics-quality_regression-01"),
    ("access", "inc-analytics-pii_exposure-01"),
    ("deploy", "inc-analytics-downstream_availability-01"),
    ("ingest", "inc-analytics-model_drift-01"),
]

OUTPUT_DIR = Path("benchmarks/incident_commander/live-runs")
REHEARSAL = Path("scripts/run_live_incident_rehearsal.py")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required: acknowledges that this executes real provider actions per incident.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="Run only the named scenario id(s); repeatable. Default: all six.",
    )
    args = parser.parse_args()

    if not args.confirm_live:
        print(
            "--confirm-live is required: this fires real GitHub/Slack/PagerDuty/Jira actions.",
            file=sys.stderr,
        )
        return 2

    selected = [pair for pair in SCENARIO_INCIDENTS if not args.only or pair[0] in set(args.only)]
    if not selected:
        print(f"no matching scenarios for --only {args.only}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str, int]] = []
    for scenario, incident_id in selected:
        output = OUTPUT_DIR / f"{scenario}.json"
        print(f"\n=== {scenario}  ({incident_id}) -> {output} ===", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(REHEARSAL),
                "--incident-id",
                incident_id,
                "--output",
                str(output),
                "--confirm-live",
                "--force",
            ],
            check=False,
        )
        results.append((scenario, incident_id, completed.returncode))

    print("\n=== summary ===")
    failures = 0
    for scenario, incident_id, code in results:
        state = "ok" if code == 0 else f"FAILED (exit {code})"
        if code != 0:
            failures += 1
        print(f"  {scenario:10} {incident_id:42} {state}")
    print(
        "\nNext: `uv run python scripts/build_live_receipts_index.py` to publish the "
        "real receipts into the demo."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
