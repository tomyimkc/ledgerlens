#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS="$ROOT/artifacts/video-tools"
OUTPUT="${LEDGERLENS_VIDEO_OUTPUT:-$ROOT/artifacts/video}"
PLAN="${LEDGERLENS_CAPTURE_PLAN:-$OUTPUT/capture-plan.json}"

if [[ ! -d "$TOOLS/node_modules/playwright" ]]; then
  echo "Playwright tools are missing. Run 'make video-tools' first." >&2
  exit 2
fi
if [[ ! -f "$PLAN" ]]; then
  mkdir -p "$OUTPUT"
  cp "$ROOT/docs/demo/capture-plan.example.json" "$PLAN"
  echo "Created $PLAN." >&2
  echo "Review its URLs/selectors, then rerun 'make capture-demo'." >&2
  exit 2
fi

cp "$ROOT/scripts/video/capture_real_ui.mjs" "$TOOLS/capture_real_ui.mjs"
(
  cd "$ROOT"
  LEDGERLENS_ROOT="$ROOT" \
    LEDGERLENS_VIDEO_OUTPUT="$OUTPUT" \
    LEDGERLENS_CAPTURE_PLAN="$PLAN" \
    node "$TOOLS/capture_real_ui.mjs"
)
