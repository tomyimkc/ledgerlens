#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPT_ROOT="$ROOT/docs/demo/grok"
OUTPUT="$ROOT/artifacts/video/grok"

command -v grok >/dev/null || { echo "Grok CLI is required." >&2; exit 2; }
mkdir -p "$OUTPUT"

cat <<'EOF'
LedgerLens Grok asset policy:
  - concept visuals only;
  - no fake DataHub, LedgerLens, terminal, test, or benchmark UI;
  - every included clip must be labeled "CONCEPT VISUAL — AI-GENERATED";
  - real product proof comes from scripts/video/capture_real_ui.sh.
EOF

for prompt in "$PROMPT_ROOT"/*.prompt.md; do
  name="$(basename "$prompt" .prompt.md)"
  echo
  echo "Launching Grok CLI for: $name"
  echo "After generation, save the approved clip under: $OUTPUT/$name.mp4"
  echo "Prompt: $prompt"
  if [[ "${GROK_NONINTERACTIVE:-false}" == "true" ]]; then
    grok --cwd "$ROOT" --single "$(cat "$prompt")" --output-format plain \
      | tee "$OUTPUT/$name.grok-output.txt"
  else
    grok --cwd "$ROOT" "$(cat "$prompt")"
  fi
done

echo "Review every asset before adding it to the edit. Generated clips are optional."
