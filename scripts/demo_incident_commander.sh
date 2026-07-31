#!/usr/bin/env bash
set -euo pipefail

host="${LEDGERLENS_HOST:-127.0.0.1}"
port="${LEDGERLENS_PORT:-8000}"
autonomous="${LEDGERLENS_AUTONOMOUS:-true}"
open_browser="${LEDGERLENS_OPEN_BROWSER:-true}"

case "$autonomous" in
  true|1|yes) authorization_flag="--autonomous" ;;
  false|0|no) authorization_flag="--manual" ;;
  *)
    echo "LEDGERLENS_AUTONOMOUS must be true or false." >&2
    exit 2
    ;;
esac

case "$open_browser" in
  true|1|yes) browser_flag="--open-browser" ;;
  false|0|no) browser_flag="--no-open-browser" ;;
  *)
    echo "LEDGERLENS_OPEN_BROWSER must be true or false." >&2
    exit 2
    ;;
esac

echo "LedgerLens Incident Commander"
echo "  URL: http://${host}:${port}/incident"
echo "  mode: FIXTURE / REPLAY"
echo "  authorization: ${authorization_flag#--}"
echo "  external mutations: false"
echo "  candidateOnly: true"
echo "  canClaimAGI: false"

exec ledgerlens incident-commander \
  --fixture \
  "$authorization_flag" \
  "$browser_flag" \
  --host "$host" \
  --port "$port"
