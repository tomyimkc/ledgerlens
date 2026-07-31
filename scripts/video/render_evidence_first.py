#!/usr/bin/env python3
"""Render the 2:48 LedgerLens evidence-first demo with narration and captions."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "artifacts/video/evidence-first"
TIMELINE = ROOT / "docs/demo/evidence-first-timeline.json"


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def duration(path: Path) -> float:
    return float(
        run(
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
            capture=True,
        )
    )


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def atempo_chain(factor: float) -> str:
    factors: list[float] = []
    remaining = factor
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={item:.8f}" for item in factors)


def allocate_cue_durations(cues: list[str], scene_seconds: float) -> list[float]:
    weights = [max(1, len(cue.split())) for cue in cues]
    total = sum(weights)
    raw = [scene_seconds * weight / total for weight in weights]
    minimum = min(3.0, scene_seconds / len(cues))
    allocated = [max(minimum, item) for item in raw]
    scale = scene_seconds / sum(allocated)
    allocated = [item * scale for item in allocated]
    allocated[-1] += scene_seconds - sum(allocated)
    return allocated


def build_narration(
    timeline: dict[str, Any],
    work: Path,
    *,
    voice: str,
    rate: int,
) -> tuple[Path, Path]:
    say = shutil.which("say")
    if not say:
        raise SystemExit("macOS 'say' is required unless a narration track is supplied.")
    cue_audio = work / "narration-cues"
    cue_audio.mkdir(parents=True, exist_ok=True)
    concat_lines: list[str] = []
    srt_blocks: list[str] = []
    cursor = 0.0
    cue_number = 1

    for scene in timeline["scenes"]:
        cues = list(scene["cues"])
        allocations = allocate_cue_durations(cues, float(scene["durationSeconds"]))
        for cue, allocation in zip(cues, allocations, strict=True):
            stem = cue_audio / f"cue-{cue_number:03d}"
            text_path = stem.with_suffix(".txt")
            aiff_path = stem.with_suffix(".aiff")
            spoken_path = stem.with_name(stem.name + "-spoken.wav")
            fitted_path = stem.with_suffix(".wav")
            text_path.write_text(cue + "\n", encoding="utf-8")
            run([say, "-v", voice, "-r", str(rate), "-f", str(text_path), "-o", str(aiff_path)])
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(aiff_path),
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    str(spoken_path),
                ]
            )
            spoken_duration = duration(spoken_path)
            target_spoken = max(0.5, allocation - 0.35)
            filters: list[str] = []
            if spoken_duration > target_spoken:
                filters.append(atempo_chain(spoken_duration / target_spoken))
            filters.extend([f"apad=pad_dur={allocation:.6f}", f"atrim=0:{allocation:.6f}"])
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(spoken_path),
                    "-af",
                    ",".join(filters),
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    str(fitted_path),
                ]
            )
            concat_lines.append(f"file '{fitted_path.resolve()}'")
            start = cursor
            end = cursor + allocation
            srt_blocks.append(f"{cue_number}\n{srt_time(start)} --> {srt_time(end)}\n{cue}\n")
            cursor = end
            cue_number += 1

    narration = work / "narration.wav"
    concat_path = cue_audio / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
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
            str(concat_path),
            "-c",
            "copy",
            str(narration),
        ]
    )
    captions = work / "captions.srt"
    captions.write_text("\n".join(srt_blocks), encoding="utf-8")
    return narration, captions


def build_video(timeline: dict[str, Any], out: Path, work: Path) -> Path:
    frames = out / "frames"
    segments = work / "segments"
    segments.mkdir(parents=True, exist_ok=True)
    concat_lines: list[str] = []
    for index, scene in enumerate(timeline["scenes"]):
        source = frames / scene["frame"]
        if not source.is_file():
            raise SystemExit(f"Missing video frame: {source}")
        destination = segments / f"{index:02d}-{scene['id']}.mp4"
        scene_duration = float(scene["durationSeconds"])
        direction = 1 if index % 2 == 0 else -1
        x_expr = "iw/2-(iw/zoom/2)" if direction > 0 else "(iw-iw/zoom)*(1-on/(30*18))"
        filter_graph = (
            "scale=2000:1125,"
            f"zoompan=z='min(zoom+0.000055,1.025)':x='{x_expr}':"
            "y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,"
            "format=yuv420p"
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-t",
                f"{scene_duration:.6f}",
                "-i",
                str(source),
                "-vf",
                filter_graph,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                str(destination),
            ]
        )
        concat_lines.append(f"file '{destination.resolve()}'")
    concat_path = segments / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    silent = work / "silent.mp4"
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
            str(concat_path),
            "-c",
            "copy",
            str(silent),
        ]
    )
    return silent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--voice", default="Daniel")
    parser.add_argument("--rate", type=int, default=148)
    args = parser.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is required")

    out = args.output_dir.resolve()
    work = out / "render"
    work.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    total = sum(float(item["durationSeconds"]) for item in timeline["scenes"])
    if not math.isclose(total, float(timeline["targetDurationSeconds"]), abs_tol=1e-9):
        raise SystemExit(f"Timeline duration mismatch: {total}")
    if timeline.get("candidateOnly") is not True or timeline.get("canClaimAGI") is not False:
        raise SystemExit("Timeline violates the claim boundary")

    narration, captions = build_narration(
        timeline,
        work,
        voice=args.voice,
        rate=args.rate,
    )
    silent = build_video(timeline, out, work)
    caption_overlay = work / "caption-overlay"
    manifest = run(
        [
            "python3",
            str(ROOT / "scripts/video/render_caption_overlay.py"),
            str(captions),
            str(caption_overlay),
            "--duration",
            f"{total:.6f}",
            "--font-size",
            "42",
            "--bottom-margin",
            "145",
        ],
        capture=True,
    )
    final = out / "ledgerlens-evidence-first.mp4"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(silent),
            "-i",
            str(narration),
            "-i",
            str(captions),
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            manifest,
            "-filter_complex",
            "[0:v][3:v]overlay=0:0:shortest=1[v]",
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-map",
            "2:0",
            "-t",
            f"{total:.6f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata",
            "title=LedgerLens Evidence-First Demo",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )

    render_manifest = {
        "schemaVersion": "1.0",
        "createdAtUtc": datetime.now(UTC).isoformat(),
        "targetDurationSeconds": total,
        "scenes": timeline["scenes"],
        "generatedSeconds": 0.0,
        "realProductProofSeconds": total,
        "generatedRatio": 0.0,
        "captionsBurnedIn": True,
        "selectableEnglishCaptionTrack": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "sourceDistinctions": {
            "publicSpace": "live host showing deterministic fixture replay",
            "github": "published live external-mutation receipt",
            "datahub": "published live DataHub OSS write-back and retrieval receipt",
            "aiVerification": "published live advisory rehearsal with deterministic authorization",
            "benchmark": "deterministic synthetic fixture benchmark",
        },
        "narration": {
            "voice": args.voice,
            "rate": args.rate,
            "path": str(narration.relative_to(ROOT)),
        },
        "captions": str(captions.relative_to(ROOT)),
        "finalVideo": str(final.relative_to(ROOT)),
    }
    (out / "render-manifest.json").write_text(
        json.dumps(render_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Rendered evidence-first video: {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
