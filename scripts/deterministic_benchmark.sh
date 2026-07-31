#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pytest -q -m "not live_datahub"
bash scripts/deterministic_demo.sh >/dev/null
python scripts/check_public_package.py
python scripts/check_secrets.py

echo "Deterministic fixture benchmark completed."
echo "DataHub contacted: false"
echo "External validation: false"
