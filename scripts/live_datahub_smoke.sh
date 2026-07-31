#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/datahub_quickstart.sh status

python scripts/run_benchmark.py \
  --kind live-datahub-smoke \
  --datahub-version "${DATAHUB_VERSION:-v1.6.0}" \
  --output artifacts/benchmarks/live-datahub-smoke.json \
  -- bash scripts/live_datahub_checks.sh
