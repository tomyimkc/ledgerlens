#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${LEDGERLENS_VIDEO_OUTPUT:-$ROOT/artifacts/video}"
SCREENSHOTS="$OUT/screenshots"
WORK="$OUT/real-ui-montage"
FINAL="${LEDGERLENS_REAL_MONTAGE:-$OUT/real-ui-montage.mp4}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SHOT_DURATION="${LEDGERLENS_SHOT_DURATION:-5.625}"
FADE_OUT_START="$("$PYTHON_BIN" -c \
  'import sys; print(max(0.0, float(sys.argv[1]) - 0.2))' "$SHOT_DURATION")"

files=(
  "01-ledgerlens-boundary.png"
  "02-datahub-finding.png"
  "03-remediation-report.png"
  "04-supersession-chain.png"
  "05-reproducibility-receipts.png"
  "06-public-repository-disclosure.png"
)

command -v ffmpeg >/dev/null || { echo "ffmpeg is required." >&2; exit 2; }
mkdir -p "$WORK"

"$PYTHON_BIN" - "$WORK" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for path in root.glob("shot-*.mp4"):
    path.unlink()
(root / "concat.txt").unlink(missing_ok=True)
PY

concat="$WORK/concat.txt"
index=0
for name in "${files[@]}"; do
  input="$SCREENSHOTS/$name"
  [[ -f "$input" ]] || { echo "Missing real UI screenshot: $input" >&2; exit 2; }
  printf -v segment "%s/shot-%02d.mp4" "$WORK" "$index"
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -t "$SHOT_DURATION" -i "$input" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=$FADE_OUT_START:d=0.2" \
    -an -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p "$segment"
  printf "file '%s'\n" "$segment" >>"$concat"
  index=$((index + 1))
done

ffmpeg -hide_banner -loglevel error -y \
  -f concat -safe 0 -i "$concat" -c copy -movflags +faststart "$FINAL"

"$PYTHON_BIN" - "$ROOT" "$FINAL" "${files[@]}" <<'PY'
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
video = Path(sys.argv[2])
files = sys.argv[3:]
receipt = {
    "schemaVersion": "1.0",
    "captureKind": "real-ui-screenshot-montage",
    "syntheticProductImitation": False,
    "candidateOnly": True,
    "canClaimAGI": False,
    "createdAtUtc": datetime.now(UTC).isoformat(),
    "video": {
        "path": str(video.relative_to(root)),
        "sha256": sha256(video.read_bytes()).hexdigest(),
    },
    "sourceScreenshots": [
        {
            "path": str((video.parent / "screenshots" / name).relative_to(root)),
            "sha256": sha256((video.parent / "screenshots" / name).read_bytes()).hexdigest(),
        }
        for name in files
    ],
    "limitations": [
        "The montage is composed only from captured real UI screenshots.",
        "This is product-operation evidence, not independent validation of source findings.",
    ],
}
(video.parent / "montage-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"Real UI montage written to {video}")
PY
