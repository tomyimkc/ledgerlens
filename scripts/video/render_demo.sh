#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${LEDGERLENS_VIDEO_OUTPUT:-$ROOT/artifacts/video}"
WORK="$OUT/render"
REAL_CAPTURE="${LEDGERLENS_REAL_CAPTURE:-$OUT/real-ui-capture.webm}"
INTRO="${LEDGERLENS_GROK_INTRO:-}"
OUTRO="${LEDGERLENS_GROK_OUTRO:-}"
NARRATION="${LEDGERLENS_NARRATION:-$OUT/narration.wav}"
CAPTIONS="${LEDGERLENS_CAPTIONS:-$OUT/captions.srt}"
FINAL="${LEDGERLENS_FINAL_VIDEO:-$OUT/ledgerlens-demo.mp4}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LABEL="$WORK/concept-label.png"
INTRO_SECONDS="${LEDGERLENS_INTRO_SECONDS:-3}"
OUTRO_SECONDS="${LEDGERLENS_OUTRO_SECONDS:-2}"
SEGMENTS_TSV="$WORK/segments.tsv"
MANIFEST="$OUT/render-manifest.json"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required." >&2; exit 2; }
[[ -f "$REAL_CAPTURE" ]] || {
  echo "Real UI capture is required: $REAL_CAPTURE" >&2
  echo "Synthetic footage cannot substitute for product proof." >&2
  exit 2
}
[[ -f "$NARRATION" ]] || { echo "English narration is required: $NARRATION" >&2; exit 2; }
[[ -f "$CAPTIONS" ]] || { echo "English captions are required: $CAPTIONS" >&2; exit 2; }

mkdir -p "$WORK"
"$PYTHON_BIN" "$ROOT/scripts/video/create_concept_label.py" "$LABEL"
"$PYTHON_BIN" - "$WORK" <<'PY'
from pathlib import Path
import sys
for path in Path(sys.argv[1]).glob("segment-*.mp4"):
    path.unlink()
(Path(sys.argv[1]) / "concat.txt").unlink(missing_ok=True)
(Path(sys.argv[1]) / "segments.tsv").unlink(missing_ok=True)
PY

segments=()
encode_segment() {
  local input="$1"
  local output="$2"
  local generated="$3"
  local max_duration="${4:-}"
  local filter="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
  if [[ "$generated" == "true" ]]; then
    ffmpeg -hide_banner -loglevel error -y \
      -i "$input" -loop 1 -i "$LABEL" \
      -filter_complex "[0:v]$filter[base];[base][1:v]overlay=40:990:shortest=1[out]" \
      -map "[out]" -t "$max_duration" -an \
      -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p "$output"
  else
    ffmpeg -hide_banner -loglevel error -y -i "$input" \
      -an -vf "$filter" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p "$output"
  fi
  segments+=("$output")
  printf "%s\t%s\n" "$output" "$generated" >>"$SEGMENTS_TSV"
}

index=0
if [[ -n "$INTRO" ]]; then
  [[ -f "$INTRO" ]] || { echo "Missing Grok intro: $INTRO" >&2; exit 2; }
  printf -v segment "%s/segment-%02d.mp4" "$WORK" "$index"
  encode_segment "$INTRO" "$segment" true "$INTRO_SECONDS"
  index=$((index + 1))
fi

printf -v segment "%s/segment-%02d.mp4" "$WORK" "$index"
encode_segment "$REAL_CAPTURE" "$segment" false
index=$((index + 1))

if [[ -n "$OUTRO" ]]; then
  [[ -f "$OUTRO" ]] || { echo "Missing Grok outro: $OUTRO" >&2; exit 2; }
  printf -v segment "%s/segment-%02d.mp4" "$WORK" "$index"
  encode_segment "$OUTRO" "$segment" true "$OUTRO_SECONDS"
fi

concat_file="$WORK/concat.txt"
for item in "${segments[@]}"; do
  printf "file '%s'\n" "$item" >>"$concat_file"
done

silent="$WORK/silent-proof.mp4"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$concat_file" -c copy "$silent"

CAPTIONS_FILTER="$("$PYTHON_BIN" - "$CAPTIONS" <<'PY'
import sys
print(sys.argv[1].replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'"))
PY
)"
ffmpeg -hide_banner -loglevel error -y \
  -i "$silent" -i "$NARRATION" -i "$CAPTIONS" \
  -filter_complex \
  "[0:v]subtitles=filename='$CAPTIONS_FILTER':force_style='FontName=Arial,FontSize=24,Outline=2,Shadow=0,MarginV=42'[v]" \
  -map "[v]" -map 1:a:0 -map 2:0 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -c:s mov_text \
  -metadata:s:s:0 language=eng -movflags +faststart \
  "$FINAL"

"$PYTHON_BIN" - "$ROOT" "$SEGMENTS_TSV" "$MANIFEST" <<'PY'
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
segments_file = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
segments = []
generated_seconds = 0.0
real_seconds = 0.0
for line in segments_file.read_text(encoding="utf-8").splitlines():
    path_text, generated_text = line.split("\t", 1)
    path = Path(path_text)
    duration = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
    )
    generated = generated_text == "true"
    generated_seconds += duration if generated else 0.0
    real_seconds += 0.0 if generated else duration
    segments.append(
        {
            "path": str(path.relative_to(root)),
            "generated": generated,
            "durationSeconds": duration,
        }
    )
total = generated_seconds + real_seconds
manifest = {
    "schemaVersion": "1.0",
    "createdAtUtc": datetime.now(UTC).isoformat(),
    "segments": segments,
    "generatedSeconds": generated_seconds,
    "realProductProofSeconds": real_seconds,
    "generatedRatio": generated_seconds / total if total else 0.0,
    "captionsBurnedIn": True,
    "selectableEnglishCaptionTrack": True,
    "candidateOnly": True,
    "canClaimAGI": False,
}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

"$PYTHON_BIN" "$ROOT/scripts/video/verify_video.py" "$FINAL"
echo "Rendered LedgerLens demo: $FINAL"
