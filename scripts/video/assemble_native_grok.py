#!/usr/bin/env python3
"""Assemble native Grok clips into a single submission MP4 (normalize + concat).

Each clip is forced to exactly 15s / 30fps / 1280x720 (or scaled to 1920x1080),
keeping Grok's native audio track — no macOS `say` TTS.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "artifacts" / "video" / "native-grok"
OUT = HERE / "output"
FINAL = HERE / "ledgerlens-native-grok.mp4"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", default=str(HERE / "scenes.json"))
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--clip-seconds", type=float, default=15.0)
    parser.add_argument("--output", type=Path, default=FINAL)
    args = parser.parse_args()

    scenes = json.loads(Path(args.scenes).read_text(encoding="utf-8"))["scenes"]
    work = HERE / "assemble"
    work.mkdir(parents=True, exist_ok=True)
    normalized: list[Path] = []
    for scene in scenes:
        src = OUT / f"{scene['id']}-raw.mp4"
        if not src.is_file():
            raise SystemExit(f"missing clip: {src} — run generate_native_grok.py first")
        dest = work / f"{scene['id']}-norm.mp4"
        # Scale to target, pad if needed, trim/pad to exact duration, keep native audio.
        vf = (
            f"scale={args.width}:{args.height}:force_original_aspect_ratio=decrease,"
            f"pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps=30,format=yuv420p,setsar=1"
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(src),
                "-t",
                f"{args.clip_seconds:.3f}",
                "-vf",
                vf,
                "-af",
                f"apad=pad_dur={args.clip_seconds:.3f},atrim=0:{args.clip_seconds:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(dest),
            ]
        )
        normalized.append(dest)

    concat_list = work / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{path.resolve()}'" for path in normalized) + "\n",
        encoding="utf-8",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(args.output),
        ]
    )
    # Optional burned English captions from requested speech (not native ASR).
    srt = work / "requested-speech.srt"
    blocks = []
    t = 0.0
    for index, scene in enumerate(scenes, start=1):
        start, end = t, t + args.clip_seconds

        def ts(sec: float) -> str:
            ms = int(round(sec * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        blocks.append(f"{index}\n{ts(start)} --> {ts(end)}\n{scene['speech']}\n")
        t = end
    srt.write_text("\n".join(blocks) + "\n", encoding="utf-8")

    receipt = {
        "schemaVersion": "1.0",
        "builtAtUtc": datetime.now(UTC).isoformat(),
        "candidateOnly": True,
        "canClaimAGI": False,
        "output": str(args.output),
        "bytes": args.output.stat().st_size,
        "clipCount": len(normalized),
        "durationSeconds": len(normalized) * args.clip_seconds,
        "nativeAudio": True,
        "tts": False,
        "profilePortrait": "artifacts/video/native-grok/presenter-reference.png",
        "pipeline": "polygraph generate.py recipe (grok-imagine-video-1.5)",
        "captionsRequestedSpeechSrt": str(srt),
        "disclaimer": (
            "Presenter is AI-generated from the user profile portrait with native Grok audio. "
            "Not a live recording. Human review of wording and lip-sync required before publish."
        ),
    }
    receipt_path = args.output.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    print(f"final: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
