#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STACK_STATE_DIR="${LIVE_PROOF_STACK_STATE_DIR:-$HOME/.cache/ledgerlens-live-proof-stack}"
LIVE_PROOF_ENV_FILE="${LIVE_PROOF_ENV_FILE:-$STACK_STATE_DIR/judge.env}"
LEDGERLENS_PORT="${LIVE_PROOF_LEDGERLENS_PORT:-18000}"
APP_PID_FILE="$STACK_STATE_DIR/ledgerlens.pid"
APP_LOG_FILE="$STACK_STATE_DIR/ledgerlens.log"
APP_RUNNER="$STACK_STATE_DIR/run-ledgerlens.sh"

export DEPLOY_STATE_DIR="$STACK_STATE_DIR"
export JUDGE_ENV_FILE="$LIVE_PROOF_ENV_FILE"

# shellcheck source=deploy/bin/common.sh
# shellcheck disable=SC1091
source "$ROOT/deploy/bin/common.sh"

usage() {
  cat <<'EOF'
Usage: deploy/live-proof/stack.sh {check|start|status|stop}

This wrapper starts the repository's hardened, loopback-only DataHub OSS stack
and a live LedgerLens web process. It never creates a VM, DNS record, named
tunnel, or paid resource.

Required for start:
  LIVE_PROOF_ENV_FILE=/absolute/path/to/judge.env
  LIVE_PROOF_ALLOW_DOWNLOADS=1

The environment file uses the names documented in deploy/.env.example. For
this temporary no-DNS path, LEDGERLENS_FQDN and DATAHUB_FQDN may use distinct
.invalid placeholders because the generated public Caddy configuration is
validated but never started.
EOF
}

require_port_number() {
  local value="$1"
  local name="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || ((value < 1024 || value > 65535)); then
    printf '%s must be an integer between 1024 and 65535.\n' "$name" >&2
    return 2
  fi
}

port_is_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnH "sport = :$port" 2>/dev/null | grep -q .
  else
    return 1
  fi
}

process_matches() {
  local pid="$1"
  local command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command_line" == *"ledgerlens serve"* && "$command_line" == *"--port $LEDGERLENS_PORT"* ]]
}

stop_ledgerlens() {
  if [[ ! -f "$APP_PID_FILE" ]]; then
    return 0
  fi
  local pid
  pid="$(<"$APP_PID_FILE")"
  if process_matches "$pid"; then
    kill -TERM "$pid"
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
      printf 'LedgerLens PID %s did not stop after SIGTERM; leaving it for manual review.\n' \
        "$pid" >&2
      return 1
    fi
  elif kill -0 "$pid" 2>/dev/null; then
    printf 'Refusing to signal PID %s because it does not match this live-proof process.\n' \
      "$pid" >&2
    return 1
  fi
  : >"$APP_PID_FILE"
}

load_and_check_environment() {
  if [[ ! -f "$LIVE_PROOF_ENV_FILE" ]]; then
    printf 'Missing LIVE_PROOF_ENV_FILE: %s\n' "$LIVE_PROOF_ENV_FILE" >&2
    return 2
  fi
  load_judge_env
  export LEDGERLENS_FQDN="${LEDGERLENS_FQDN:-ledgerlens.invalid}"
  export DATAHUB_FQDN="${DATAHUB_FQDN:-datahub.invalid}"
  bash "$ROOT/deploy/bin/preflight.sh"
}

check_command() {
  require_port_number "$LEDGERLENS_PORT" LIVE_PROOF_LEDGERLENS_PORT
  load_and_check_environment

  for port in "$LEDGERLENS_PORT" "$DATAHUB_MAPPED_GMS_PORT" "$DATAHUB_MAPPED_FRONTEND_PORT"; do
    if port_is_listening "$port"; then
      printf 'Port %s is already listening; refusing to take over an existing service.\n' \
        "$port" >&2
      return 2
    fi
  done
  echo "Live-proof stack check passed."
}

