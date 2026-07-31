#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

for command_name in docker curl uv python3; do
  require_command "$command_name"
done
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
  echo "Either sha256sum or shasum is required." >&2
  exit 127
fi
docker info >/dev/null
docker compose version >/dev/null

for name in \
  LEDGERLENS_FQDN \
  DATAHUB_FQDN \
  JUDGE_GATEWAY_USERNAME \
  JUDGE_GATEWAY_PASSWORD \
  JUDGE_GATEWAY_PASSWORD_HASH \
  DATAHUB_ADMIN_PASSWORD \
  DATAHUB_JUDGE_PASSWORD \
  DATAHUB_SERVICE_PASSWORD; do
  require_value "$name"
done

if [[ "$DATAHUB_ADMIN_USERNAME" != "datahub" ]]; then
  echo "DATAHUB_ADMIN_USERNAME must remain 'datahub'; rotate its password instead." >&2
  exit 2
fi

if [[ "$LEDGERLENS_FQDN" == "$DATAHUB_FQDN" ]]; then
  echo "LedgerLens and DataHub require distinct DNS names." >&2
  exit 2
fi

for fqdn in "$LEDGERLENS_FQDN" "$DATAHUB_FQDN"; do
  if [[ "$fqdn" == *"://"* || "$fqdn" == */* || "$fqdn" != *.* ]]; then
    printf 'Expected a bare fully-qualified domain name, got: %s\n' "$fqdn" >&2
    exit 2
  fi
done

for value_name in \
  DATAHUB_ADMIN_PASSWORD \
  DATAHUB_JUDGE_PASSWORD \
  DATAHUB_SERVICE_PASSWORD; do
  value="${!value_name}"
  if [[ "$value" == *:* || "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    printf '%s cannot contain colon or newline characters (DataHub user.props format).\n' \
      "$value_name" >&2
    exit 2
  fi
  if ((${#value} < 16)); then
    printf '%s must be at least 16 characters.\n' "$value_name" >&2
    exit 2
  fi
done

if [[ ! "$JUDGE_TTL_HOURS" =~ ^[0-9]+$ ]] \
  || ((JUDGE_TTL_HOURS < 1 || JUDGE_TTL_HOURS > 168)); then
  echo "JUDGE_TTL_HOURS must be an integer between 1 and 168." >&2
  exit 2
fi

if [[ "$PUBLIC_HTTP_PORT" != "80" || "$PUBLIC_HTTPS_PORT" != "443" ]]; then
  echo "Public ports must remain 80/443 so Caddy ACME validation and HTTPS URLs are correct." >&2
  exit 2
fi

mkdir -p "$STATE_DIR"
available_kb="$(df -Pk "$STATE_DIR" | awk 'NR == 2 {print $4}')"
if [[ "$available_kb" =~ ^[0-9]+$ ]] && ((available_kb < 20 * 1024 * 1024)); then
  echo "At least 20 GB free disk is required for DataHub images and state." >&2
  exit 2
fi

if [[ -r /proc/meminfo ]]; then
  memory_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
  if [[ "$memory_kb" =~ ^[0-9]+$ ]] && ((memory_kb < 8 * 1024 * 1024)); then
    echo "DataHub quickstart requires at least 8 GB RAM; 16 GB is recommended." >&2
    exit 2
  fi
fi

echo "Preflight passed."
echo "Operator must still enforce a cloud firewall/security group allowing only SSH, 80, and 443."
