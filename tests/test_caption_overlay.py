"""Tests for the libass-free burned-caption renderer."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/video/render_caption_overlay.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_caption_overlay", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_srt_and_render_transparent_assets(tmp_path: Path) -> None:
    module = _load_module()
    captions = tmp_path / "captions.srt"
    captions.write_text(
        """1
00:00:00,000 --> 00:00:01,500
First caption.

2
00:00:02,000 --> 00:00:03,000
Second caption
on two lines.
""",
        encoding="utf-8",
    )

    cues = module.parse_srt(captions)
    assert [(cue.start_seconds, cue.end_seconds) for cue in cues] == [
        (0.0, 1.5),
        (2.0, 3.0),
    ]

    manifest = module.build_overlay_assets(
        captions,
        tmp_path / "overlay",
        duration_seconds=4.0,
        width=640,
        height=360,
        font_size=24,
    )
    manifest_text = manifest.read_text(encoding="utf-8")
    assert "duration 1.500000" in manifest_text
    assert "duration 0.500000" in manifest_text
    assert "duration 1.000000" in manifest_text

    blank = Image.open(tmp_path / "overlay/blank.png").convert("RGBA")
    caption = Image.open(tmp_path / "overlay/caption-001.png").convert("RGBA")
    assert blank.getbbox() is None
    assert caption.getbbox() is not None


def test_srt_overlap_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    captions = tmp_path / "captions.srt"
    captions.write_text(
        """1
00:00:00,000 --> 00:00:02,000
First.

2
00:00:01,500 --> 00:00:03,000
Second.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlaps"):
        module.parse_srt(captions)


def test_overlay_rejects_caption_past_video_end(tmp_path: Path) -> None:
    module = _load_module()
    captions = tmp_path / "captions.srt"
    captions.write_text(
        """1
00:00:00,000 --> 00:00:03,000
Too long.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="shorter than the final caption"):
        module.build_overlay_assets(
            captions,
            tmp_path / "overlay",
            duration_seconds=2.0,
        )
