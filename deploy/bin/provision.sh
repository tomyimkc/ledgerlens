#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

gms_url="$(local_gms_url)"
admin_token_file="$STATE_DIR/admin.token"
service_token_file="$STATE_DIR/service.token"

umask 077
mkdir -p "$STATE_DIR/receipts"

DATAHUB_GMS_URL="$gms_url" \
  DATAHUB_USERNAME="$DATAHUB_ADMIN_USERNAME" \
  DATAHUB_PASSWORD="$DATAHUB_ADMIN_PASSWORD" \
  datahub_cli init --token-duration ONE_DAY --force >/dev/null
read_datahub_token >"$admin_token_file"
chmod 600 "$admin_token_file"

(
  cd "$ROOT"
  uv run python deploy/bin/provision_datahub.py bootstrap \
    --gms-url "$gms_url" \
    --admin-token-file "$admin_token_file" \
    --receipt "$STATE_DIR/receipts/datahub-bootstrap.json"
)

DATAHUB_GMS_URL="$gms_url" \
  DATAHUB_USERNAME="$DATAHUB_SERVICE_USERNAME" \
  DATAHUB_PASSWORD="$DATAHUB_SERVICE_PASSWORD" \
  datahub_cli init --token-duration ONE_WEEK --force >/dev/null
read_datahub_token >"$service_token_file"
chmod 600 "$service_token_file"
service_token="$(<"$service_token_file")"

admin_token="$(<"$admin_token_file")"
(
  cd "$ROOT"
  DATAHUB_GMS_URL="$gms_url" \
    DATAHUB_GMS_TOKEN="$admin_token" \
    LEDGERLENS_LLM_ENABLED=false \
    LEDGERLENS_MUTATIONS_ENABLED=false \
    uv run ledgerlens ingest fixtures/sophia_failure_ledger_sanitized.md \
      --format json >"$STATE_DIR/receipts/seed.json"
)

(
  cd "$ROOT"
  uv run python deploy/bin/provision_datahub.py lock-down \
    --gms-url "$gms_url" \
    --admin-token-file "$admin_token_file" \
    --receipt "$STATE_DIR/receipts/datahub-lock-down.json"
)

python3 - "$LEDGERLENS_RUNTIME_ENV" "$service_token" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
token = sys.argv[2]
if not token or "\n" in token or "\r" in token:
    raise SystemExit("invalid service token")
path.write_text(
    "\n".join(
        [
            f"DATAHUB_GMS_TOKEN={token}",
            "DATAHUB_TIMEOUT_SECONDS=15",
            "LEDGERLENS_MCP_TIMEOUT_SECONDS=20",
            "LEDGERLENS_LLM_ENABLED=false",
            "LEDGERLENS_MUTATIONS_ENABLED=false",
            "",
        ]
    ),
    encoding="utf-8",
)
path.chmod(0o600)
PY

rm -f "$admin_token_file" "$DATAHUB_HOME/.datahubenv"
unset admin_token service_token
echo "DataHub judge and service identities are provisioned and verified read-only."
