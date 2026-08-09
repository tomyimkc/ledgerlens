#!/usr/bin/env python3
"""Verify the disclosed policy-sealed native-Grok contest video."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

FORBIDDEN_PRESENTATION = re.compile(r"\bautonomous\b", re.IGNORECASE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Defaults to native-grok-render-manifest.json beside the video.",
    )
    args = parser.parse_args()
    video = args.video.resolve()
    manifest_path = (
        args.manifest.resolve()
        if args.manifest is not None
        else video.parent / "native-grok-render-manifest.json"
    )
    if not video.is_file():
        raise SystemExit(f"video does not exist: {video}")
    if not manifest_path.is_file():
        raise SystemExit(f"manifest does not exist: {manifest_path}")

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
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    streams = probe.get("streams", [])
    video_stream = next(
        (item for item in streams if item.get("codec_type") == "video"),
        {},
    )
    audio_stream = next(
        (item for item in streams if item.get("codec_type") == "audio"),
        {},
    )
    subtitle_stream = next(
        (item for item in streams if item.get("codec_type") == "subtitle"),
        {},
    )
    duration = float(probe.get("format", {}).get("duration", 0))
    errors: list[str] = []
    if not 90 <= duration < 180:
        errors.append(f"duration must be 90–179.999 seconds; got {duration:.3f}")
    if (
        int(video_stream.get("width", 0)),
        int(video_stream.get("height", 0)),
    ) != (1920, 1080):
        errors.append("video must be 1920x1080")
    if video_stream.get("codec_name") != "h264":
        errors.append("video codec must be H.264")
    if audio_stream.get("codec_name") != "aac":
        errors.append("audio codec must be AAC")
    if subtitle_stream.get("codec_name") not in {"mov_text", "subrip"}:
        errors.append("selectable English captions are required")
    if manifest.get("candidateOnly") is not True:
        errors.append("manifest must keep candidateOnly: true")
    if manifest.get("canClaimAGI") is not False:
        errors.append("manifest must keep canClaimAGI: false")
    if manifest.get("generatedPresenter") is not True:
        errors.append("manifest must disclose the generated presenter")
    if manifest.get("generatedPresenterDisclosureVisible") is not True:
        errors.append("generated presenter disclosure must be visible")
    if manifest.get("captionsBurnedIn") is not True:
        errors.append("burned English captions are required")
    if manifest.get("selectableEnglishCaptions") is not True:
        errors.append("manifest must record selectable English captions")
    panels = manifest.get("productEvidencePanels")
    if not isinstance(panels, list) or len(panels) < 5:
        errors.append("at least five product-evidence panels are required")
    if FORBIDDEN_PRESENTATION.search(json.dumps(manifest, ensure_ascii=False, sort_keys=True)):
        errors.append("stale Autonomous presentation wording remains")
    expected_digest = manifest.get("output", {}).get("sha256")
    actual_digest = _sha256(video)
    if expected_digest != actual_digest:
        errors.append("manifest video digest does not match")

    receipt = {
        "schemaVersion": "ledgerlens.native-grok-video-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "verifiedAtUtc": datetime.now(UTC).isoformat(),
        "candidateOnly": True,
        "canClaimAGI": False,
        "video": {
            "path": str(video),
            "bytes": video.stat().st_size,
            "sha256": actual_digest,
            "durationSeconds": duration,
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "videoCodec": video_stream.get("codec_name"),
            "audioCodec": audio_stream.get("codec_name"),
            "captionCodec": subtitle_stream.get("codec_name"),
        },
        "errors": errors,
        "manualChecksRequired": [
            "Presenter disclosure is legible throughout.",
            "Proof panels show the intended public UI or receipt-derived frame.",
            "Captions match the audible wording closely enough for judging.",
            "No secret, private destination, or account-only data is visible.",
            "The public upload title and Devpost embed use Policy-Sealed wording.",
        ],
    }
    receipt_path = video.parent / "native-grok-video-verification.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
