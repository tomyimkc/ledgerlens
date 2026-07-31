#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

mkdir -p "$STATE_DIR"
printf '0\n' >"$STATE_DIR/expiry-deadline"

if [[ -f "$STATE_DIR/compose.env" ]]; then
  judge_compose down --remove-orphans
fi
if [[ -f "$DATAHUB_COMPOSE_FILE" ]]; then
  datahub_cli docker quickstart \
    --stop \
    --quickstart-compose-file "$DATAHUB_COMPOSE_FILE"
fi

echo "Judge services stopped. DataHub/Caddy volumes and scenario backups were preserved."
