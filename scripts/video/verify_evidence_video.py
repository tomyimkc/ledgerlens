#!/usr/bin/env python3
"""Verify LedgerLens evidence-first duration, media, and claim/source boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MIN_DURATION = 160.0
MAX_DURATION = 175.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    video = args.video.resolve()
    if not video.is_file():
        parser.error(f"video does not exist: {video}")

    probe = json.loads(
        subprocess.run(
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
        ).stdout
    )
    streams = probe["streams"]
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
    subtitle_stream = next((item for item in streams if item.get("codec_type") == "subtitle"), None)
    errors: list[str] = []
    if not isinstance(video_stream, dict):
        errors.append("video stream is required")
        video_stream = {}
    duration = float(probe["format"]["duration"])
    video_duration = float(video_stream.get("duration", duration))
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    frame_rate = video_stream.get("avg_frame_rate")
    if not MIN_DURATION <= duration <= MAX_DURATION:
        errors.append(
            "duration must be 2:40–2:55 "
            f"({MIN_DURATION:.0f}–{MAX_DURATION:.0f}s); got {duration:.3f}s"
        )
    if abs(video_duration - duration) > 0.1:
        errors.append(
            "video stream duration must match container duration; "
            f"got video={video_duration:.3f}, container={duration:.3f}"
        )
    if (width, height) != (1920, 1080):
        errors.append(f"expected 1920x1080; got {width}x{height}")
    if video_stream.get("codec_name") != "h264":
        errors.append(f"expected H.264; got {video_stream.get('codec_name')}")
    if frame_rate not in {"30/1", "60/2"}:
        errors.append(f"expected 30 fps; got {frame_rate}")
    if not isinstance(audio_stream, dict):
        errors.append("English narration audio stream is required")
    if not isinstance(subtitle_stream, dict):
        errors.append("selectable English caption stream is required")

    manifest_path = video.parent / "render-manifest.json"
    evidence_path = video.parent / "public-evidence.json"
    manifest: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        errors.append("render-manifest.json is required")
    if evidence_path.is_file():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    else:
        errors.append("public-evidence.json is required")

    for label, payload in (("manifest", manifest), ("evidence", evidence)):
        if payload.get("candidateOnly") is not True:
            errors.append(f"{label} must preserve candidateOnly: true")
        if payload.get("canClaimAGI") is not False:
            errors.append(f"{label} must preserve canClaimAGI: false")
    if manifest.get("captionsBurnedIn") is not True:
        errors.append("captions must be burned in")
    if manifest.get("selectableEnglishCaptionTrack") is not True:
        errors.append("selectable English caption track must be declared")
    if float(manifest.get("generatedRatio", 1.0)) >= 0.15:
        errors.append("generated footage ratio must stay below 15%")

    health = evidence.get("publicSpace", {}).get("health", {})
    if health.get("mode") != "fixture" or health.get("externalMutations") is not False:
        errors.append("public Space must remain visibly classified as fixture/no external mutation")
    required_classes = {
        "github": "live-external-mutation",
        "datahub": "live-datahub-oss-writeback",
        "aiVerification": "live-ai-advisory-rehearsal",
        "benchmark": "deterministic-fixture-benchmark",
    }
    recorded = evidence.get("evidence", {})
    for key, expected in required_classes.items():
        actual = recorded.get(key, {}).get("evidenceClass")
        if actual != expected:
            errors.append(f"{key} evidence class must be {expected}; got {actual}")
    if recorded.get("benchmark", {}).get("liveDataHub") is not False:
        errors.append("benchmark must remain explicitly non-live")
    if recorded.get("aiVerification", {}).get("providerFamilyIndependenceClaimed") is not False:
        errors.append("AI receipt must not claim provider-family independence")

    receipt = {
        "schemaVersion": "1.0",
        "status": "PASS" if not errors else "FAIL",
        "verifiedAtUtc": datetime.now(UTC).isoformat(),
        "candidateOnly": True,
        "canClaimAGI": False,
        "video": {
            "path": video.name,
            "bytes": video.stat().st_size,
            "sha256": sha256(video),
            "durationSeconds": duration,
            "videoStreamDurationSeconds": video_duration,
            "width": width,
            "height": height,
            "frameRate": frame_rate,
            "videoCodec": video_stream.get("codec_name"),
            "audioCodec": (
                audio_stream.get("codec_name") if isinstance(audio_stream, dict) else None
            ),
            "captionCodec": (
                subtitle_stream.get("codec_name") if isinstance(subtitle_stream, dict) else None
            ),
        },
        "evidenceClasses": required_classes,
        "errors": errors,
        "manualChecksRequired": [
            "Narration and burned captions match the published receipts.",
            "The live-host/fixture-replay distinction remains readable.",
            "No secret, token, or private filesystem path is visible.",
            "The public upload plays in a clean/incognito browser.",
        ],
    }
    output = video.parent / "evidence-video-verification.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
