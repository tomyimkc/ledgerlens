#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
DATAHUB_VERSION="${DATAHUB_VERSION:-v1.6.0}"
GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8080}"
FRONTEND_URL="${DATAHUB_FRONTEND_URL:-http://localhost:9002}"

datahub_cmd() {
  if command -v datahub >/dev/null 2>&1; then
    datahub "$@"
  elif command -v uv >/dev/null 2>&1; then
    uv run datahub "$@"
  else
    echo "DataHub CLI is unavailable. Run 'make setup' first." >&2
    return 127
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-90}"
  local delay="${3:-2}"
  for ((index = 1; index <= attempts; index++)); do
    if curl --fail --silent --show-error --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

case "$ACTION" in
  up)
    echo "Starting external DataHub OSS quickstart version $DATAHUB_VERSION"
    datahub_cmd docker quickstart --version "$DATAHUB_VERSION"
    wait_for_url "$GMS_URL/config"
    echo "DataHub GMS is ready at $GMS_URL"
    echo "DataHub frontend: $FRONTEND_URL"
    ;;
  down)
    echo "Stopping DataHub quickstart without deleting volumes or images."
    datahub_cmd docker quickstart --stop
    ;;
  status)
    gms_status="unreachable"
    frontend_status="unreachable"
    if curl --fail --silent --max-time 3 "$GMS_URL/config" >/dev/null; then
      gms_status="reachable"
    fi
    if curl --fail --silent --max-time 3 "$FRONTEND_URL" >/dev/null; then
      frontend_status="reachable"
    fi
    printf 'DataHub GMS: %s (%s)\n' "$gms_status" "$GMS_URL"
    printf 'DataHub frontend: %s (%s)\n' "$frontend_status" "$FRONTEND_URL"
    [[ "$gms_status" == "reachable" && "$frontend_status" == "reachable" ]]
    ;;
  *)
    echo "Usage: $0 {up|down|status}" >&2
    exit 2
    ;;
esac
