#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=deploy/bin/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_judge_env

deadline_file="$STATE_DIR/expiry-deadline"
while [[ -f "$deadline_file" ]]; do
  deadline="$(<"$deadline_file")"
  if [[ ! "$deadline" =~ ^[0-9]+$ ]] || ((deadline == 0)); then
    exit 0
  fi
  now="$(date +%s)"
  if ((now >= deadline)); then
    echo "Judge TTL expired; stopping LedgerLens and DataHub without deleting volumes."
    bash "$DEPLOY_DIR/bin/down.sh"
    exit 0
  fi
  remaining=$((deadline - now))
  if ((remaining > 300)); then
    sleep 300
  else
    sleep "$remaining"
  fi
done
