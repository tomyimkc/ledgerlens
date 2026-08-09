#!/usr/bin/env python3
"""Package the disclosed native-Grok presenter cut with selectable captions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REMOTION = (
    ROOT
    / "artifacts"
    / "video"
    / "native-grok"
    / "remotion"
    / "out"
    / "ledgerlens-datahub-demo.mp4"
)
DEFAULT_CUES = ROOT / "artifacts" / "video" / "native-grok" / "remotion" / "src" / "cues.json"
DEFAULT_STORY = ROOT / "artifacts" / "video" / "native-grok" / "remotion" / "src" / "story.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "video" / "native-grok" / "ledgerlens-policy-sealed-final.mp4"
FORBIDDEN_PRESENTATION = re.compile(r"\bautonomous\b", re.IGNORECASE)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_REMOTION)
    parser.add_argument("--cues", type=Path, default=DEFAULT_CUES)
    parser.add_argument("--story", type=Path, default=DEFAULT_STORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scene-seconds", type=float, default=15.0)
    return parser.parse_args()


def _timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _write_srt(
    cues: dict[str, list[dict[str, Any]]],
    scene_ids: list[str],
    *,
    scene_seconds: float,
    output: Path,
) -> int:
    blocks: list[str] = []
    index = 1
    for scene_index, scene_id in enumerate(scene_ids):
        offset = scene_index * scene_seconds
        for cue in cues.get(scene_id, []):
            start = offset + float(cue["s"])
            end = offset + float(cue["e"])
            text = str(cue["t"]).strip()
            blocks.append(f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
            index += 1
    output.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    return index - 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = _arguments()
    if not args.input.is_file():
        raise SystemExit(f"missing Remotion render: {args.input}")
    story = json.loads(args.story.read_text(encoding="utf-8"))
    cues = json.loads(args.cues.read_text(encoding="utf-8"))
    serialized_copy = json.dumps(
        {"story": story, "cues": cues},
        ensure_ascii=False,
        sort_keys=True,
    )
    if FORBIDDEN_PRESENTATION.search(serialized_copy):
        raise SystemExit("stale Autonomous presentation wording remains")
    if story.get("candidateOnly") is not True:
        raise SystemExit("story must keep candidateOnly: true")
    if story.get("canClaimAGI") is not False:
        raise SystemExit("story must keep canClaimAGI: false")
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise SystemExit("story must contain scenes")
    scene_ids = [str(scene["id"]) for scene in scenes]
    proof_images = [
        str(scene["panel"]["image"])
        for scene in scenes
        if isinstance(scene.get("panel"), dict) and isinstance(scene["panel"].get("image"), str)
    ]
    if len(proof_images) < 5:
        raise SystemExit("at least five real product-evidence panels are required")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    captions = args.output.with_suffix(".en.srt")
    cue_count = _write_srt(
        cues,
        scene_ids,
        scene_seconds=args.scene_seconds,
        output=captions,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(args.input),
            "-i",
            str(captions),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-map",
            "1:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata:s:s:0",
            "title=English",
            "-metadata",
            "title=LedgerLens — Policy-Sealed Incident Commander",
            "-movflags",
            "+faststart",
            str(args.output),
        ],
        check=True,
    )
    manifest = {
        "schemaVersion": "ledgerlens.native-grok-video.v1",
        "builtAtUtc": datetime.now(UTC).isoformat(),
        "title": "LedgerLens — Policy-Sealed Incident Commander",
        "candidateOnly": True,
        "canClaimAGI": False,
        "generatedPresenter": True,
        "generatedPresenterDisclosureVisible": True,
        "nativeGrokAudio": True,
        "captionsBurnedIn": True,
        "selectableEnglishCaptions": True,
        "captionCueCount": cue_count,
        "productEvidencePolicy": (
            "Generated presenter is explicitly labeled; functionality proof panels use "
            "captured LedgerLens UI or receipt-derived frames."
        ),
        "productEvidencePanels": proof_images,
        "limitations": [
            "The presenter footage and voice are AI-generated.",
            "The public application shown in product panels is a fixture replay with "
            "external mutations disabled.",
            "E-16 provider execution and E-07 DataHub write/read remain separate runs.",
            "The video does not establish incident causality, recovery, validated uplift, "
            "production reliability, or AGI.",
        ],
        "output": {
            "path": str(args.output),
            "bytes": args.output.stat().st_size,
            "sha256": _sha256(args.output),
        },
    }
    manifest_path = args.output.parent / "native-grok-render-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "manifest": str(manifest_path),
                "captionCueCount": cue_count,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
