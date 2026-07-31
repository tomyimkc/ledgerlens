#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS="$ROOT/artifacts/video-tools"
VERSION="${PLAYWRIGHT_VERSION:-1.62.1}"

command -v node >/dev/null || { echo "Node.js is required." >&2; exit 2; }
command -v npm >/dev/null || { echo "npm is required." >&2; exit 2; }

mkdir -p "$TOOLS"
if [[ ! -f "$TOOLS/package.json" ]]; then
  (
    cd "$TOOLS"
    npm init --yes >/dev/null
  )
fi

echo "Installing Playwright $VERSION under artifacts/video-tools/"
npm --prefix "$TOOLS" install --no-save "playwright@$VERSION"
npx --prefix "$TOOLS" playwright install chromium

cp "$ROOT/scripts/video/capture_real_ui.mjs" "$TOOLS/capture_real_ui.mjs"
echo "Capture tools ready: $TOOLS"
