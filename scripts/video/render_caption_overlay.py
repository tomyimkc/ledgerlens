#!/usr/bin/env python3
"""Render SRT cues as transparent PNG overlays for FFmpeg builds without libass."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TIMING_RE = re.compile(
    r"^(?P<sh>\d{2,}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})"
    r"\s+-->\s+"
    r"(?P<eh>\d{2,}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})$"
)


@dataclass(frozen=True)
class CaptionCue:
    start_seconds: float
    end_seconds: float
    text: str


def _timestamp_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_srt(path: Path) -> list[CaptionCue]:
    """Parse the small, deterministic SRT subset used by the demo renderer."""

    cues: list[CaptionCue] = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines()]
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2:
            raise ValueError(f"caption block {block_number} is incomplete")
        match = TIMING_RE.fullmatch(lines[0].strip())
        if match is None:
            raise ValueError(f"caption block {block_number} has an invalid timing line")
        groups = match.groupdict()
        start = _timestamp_seconds(groups["sh"], groups["sm"], groups["ss"], groups["sms"])
        end = _timestamp_seconds(groups["eh"], groups["em"], groups["es"], groups["ems"])
        if end <= start:
            raise ValueError(f"caption block {block_number} must end after it starts")
        if cues and start < cues[-1].end_seconds:
            raise ValueError(f"caption block {block_number} overlaps the previous cue")
        text = "\n".join(line.strip() for line in lines[1:] if line.strip())
        if not text:
            raise ValueError(f"caption block {block_number} has no text")
        cues.append(CaptionCue(start, end, text))
    if not cues:
        raise ValueError("caption file contains no cues")
    return cues


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _wrap_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = line.split()
    if not words:
        return [""]
    wrapped: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font, stroke_width=2)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            wrapped.append(current)
            current = word
    wrapped.append(current)
    return wrapped


def render_caption(
    cue: CaptionCue,
    path: Path,
    *,
    width: int,
    height: int,
    font_size: int,
) -> None:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_font(font_size)
    lines: list[str] = []
    for source_line in cue.text.splitlines():
        lines.extend(_wrap_line(draw, source_line, font, width - 260))

    line_gap = max(8, font_size // 5)
    measured = [draw.textbbox((0, 0), line, font=font, stroke_width=3) for line in lines]
    line_heights = [box[3] - box[1] for box in measured]
    total_height = sum(line_heights) + line_gap * max(0, len(lines) - 1)
    padding_x = 34
    padding_y = 22
    box_width = max(box[2] - box[0] for box in measured) + padding_x * 2
    box_height = total_height + padding_y * 2
    left = (width - box_width) // 2
    top = height - 58 - box_height
    draw.rounded_rectangle(
        (left, top, left + box_width, top + box_height),
        radius=18,
        fill=(0, 0, 0, 205),
        outline=(255, 255, 255, 90),
        width=2,
    )
    y = top + padding_y
    for line, box, line_height in zip(lines, measured, line_heights, strict=True):
        line_width = box[2] - box[0]
        draw.text(
            ((width - line_width) / 2, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=3,
            stroke_fill=(0, 0, 0, 255),
        )
        y += line_height + line_gap
    image.save(path)


def _concat_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace("'", "\\'")


def build_overlay_assets(
    captions: Path,
    output_dir: Path,
    *,
    duration_seconds: float,
    width: int = 1920,
    height: int = 1080,
    font_size: int = 46,
) -> Path:
    cues = parse_srt(captions)
    if duration_seconds < cues[-1].end_seconds:
        raise ValueError(
            "video duration is shorter than the final caption "
            f"({duration_seconds:.3f} < {cues[-1].end_seconds:.3f})"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    blank = output_dir / "blank.png"
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(blank)

    entries: list[tuple[Path, float]] = []
    cursor = 0.0
    for index, cue in enumerate(cues, start=1):
        if cue.start_seconds > cursor:
            entries.append((blank, cue.start_seconds - cursor))
        image_path = output_dir / f"caption-{index:03d}.png"
        render_caption(
            cue,
            image_path,
            width=width,
            height=height,
            font_size=font_size,
        )
        entries.append((image_path, cue.end_seconds - cue.start_seconds))
        cursor = cue.end_seconds
    if cursor < duration_seconds:
        entries.append((blank, duration_seconds - cursor))

    manifest = output_dir / "captions.ffconcat"
    manifest_lines = ["ffconcat version 1.0"]
    for image_path, entry_duration in entries:
        manifest_lines.append(f"file '{_concat_path(image_path)}'")
        manifest_lines.append(f"duration {entry_duration:.6f}")
    manifest_lines.append(f"file '{_concat_path(entries[-1][0])}'")
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    metadata = {
        "schemaVersion": "1.0",
        "source": str(captions),
        "durationSeconds": duration_seconds,
        "width": width,
        "height": height,
        "cues": [asdict(cue) for cue in cues],
        "manifest": str(manifest),
    }
    (output_dir / "caption-overlay.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("captions", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--duration", required=True, type=float)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--font-size", type=int, default=46)
    args = parser.parse_args()
    manifest = build_overlay_assets(
        args.captions,
        args.output_dir,
        duration_seconds=args.duration,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
