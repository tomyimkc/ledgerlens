#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

scenario="${1:-baseline}"
scenario_doc="$DEPLOY_DIR/scenarios/${scenario}.md"
baseline_backup="$STATE_DIR/scenarios/baseline.sql"
if [[ ! "$scenario" =~ ^[a-z0-9-]+$ ]] || [[ ! -f "$scenario_doc" ]]; then
  printf 'Unknown scenario: %s\nAvailable scenarios:\n' "$scenario" >&2
  find "$DEPLOY_DIR/scenarios" -maxdepth 1 -name '*.md' -exec basename {} .md \; | sort >&2
  exit 2
fi
if [[ ! -s "$baseline_backup" ]]; then
  echo "Baseline backup is missing; run deploy/bin/up.sh first." >&2
  exit 1
fi

judge_compose stop ledgerlens
datahub_cli docker quickstart \
  --restore \
  --restore-file "$baseline_backup" \
  --quickstart-compose-file "$DATAHUB_COMPOSE_FILE"
wait_for_url "$(local_gms_url)/config" 120 2
judge_compose up --detach ledgerlens caddy
printf '%s\n' "$scenario" >"$STATE_DIR/active-scenario"
bash "$DEPLOY_DIR/bin/healthcheck.sh"

echo "Scenario reset complete: $scenario"
echo "Judge guide: $scenario_doc"
