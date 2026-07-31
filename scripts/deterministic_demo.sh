#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${LEDGERLENS_DEMO_OUTPUT:-$ROOT/artifacts/demo}"
mkdir -p "$OUT"

python - "$OUT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in (
    "validation.json",
    "ingestion.json",
    "triage-report.json",
    "triage-report.md",
    "supersession.json",
):
    (root / name).unlink(missing_ok=True)
PY

ledgerlens validate --demo --format json >"$OUT/validation.json"
ledgerlens ingest --demo --format json >"$OUT/ingestion.json"
ledgerlens triage --demo --format json --output "$OUT/triage-report.json"
ledgerlens triage --demo --format markdown --output "$OUT/triage-report.md"
ledgerlens supersession ledger-validator-blind-spots-2026-07-26 \
  --demo --format json >"$OUT/supersession.json"

python - "$OUT" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1])
records = {}
for path in sorted(root.iterdir()):
    if path.is_file():
        records[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
manifest = {
    "mode": "deterministic-fixture",
    "liveDataHub": False,
    "externalValidation": False,
    "candidateOnly": True,
    "canClaimAGI": False,
    "artifacts": records,
    "limitations": [
        "DataHub was not contacted.",
        "Fixture behavior is not independent validation of source findings.",
    ],
}
(root / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(manifest, indent=2, sort_keys=True))
PY
