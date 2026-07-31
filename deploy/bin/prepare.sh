#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

bash "$DEPLOY_DIR/bin/preflight.sh"

mkdir -p "$STATE_DIR/downloads" "$DATAHUB_HOME"
source_compose="$STATE_DIR/downloads/datahub-${DATAHUB_VERSION}-quickstart.yml"
temporary_compose="${source_compose}.tmp"
official_url="https://raw.githubusercontent.com/datahub-project/datahub/${DATAHUB_VERSION}/docker/quickstart/docker-compose.quickstart-profile.yml"

curl --fail --location --silent --show-error "$official_url" --output "$temporary_compose"
actual_hash="$(sha256_file "$temporary_compose")"
if [[ "$actual_hash" != "$DATAHUB_QUICKSTART_COMPOSE_SHA256" ]]; then
  printf 'Official DataHub compose hash mismatch. Expected %s, got %s.\n' \
    "$DATAHUB_QUICKSTART_COMPOSE_SHA256" "$actual_hash" >&2
  exit 1
fi
mv "$temporary_compose" "$source_compose"

(
  cd "$ROOT"
  uv run python deploy/bin/render_config.py \
    --source-compose "$source_compose" \
    --state-dir "$STATE_DIR" \
    --template "$DEPLOY_DIR/Caddyfile.template"
)

export DATAHUB_FQDN CADDY_IMAGE DATAHUB_NETWORK_NAME
export LEDGERLENS_RUNTIME_ENV CADDYFILE_PATH PUBLIC_HTTP_PORT PUBLIC_HTTPS_PORT
touch "$LEDGERLENS_RUNTIME_ENV"
chmod 600 "$LEDGERLENS_RUNTIME_ENV"
judge_compose config --quiet

docker run --rm --interactive \
  "$CADDY_IMAGE" \
  caddy validate --config - --adapter caddyfile <"$CADDYFILE_PATH"

echo "Rendered hardened deployment configuration under $STATE_DIR"
