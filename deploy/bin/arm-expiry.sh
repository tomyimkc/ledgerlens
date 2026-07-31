#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

mkdir -p "$STATE_DIR"
deadline="$(( $(date +%s) + JUDGE_TTL_HOURS * 3600 ))"
printf '%s\n' "$deadline" >"$STATE_DIR/expiry-deadline"
date -u -r "$deadline" '+Expiry armed for %Y-%m-%dT%H:%M:%SZ' 2>/dev/null \
  || date -u -d "@$deadline" '+Expiry armed for %Y-%m-%dT%H:%M:%SZ'

nohup bash "$DEPLOY_DIR/bin/expiry-watchdog.sh" \
  </dev/null >>"$STATE_DIR/expiry.log" 2>&1 &
printf '%s\n' "$!" >"$STATE_DIR/expiry-watchdog.pid"
echo "Host-side expiry watchdog started."
