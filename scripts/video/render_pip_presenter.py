#!/usr/bin/env python3
"""Overlay a presenter talking-head PIP in the corner of the evidence-first demo.

Main stage remains product UI + real terminal coding I/O.
Corner shows the presenter's face track (from profile/lipsync source).
Presenter is labeled so judges know the main proof is the product, not the avatar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def run(cmd: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(cmd, check=True, text=True, capture_output=capture)
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--main",
        type=Path,
        default=Path("artifacts/video/evidence-first/ledgerlens-evidence-first.mp4"),
    )
    parser.add_argument(
        "--presenter",
        type=Path,
        default=Path("artifacts/video/presenter-pip/presenter-face-track.mp4"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/video/evidence-first/ledgerlens-evidence-pip.mp4"),
    )
    # Small top-right chip so captions + terminal text stay fully readable.
    parser.add_argument("--pip-width", type=int, default=200)
    parser.add_argument("--margin", type=int, default=24)
    parser.add_argument(
        "--position",
        choices=("top-right", "bottom-right"),
        default="top-right",
        help="Where to place the presenter PIP (top-right avoids covering captions).",
    )
    args = parser.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is required")
    if not args.main.is_file():
        raise SystemExit(f"missing main video: {args.main}")
    if not args.presenter.is_file():
        raise SystemExit(f"missing presenter track: {args.presenter}")

    main_dur = duration(args.main)
    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "pip-work"
    work.mkdir(parents=True, exist_ok=True)

    # Loop presenter to at least main duration, then trim.
    looped = work / "presenter-looped.mp4"
    # stream_loop enough times for 170s+
    loops = max(1, int(main_dur // max(1.0, duration(args.presenter))) + 2)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-stream_loop",
            str(loops),
            "-i",
            str(args.presenter),
            "-t",
            f"{main_dur:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(looped),
        ]
    )

    # Compact PIP + thin labels. Top-right keeps bottom captions and terminal text free.
    w = args.pip_width
    h = int(w * 1.12)
    m = args.margin
    from PIL import Image, ImageDraw, ImageFont  # local import keeps ffmpeg path lean

    def _badge(text: str, path: Path, width: int, height: int, fg: tuple[int, int, int]) -> None:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (0, 0, width - 1, height - 1),
            radius=8,
            fill=(11, 23, 40, 210),
            outline=(*fg, 255),
            width=2,
        )
        try:
            face = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 16
            )
        except OSError:
            face = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=face)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((width - tw) // 2, (height - th) // 2 - 1), text, font=face, fill=(*fg, 255))
        img.save(path)

    label_main = work / "label-main.png"
    label_pip = work / "label-pip.png"
    _badge("REAL UI + CODE", label_main, 180, 30, (255, 190, 90))
    _badge("PRESENTER", label_pip, 110, 26, (80, 220, 205))

    # Face overlay position
    if args.position == "top-right":
        face_xy = f"W-w-{m}:{m}+28"
        pip_label_xy = f"W-{w}-{m}:{m}"
        main_label_xy = f"{m}:{m}"
    else:
        face_xy = f"W-w-{m}:H-h-{m}-36"
        pip_label_xy = f"W-{w}-{m}:H-h-{m}-36-30"
        main_label_xy = f"{m}:{m}"

    filter_complex = (
        f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=0x50DCCD@0.9:t=3[face];"
        f"[0:v][face]overlay={face_xy}[base];"
        f"[base][2:v]overlay={main_label_xy}[withmain];"
        f"[withmain][3:v]overlay={pip_label_xy}[vout]"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(args.main),
            "-i",
            str(looped),
            "-i",
            str(label_main),
            "-i",
            str(label_pip),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            "-map",
            "0:s?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-shortest",
            str(out),
        ]
    )

    receipt = {
        "schemaVersion": "1.0",
        "status": "PASS",
        "builtAtUtc": datetime.now(UTC).isoformat(),
        "candidateOnly": True,
        "canClaimAGI": False,
        "mainVideo": {
            "path": str(args.main),
            "durationSeconds": main_dur,
            "sha256": sha256(args.main),
        },
        "presenter": {
            "path": str(args.presenter),
            "role": "corner-pip-talking-head",
            "source": "profile/lipsync face crop — visual presence only; product proof is main stage",
            "label": "PRESENTER · LIVE NARRATION",
        },
        "output": {
            "path": str(out),
            "bytes": out.stat().st_size,
            "sha256": sha256(out),
            "durationSeconds": duration(out),
        },
        "layout": {
            "main": "REAL UI + REAL CODING I/O",
            "pip": f"{args.position} {w}x{h}px margin {m}px",
        },
        "integrity": {
            "productProof": "main stage only",
            "presenterDoesNotSubstituteForProduct": True,
            "generatedProductImitation": False,
        },
    }
    receipt_path = out.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    print(f"PIP video: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
