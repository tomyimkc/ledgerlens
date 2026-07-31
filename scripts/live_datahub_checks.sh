#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${LEDGERLENS_LIVE_SOURCE:-$ROOT/docs/fixtures/failure-ledger-demo.md}"
GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8080}"
OUT="${LEDGERLENS_LIVE_OUTPUT:-$ROOT/artifacts/live-smoke}"
EXPLAIN_ID="${LEDGERLENS_LIVE_EXPLAIN_ID:-mcp-audit-surface-gap-2026-07-26}"
SUPERSESSION_ID="${LEDGERLENS_LIVE_SUPERSESSION_ID:-strict-parser-fixture-suite-2026-07-31}"

mkdir -p "$OUT"

python - "$OUT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in (
    "datahub-config.json",
    "validation.json",
    "ingestion.json",
    "triage-report.json",
    "explain.json",
    "supersession.json",
):
    (root / name).unlink(missing_ok=True)
PY

curl --fail --silent --show-error --max-time 5 "$GMS_URL/config" >"$OUT/datahub-config.json"
ledgerlens validate "$SOURCE" --format json >"$OUT/validation.json"
ledgerlens ingest "$SOURCE" --format json >"$OUT/ingestion.json"
ledgerlens triage --format json --output "$OUT/triage-report.json"
ledgerlens explain "$EXPLAIN_ID" --format json >"$OUT/explain.json"
ledgerlens supersession "$SUPERSESSION_ID" --format json >"$OUT/supersession.json"

python - \
  "$OUT/ingestion.json" \
  "$OUT/triage-report.json" \
  "$OUT/explain.json" \
  "$OUT/supersession.json" <<'PY'
from pathlib import Path
import json
import sys

ingestion = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
explain = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
supersession = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
if ingestion.get("mode") != "live" or ingestion.get("mutated") is not True:
    raise SystemExit("live smoke did not produce a live DataHub ingestion receipt")
if int(ingestion.get("dataset_count", 0)) < 1:
    raise SystemExit("live smoke ingested no DataHub datasets")
if payload.get("mode") != "live":
    raise SystemExit("live smoke refused a deterministic demo payload")
if payload.get("candidateOnly") is not True:
    raise SystemExit("candidateOnly must remain true")
if payload.get("canClaimAGI") is not False:
    raise SystemExit("canClaimAGI must remain false")
if payload.get("conflicts"):
    raise SystemExit(f"live triage has grounding conflicts: {payload['conflicts']}")
if int(payload.get("summary", {}).get("actionable", 0)) < 1:
    raise SystemExit("live triage produced no actionable findings")
audit = explain.get("finding", {}).get("audit", {})
if not audit.get("ingested_at") or not audit.get("ingested_by"):
    raise SystemExit("live explain did not recover DataHub audit metadata")
chain = supersession.get("chain", [])
if len(chain) < 2:
    raise SystemExit("live supersession did not recover the explicit historical chain")
for result in (explain, supersession):
    if result.get("candidateOnly") is not True or result.get("canClaimAGI") is not False:
        raise SystemExit("live result violated the claim boundary")
print("Live DataHub triage artifact passed claim-boundary checks.")
PY
