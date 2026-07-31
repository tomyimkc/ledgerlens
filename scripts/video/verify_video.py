#!/usr/bin/env python3
"""Verify demo-video technical constraints and write a sanitized receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    video = args.video.resolve()
    if not video.is_file():
        parser.error(f"video does not exist: {video}")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe: dict[str, Any] = json.loads(result.stdout)
    streams = probe.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
    subtitle_stream = next((item for item in streams if item.get("codec_type") == "subtitle"), None)
    if not isinstance(video_stream, dict):
        raise SystemExit("No video stream found.")

    duration = float(probe["format"]["duration"])
    video_duration = float(video_stream.get("duration", duration))
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    codec = video_stream.get("codec_name")
    errors: list[str] = []
    if duration >= 180:
        errors.append(f"duration must be under 180 seconds; got {duration:.3f}")
    if abs(video_duration - duration) > 0.1:
        errors.append(
            "video stream duration must match container duration; "
            f"got video={video_duration:.3f}, container={duration:.3f}"
        )
    if (width, height) != (1920, 1080):
        errors.append(f"expected 1920x1080; got {width}x{height}")
    if codec != "h264":
        errors.append(f"expected H.264; got {codec}")
    if not isinstance(audio_stream, dict):
        errors.append("English narration audio stream is required")
    if not isinstance(subtitle_stream, dict):
        errors.append("selectable English caption stream is required")

    manifest_path = video.parent / "render-manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        errors.append("render-manifest.json is required")
    generated_ratio = float(manifest.get("generatedRatio", 0.0))
    if generated_ratio >= 0.15:
        errors.append(f"generated footage must be below 15%; got {generated_ratio:.3%}")
    if manifest.get("captionsBurnedIn") is not True:
        errors.append("English captions must be burned into the video")

    receipt = {
        "schemaVersion": "1.0",
        "status": "PASS" if not errors else "FAIL",
        "verifiedAtUtc": datetime.now(UTC).isoformat(),
        "candidateOnly": True,
        "canClaimAGI": False,
        "productProofPolicy": "real UI capture required; synthetic imitation forbidden",
        "video": {
            "path": video.name,
            "bytes": video.stat().st_size,
            "sha256": sha256(video),
            "durationSeconds": duration,
            "videoStreamDurationSeconds": video_duration,
            "width": width,
            "height": height,
            "codec": codec,
            "audioCodec": (
                audio_stream.get("codec_name") if isinstance(audio_stream, dict) else None
            ),
            "captionCodec": (
                subtitle_stream.get("codec_name") if isinstance(subtitle_stream, dict) else None
            ),
            "captionsBurnedIn": manifest.get("captionsBurnedIn") is True,
            "generatedRatio": generated_ratio,
        },
        "errors": errors,
        "manualChecksRequired": [
            "English captions and narration are accurate.",
            "No secrets or private data are visible.",
            "Generated concept clips are labeled.",
            "All functionality claims use real UI capture.",
            "Public upload works in an incognito browser.",
        ],
    }
    receipt_path = video.parent / "render-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if errors:
        return 1
    print(f"Video verification passed; receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
