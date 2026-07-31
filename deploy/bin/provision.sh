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

init_datahub_token() {
  local username="$1"
  local password="$2"
  local duration="$3"
  local label="$4"
  local attempts="${5:-30}"
  local delay="${6:-4}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if DATAHUB_GMS_URL="$gms_url" \
      DATAHUB_USERNAME="$username" \
      DATAHUB_PASSWORD="$password" \
      datahub_cli init --token-duration "$duration" --force >/dev/null 2>&1; then
      return 0
    fi
    if ((attempt < attempts)); then
      sleep "$delay"
    fi
  done
  printf 'Timed out waiting for DataHub %s authentication after %s attempts.\n' \
    "$label" "$attempts" >&2
  return 1
}

init_datahub_token \
  "$DATAHUB_ADMIN_USERNAME" \
  "$DATAHUB_ADMIN_PASSWORD" \
  ONE_DAY \
  admin
read_datahub_token >"$admin_token_file"
chmod 600 "$admin_token_file"

(
  cd "$ROOT"
  uv run python deploy/bin/provision_datahub.py bootstrap \
    --gms-url "$gms_url" \
    --admin-token-file "$admin_token_file" \
    --receipt "$STATE_DIR/receipts/datahub-bootstrap.json"
)

init_datahub_token \
  "$DATAHUB_SERVICE_USERNAME" \
  "$DATAHUB_SERVICE_PASSWORD" \
  ONE_WEEK \
  service
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
    uv run ledgerlens ingest docs/fixtures/failure-ledger-demo.md \
      --format json >"$STATE_DIR/receipts/seed.json"
)

resource_urn="$(
  python3 - "$STATE_DIR/receipts/seed.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
urns = payload.get("dataset_urns")
if not isinstance(urns, list) or not urns or not isinstance(urns[0], str):
    raise SystemExit("seed receipt did not contain a dataset URN")
print(urns[0], end="")
PY
)"

(
  cd "$ROOT"
  uv run python deploy/bin/provision_datahub.py lock-down \
    --gms-url "$gms_url" \
    --admin-token-file "$admin_token_file" \
    --resource-urn "$resource_urn" \
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
unset admin_token resource_urn service_token
echo "DataHub judge and service identities are provisioned and verified read-only."
