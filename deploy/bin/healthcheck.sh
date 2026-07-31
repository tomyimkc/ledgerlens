#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

wait_for_url "$(local_gms_url)/config" 60 2
wait_for_url "$(local_frontend_url)/login" 60 2

judge_compose ps
ledgerlens_container="$(judge_compose ps --quiet ledgerlens)"
if [[ -z "$ledgerlens_container" ]]; then
  echo "LedgerLens container is not running." >&2
  exit 1
fi
health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$ledgerlens_container")"
if [[ "$health_status" != "healthy" ]]; then
  printf 'LedgerLens container health is %s.\n' "$health_status" >&2
  exit 1
fi

gms_url="$(local_gms_url)"
admin_token_file="$STATE_DIR/admin-health.token"
umask 077
DATAHUB_GMS_URL="$gms_url" \
  DATAHUB_USERNAME="$DATAHUB_ADMIN_USERNAME" \
  DATAHUB_PASSWORD="$DATAHUB_ADMIN_PASSWORD" \
  datahub_cli init --token-duration ONE_HOUR --force >/dev/null
read_datahub_token >"$admin_token_file"
(
  cd "$ROOT"
  uv run python deploy/bin/provision_datahub.py verify \
    --gms-url "$gms_url" \
    --admin-token-file "$admin_token_file" \
    --receipt "$STATE_DIR/receipts/datahub-health.json"
)
rm -f "$admin_token_file" "$DATAHUB_HOME/.datahubenv"

curl --fail --silent --show-error --location --max-time 15 \
  --user "$JUDGE_GATEWAY_USERNAME:$JUDGE_GATEWAY_PASSWORD" \
  "https://${LEDGERLENS_FQDN}/healthz" >/dev/null
curl --fail --silent --show-error --location --max-time 15 \
  --user "$JUDGE_GATEWAY_USERNAME:$JUDGE_GATEWAY_PASSWORD" \
  "https://${DATAHUB_FQDN}/login" >/dev/null

echo "Judge environment health checks passed."