start_ledgerlens() {
  cat >"$APP_RUNNER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd $(printf '%q' "$ROOT")
set -a
source $(printf '%q' "$LEDGERLENS_RUNTIME_ENV")
set +a
export DATAHUB_GMS_URL=$(printf '%q' "$(local_gms_url)")
export DATAHUB_FRONTEND_URL=$(printf '%q' "$(local_frontend_url)")
export DATAHUB_MCP_COMMAND=mcp-server-datahub
export DATAHUB_MCP_URL=
export DATAHUB_TELEMETRY_ENABLED=false
export DATAHUB_MCP_DOCUMENT_TOOLS_DISABLED=true
export SAVE_DOCUMENT_TOOL_ENABLED=false
export TOOLS_IS_MUTATION_ENABLED=false
export TOOLS_IS_USER_ENABLED=false
export LEDGERLENS_LLM_ENABLED=false
export LEDGERLENS_MUTATIONS_ENABLED=false
exec uv run ledgerlens serve \
  --host 127.0.0.1 \
  --port $(printf '%q' "$LEDGERLENS_PORT") \
  --no-open-browser
EOF
  chmod 700 "$APP_RUNNER"
  nohup "$APP_RUNNER" >"$APP_LOG_FILE" 2>&1 &
  printf '%s\n' "$!" >"$APP_PID_FILE"
  chmod 600 "$APP_PID_FILE" "$APP_LOG_FILE"

  if ! wait_for_url "http://127.0.0.1:${LEDGERLENS_PORT}/healthz" 60 2; then
    echo "LedgerLens failed to become healthy; inspect the private app log." >&2
    return 1
  fi
}

start_command() {
  if [[ "${LIVE_PROOF_ALLOW_DOWNLOADS:-0}" != "1" ]]; then
    cat >&2 <<'EOF'
Refusing to download Python packages or Docker images automatically.
Review disk/network impact, then rerun with LIVE_PROOF_ALLOW_DOWNLOADS=1.
EOF
    return 2
  fi

  check_command
  mkdir -p "$STACK_STATE_DIR"
  chmod 700 "$STACK_STATE_DIR"

  local started_datahub=0
  local completed=0
  cleanup_on_failure() {
    local exit_code=$?
    if ((completed == 0)); then
      stop_ledgerlens || true
      if ((started_datahub == 1)) && [[ -f "$DATAHUB_COMPOSE_FILE" ]]; then
        datahub_cli docker quickstart \
          --stop \
          --quickstart-compose-file "$DATAHUB_COMPOSE_FILE" || true
      fi
    fi
    return "$exit_code"
  }
  trap cleanup_on_failure EXIT

  (
    cd "$ROOT"
    uv sync --extra datahub --extra web
  )
  bash "$ROOT/deploy/bin/prepare.sh"

  export DATAHUB_VERSION DATAHUB_MAPPED_GMS_PORT DATAHUB_MAPPED_FRONTEND_PORT
  datahub_cli docker quickstart \
    --version "$DATAHUB_VERSION" \
    --quickstart-compose-file "$DATAHUB_COMPOSE_FILE" \
    --dump-logs-on-failure \
    --accept-version-default
  started_datahub=1

  wait_for_url "$(local_gms_url)/config" 120 2
  wait_for_url "$(local_frontend_url)/login" 120 2
  bash "$ROOT/deploy/bin/provision.sh"
  start_ledgerlens

  completed=1
  trap - EXIT
  echo "Private live-proof stack is ready."
  printf 'LedgerLens origin: http://127.0.0.1:%s\n' "$LEDGERLENS_PORT"
  printf 'DataHub origin: %s\n' "$(local_frontend_url)"
  echo "Run deploy/live-proof/quick_tunnels.sh start only after reviewing its public-exposure gate."
}

status_command() {
  load_judge_env
  local failed=0
  if curl --fail --silent --show-error --max-time 5 "$(local_gms_url)/config" >/dev/null; then
    echo "datahub_gms=healthy"
  else
    echo "datahub_gms=unreachable"
    failed=1
  fi
  if curl --fail --silent --show-error --max-time 5 "$(local_frontend_url)/login" >/dev/null; then
    echo "datahub_frontend=healthy"
  else
    echo "datahub_frontend=unreachable"
    failed=1
  fi
  if curl --fail --silent --show-error --max-time 5 \
    "http://127.0.0.1:${LEDGERLENS_PORT}/healthz" >/dev/null; then
    echo "ledgerlens=healthy"
  else
    echo "ledgerlens=unreachable"
    failed=1
  fi
  return "$failed"
}

stop_command() {
  load_judge_env
  local failed=0
  stop_ledgerlens || failed=1
  if [[ -f "$DATAHUB_COMPOSE_FILE" ]]; then
    datahub_cli docker quickstart \
      --stop \
      --quickstart-compose-file "$DATAHUB_COMPOSE_FILE" || failed=1
  fi
  echo "Live-proof processes stopped; DataHub volumes, images, and private state were preserved."
  return "$failed"
}

case "${1:-status}" in
  check)
    check_command
    ;;
  start)
    start_command
    ;;
  status)
    status_command
    ;;
  stop)
    stop_command
    ;;
  -h | --help | help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
