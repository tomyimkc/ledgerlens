#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
STATE_DIR="${DEPLOY_STATE_DIR:-$DEPLOY_DIR/state}"
ENV_FILE="${JUDGE_ENV_FILE:-$DEPLOY_DIR/judge.env}"

load_judge_env() {
  if [[ -f "$ENV_FILE" ]]; then
    # The file is operator-controlled, mode 0600, and contains shell-quoted values.
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  export DATAHUB_VERSION="${DATAHUB_VERSION:-v1.6.0}"
  export DATAHUB_CLI_VERSION="${DATAHUB_CLI_VERSION:-1.6.0.16}"
  export DATAHUB_QUICKSTART_COMPOSE_SHA256="${DATAHUB_QUICKSTART_COMPOSE_SHA256:-ba39d779cd0e066553b5f4673384ece3d6a872e2245983525fc71e2ece1b5077}"
  export CADDY_IMAGE="${CADDY_IMAGE:-caddy:2.10.2-alpine}"
  export DATAHUB_ADMIN_USERNAME="${DATAHUB_ADMIN_USERNAME:-datahub}"
  export DATAHUB_JUDGE_USERNAME="${DATAHUB_JUDGE_USERNAME:-ledgerlens-judge}"
  export DATAHUB_SERVICE_USERNAME="${DATAHUB_SERVICE_USERNAME:-ledgerlens-service}"
  export DATAHUB_MAPPED_GMS_PORT="${DATAHUB_MAPPED_GMS_PORT:-8080}"
  export DATAHUB_MAPPED_FRONTEND_PORT="${DATAHUB_MAPPED_FRONTEND_PORT:-9002}"
  export PUBLIC_HTTP_PORT="${PUBLIC_HTTP_PORT:-80}"
  export PUBLIC_HTTPS_PORT="${PUBLIC_HTTPS_PORT:-443}"
  export JUDGE_TTL_HOURS="${JUDGE_TTL_HOURS:-24}"
  export DATAHUB_NETWORK_NAME="${DATAHUB_NETWORK_NAME:-ledgerlens-datahub_default}"
  export DATAHUB_HOME="${DATAHUB_HOME:-$STATE_DIR/datahub-home}"
  export DATAHUB_COMPOSE_FILE="${DATAHUB_COMPOSE_FILE:-$STATE_DIR/datahub-compose.judge.yml}"
  export LEDGERLENS_RUNTIME_ENV="${LEDGERLENS_RUNTIME_ENV:-$STATE_DIR/runtime.env}"
  export CADDYFILE_PATH="${CADDYFILE_PATH:-$STATE_DIR/Caddyfile}"
}

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Required command is unavailable: %s\n' "$command_name" >&2
    return 127
  }
}

require_value() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Required environment variable is unset: %s\n' "$name" >&2
    return 2
  fi
}

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    echo "Either sha256sum or shasum is required." >&2
    return 127
  fi
}

datahub_cli() {
  (
    cd "$ROOT"
    HOME="$DATAHUB_HOME" uv run datahub "$@"
  )
}

judge_compose() {
  docker compose \
    --project-name ledgerlens-judge \
    --env-file "$STATE_DIR/compose.env" \
    --file "$DEPLOY_DIR/docker-compose.judge.yml" \
    "$@"
}

local_gms_url() {
  printf 'http://127.0.0.1:%s' "$DATAHUB_MAPPED_GMS_PORT"
}

local_frontend_url() {
  printf 'http://127.0.0.1:%s' "$DATAHUB_MAPPED_FRONTEND_PORT"
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-90}"
  local delay="${3:-2}"
  local index
  for ((index = 1; index <= attempts; index++)); do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  printf 'Timed out waiting for %s\n' "$url" >&2
  return 1
}

read_datahub_token() {
  HOME="$DATAHUB_HOME" uv run python - <<'PY'
from pathlib import Path
import os
import yaml

path = Path(os.environ["HOME"]) / ".datahubenv"
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
token = ((payload or {}).get("gms") or {}).get("token")
if not isinstance(token, str) or not token:
    raise SystemExit("DataHub CLI config did not contain a token")
print(token, end="")
PY
}
