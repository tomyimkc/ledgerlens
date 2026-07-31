#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

(
  cd "$ROOT"
  uv sync --extra datahub
)
bash "$DEPLOY_DIR/bin/prepare.sh"

export DATAHUB_VERSION DATAHUB_MAPPED_GMS_PORT DATAHUB_MAPPED_FRONTEND_PORT
datahub_cli docker quickstart \
  --version "$DATAHUB_VERSION" \
  --quickstart-compose-file "$DATAHUB_COMPOSE_FILE" \
  --dump-logs-on-failure \
  --accept-version-default

wait_for_url "$(local_gms_url)/config" 120 2
wait_for_url "$(local_frontend_url)/login" 120 2
bash "$DEPLOY_DIR/bin/provision.sh"

judge_compose up --detach --build --remove-orphans

mkdir -p "$STATE_DIR/scenarios"
baseline_backup="$STATE_DIR/scenarios/baseline.sql"
datahub_cli docker quickstart \
  --backup \
  --backup-file "$baseline_backup" \
  --quickstart-compose-file "$DATAHUB_COMPOSE_FILE"
printf 'baseline\n' >"$STATE_DIR/active-scenario"

bash "$DEPLOY_DIR/bin/arm-expiry.sh"
bash "$DEPLOY_DIR/bin/healthcheck.sh"

echo "LedgerLens judge URL: https://${LEDGERLENS_FQDN}"
echo "DataHub judge URL: https://${DATAHUB_FQDN}"
echo "Share only the gateway and DataHub judge credentials; keep root/service credentials private."
