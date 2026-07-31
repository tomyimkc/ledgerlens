#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temporary_state="$ROOT/deploy/state/validation-${RANDOM}-${RANDOM}"
mkdir -p "$temporary_state"
trap 'rm -rf "$temporary_state"' EXIT

export DEPLOY_STATE_DIR="$temporary_state"
export LEDGERLENS_FQDN="ledgerlens.validation.example"
export DATAHUB_FQDN="datahub.validation.example"
export CADDY_ACME_EMAIL="operator@example.org"
export JUDGE_GATEWAY_USERNAME="judge"
export JUDGE_GATEWAY_PASSWORD="validation-only-password"
export JUDGE_GATEWAY_PASSWORD_HASH="\$2a\$14\$Jn6/DLO0K7opr41xTWRlo./i8bklnjxZF2okOF.Yg3xZsRlFLgLgy"
export DATAHUB_ADMIN_USERNAME="datahub"
export DATAHUB_ADMIN_PASSWORD="validation-admin-password"
export DATAHUB_JUDGE_USERNAME="ledgerlens-judge"
export DATAHUB_JUDGE_PASSWORD="validation-judge-password"
export DATAHUB_SERVICE_USERNAME="ledgerlens-service"
export DATAHUB_SERVICE_PASSWORD="validation-service-password"
export DATAHUB_VERSION="v1.6.0"
export DATAHUB_CLI_VERSION="1.6.0.16"
export DATAHUB_QUICKSTART_COMPOSE_SHA256="ba39d779cd0e066553b5f4673384ece3d6a872e2245983525fc71e2ece1b5077"
export JUDGE_TTL_HOURS=1

(
  cd "$ROOT"
  uv sync --all-extras
  PYTHONPYCACHEPREFIX="$temporary_state/pycache" \
    uv run python -m py_compile deploy/bin/render_config.py deploy/bin/provision_datahub.py
  shellcheck deploy/bin/*.sh
  bash deploy/bin/prepare.sh
)

if command -v actionlint >/dev/null 2>&1; then
  actionlint "$ROOT/.github/workflows/deploy-incident-demo.yml"
fi

echo "Deployment YAML, Python, shell, Caddy, and official-compose patch validation passed."
