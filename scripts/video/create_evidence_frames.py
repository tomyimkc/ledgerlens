#!/usr/bin/env python3
"""Create polished evidence-first video frames from public captures and receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

WIDTH = 1920
HEIGHT = 1080
BACKGROUND = (5, 11, 22)
PANEL = (12, 24, 42)
PANEL_2 = (15, 31, 53)
INK = (239, 247, 255)
MUTED = (164, 183, 203)
TEAL = (80, 220, 205)
CYAN = (90, 190, 255)
AMBER = (255, 190, 90)
GREEN = (99, 226, 148)
RED = (255, 111, 122)
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/video/evidence-first"
FRAMES = OUT / "frames"
SHOTS = OUT / "screenshots"
RECEIPTS = OUT / "public-receipts"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        candidate = Path(name)
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((-240, -360, 900, 780), fill=(33, 116, 139, 85))
    draw.ellipse((1230, 500, 2200, 1450), fill=(64, 46, 140, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    image.paste(glow, mask=glow.getchannel("A"))
    return image


def rounded_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int] = PANEL,
    outline: tuple[int, int, int] = (42, 71, 96),
    radius: int = 28,
) -> None:
    ImageDraw.Draw(image).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    *,
    size: int,
    color: tuple[int, int, int] = INK,
    bold: bool = False,
    max_width: int | None = None,
    spacing: int = 8,
) -> int:
    selected = font(size, bold=bold)
    lines: list[str] = []
    for source in value.splitlines() or [""]:
        if max_width is None:
            lines.append(source)
            continue
        words = source.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if draw.textlength(candidate, font=selected) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    draw.multiline_text(xy, "\n".join(lines), font=selected, fill=color, spacing=spacing)
    bbox = draw.multiline_textbbox(xy, "\n".join(lines), font=selected, spacing=spacing)
    return bbox[3]


def badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    *,
    color: tuple[int, int, int] = TEAL,
) -> None:
    selected = font(24, bold=True)
    width = int(draw.textlength(value, font=selected)) + 38
    x, y = xy
    draw.rounded_rectangle((x, y, x + width, y + 46), radius=23, fill=(*color, 34), outline=color)
    draw.text((x + 19, y + 9), value, font=selected, fill=color)


def header(
    image: Image.Image,
    *,
    eyebrow: str,
    title_value: str,
    subtitle: str,
    evidence_badge: str,
    badge_color: tuple[int, int, int] = TEAL,
) -> None:
    draw = ImageDraw.Draw(image)
    text(draw, (90, 54), eyebrow, size=24, color=badge_color, bold=True)
    text(draw, (90, 91), title_value, size=54, bold=True, max_width=1260)
    text(draw, (92, 164), subtitle, size=26, color=MUTED, max_width=1420)
    badge(draw, (1510, 70), evidence_badge, color=badge_color)


def claim_strip(image: Image.Image, label: str) -> None:
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (80, 980, 1840, 1043),
        radius=18,
        fill=(5, 15, 27),
        outline=(49, 78, 100),
        width=2,
    )
    text(draw, (108, 995), label, size=23, color=MUTED, bold=True)
    text(draw, (1220, 995), "candidateOnly: true", size=23, color=TEAL, bold=True)
    text(draw, (1530, 995), "canClaimAGI: false", size=23, color=AMBER, bold=True)


def screenshot_frame(
    source: Path,
    destination: Path,
    *,
    eyebrow: str,
    title_value: str,
    subtitle: str,
    evidence_badge: str,
    claim_label: str,
    crop_y: float = 0.5,
) -> None:
    image = background()
    header(
        image,
        eyebrow=eyebrow,
        title_value=title_value,
        subtitle=subtitle,
        evidence_badge=evidence_badge,
    )
    rounded_panel(image, (80, 238, 1840, 944))
    captured = Image.open(source).convert("RGB")
    captured = ImageOps.fit(
        captured,
        (1700, 646),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, crop_y),
    )
    mask = Image.new("L", captured.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, captured.width, captured.height),
        radius=20,
        fill=255,
    )
    image.paste(captured, (110, 268), mask)
    claim_strip(image, claim_label)
    image.save(destination)


def receipt_payload(name: str) -> dict[str, Any]:
    return json.loads((RECEIPTS / name).read_text(encoding="utf-8"))


def value_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    *,
    color: tuple[int, int, int] = TEAL,
    value_size: int = 35,
) -> None:
    draw.rounded_rectangle(box, radius=22, fill=PANEL_2, outline=(42, 71, 96), width=2)
    x1, y1, x2, _ = box
    text(draw, (x1 + 26, y1 + 22), label, size=20, color=MUTED, bold=True)
    text(
        draw,
        (x1 + 26, y1 + 61),
        value,
        size=value_size,
        color=color,
        bold=True,
        max_width=x2 - x1 - 52,
    )


def title_frame(destination: Path) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    badge(draw, (90, 75), "EVIDENCE FIRST")
    text(draw, (88, 166), "LedgerLens", size=88, bold=True)
    text(
        draw,
        (92, 278),
        "Autonomous Data Incident Commander",
        size=44,
        color=CYAN,
        bold=True,
    )
    text(
        draw,
        (92, 354),
        "DataHub context → advisory plan → deterministic gate → receipted work → durable handoff",
        size=30,
        color=MUTED,
        max_width=1500,
    )
    labels = [
        ("LIVE HOST", "fixture replay", TEAL),
        ("LIVE GITHUB", "issue created + closed", GREEN),
        ("LIVE DATAHUB", "document write + retrieval", CYAN),
        ("BENCHMARK", "synthetic + deterministic", AMBER),
    ]
    x = 90
    for heading, detail, color in labels:
        rounded_panel(image, (x, 535, x + 405, 735), fill=PANEL_2, outline=color)
        text(draw, (x + 28, 567), heading, size=24, color=color, bold=True)
        text(draw, (x + 28, 619), detail, size=29, bold=True, max_width=345)
        x += 435
    text(
        draw,
        (92, 820),
        "The evidence class changes on screen before the claim changes.",
        size=34,
        color=INK,
        bold=True,
    )
    claim_strip(image, "PUBLIC DEMO · PUBLISHED RECEIPTS · EXPLICIT LIMITATIONS")
    image.save(destination)


def fixture_execution_frame(destination: Path) -> None:
    image = background()
    header(
        image,
        eyebrow="REPLAY EXECUTION",
        title_value="Full state transition, visibly synthetic receipts",
        subtitle=(
            "The hosted replay demonstrates orchestration without presenting "
            "fixture actions as provider state."
        ),
        evidence_badge="FIXTURE RECEIPTS",
        badge_color=AMBER,
    )
    for source, box in (
        (SHOTS / "04-space-fixture-actions.png", (80, 250, 930, 760)),
        (SHOTS / "05-space-writeback.png", (970, 250, 1840, 560)),
        (SHOTS / "06-space-memory.png", (970, 590, 1840, 920)),
    ):
        rounded_panel(image, box, fill=PANEL_2)
        shot = Image.open(source).convert("RGB")
        width = box[2] - box[0] - 28
        height = box[3] - box[1] - 28
        shot = ImageOps.fit(shot, (width, height), Image.Resampling.LANCZOS)
        image.paste(shot, (box[0] + 14, box[1] + 14))
    draw = ImageDraw.Draw(image)
    badge(draw, (116, 278), "fixture://", color=AMBER)
    claim_strip(image, "LIVE HOST · FIXTURE ACTIONS · NO EXTERNAL MUTATION")
    image.save(destination)


def github_frame(destination: Path) -> None:
    receipt = receipt_payload("github-live-action-receipt.json")
    image = background()
    header(
        image,
        eyebrow="PUBLISHED RECEIPT 1 OF 3",
        title_value="Real GitHub issue creation and closure",
        subtitle=(
            "The signed adapter created public issue #3, received HTTP 201, "
            "and closed it as completed."
        ),
        evidence_badge="LIVE EXTERNAL MUTATION",
        badge_color=GREEN,
    )
    rounded_panel(image, (80, 245, 1095, 930))
    issue = Image.open(SHOTS / "07-github-issue.png").convert("RGB")
    issue = ImageOps.fit(issue, (955, 625), Image.Resampling.LANCZOS, centering=(0.5, 0.18))
    image.paste(issue, (110, 275))
    draw = ImageDraw.Draw(image)
    value_card(draw, (1130, 250, 1840, 410), "PROVIDER RESULT", "executed · HTTP 201", color=GREEN)
    value_card(draw, (1130, 435, 1470, 590), "ISSUE", "#3", color=CYAN, value_size=52)
    value_card(
        draw,
        (1500, 435, 1840, 590),
        "CLOSURE",
        receipt["closure"]["state"],
        color=GREEN,
        value_size=42,
    )
    value_card(
        draw,
        (1130, 615, 1840, 775),
        "PUBLIC RECEIPT",
        "benchmarks/incident_commander/\ngithub-live-action-receipt.json",
        color=INK,
        value_size=24,
    )
    text(
        draw,
        (1155, 815),
        "LIMIT: proves issue creation and closure, not incident causality or recovery.",
        size=25,
        color=AMBER,
        bold=True,
        max_width=640,
    )
    claim_strip(image, "REAL GITHUB RECEIPT · SLACK / PAGERDUTY / JIRA NOT CLAIMED LIVE")
    image.save(destination)


def datahub_frame(destination: Path) -> None:
    receipt = receipt_payload("datahub-live-writeback-receipt.json")
    image = background()
    header(
        image,
        eyebrow="PUBLISHED RECEIPT 2 OF 3",
        title_value="Controlled DataHub write-back, then MCP retrieval",
        subtitle=(
            "The allowlisted save_document call produced a document URN "
            "that the next-agent path retrieved."
        ),
        evidence_badge="LIVE DATAHUB OSS",
        badge_color=CYAN,
    )
    draw = ImageDraw.Draw(image)
    value_card(draw, (80, 255, 580, 420), "MUTATION", "save_document", color=CYAN)
    value_card(draw, (610, 255, 1110, 420), "STATUS", receipt["status"], color=GREEN)
    value_card(
        draw,
        (1140, 255, 1840, 420),
        "MCP RETRIEVAL",
        "get_entities · retrieved",
        color=TEAL,
        value_size=31,
    )
    rounded_panel(image, (80, 460, 1840, 745), fill=PANEL_2)
    text(draw, (112, 490), "CREATED DATAHUB DOCUMENT URN", size=21, color=MUTED, bold=True)
    text(
        draw,
        (112, 542),
        receipt["result"]["urn"],
        size=34,
        color=CYAN,
        bold=True,
        max_width=1650,
    )
    text(
        draw,
        (112, 635),
        receipt["result"]["message"],
        size=27,
        color=INK,
        max_width=1650,
    )
    rounded_panel(image, (80, 780, 1840, 930), fill=(29, 25, 25), outline=AMBER)
    text(draw, (112, 806), "LIMITATION", size=21, color=AMBER, bold=True)
    text(
        draw,
        (112, 846),
        (
            "Catalog persistence is not incident recovery. "
            "Slack, PagerDuty, and Jira were not executed live."
        ),
        size=28,
        color=INK,
        bold=True,
        max_width=1640,
    )
    claim_strip(image, "EXTERNAL MUTATION: TRUE · RETRIEVAL: TRUE · RECOVERY: UNPROVEN")
    image.save(destination)


def ai_frame(destination: Path) -> None:
    receipt = receipt_payload("ai-verification-receipt.json")
    verification = receipt["verification"]
    models = receipt["models"]
    image = background()
    header(
        image,
        eyebrow="PUBLISHED RECEIPT 3 OF 3",
        title_value="AI advises; deterministic policy authorizes",
        subtitle=(
            "The live rehearsal records one planner, two verifier variants, "
            "quorum, and the exact authorization verdict."
        ),
        evidence_badge="LIVE AI REHEARSAL",
        badge_color=TEAL,
    )
    draw = ImageDraw.Draw(image)
    value_card(
        draw,
        (80, 255, 600, 430),
        "PLANNER",
        str(models["planner"]),
        color=CYAN,
        value_size=31,
    )
    verifier_names = "\n".join(str(item) for item in models["verifiers"])
    value_card(
        draw,
        (630, 255, 1230, 430),
        "VERIFIER VARIANTS",
        verifier_names,
        color=TEAL,
        value_size=27,
    )
    value_card(
        draw,
        (1260, 255, 1840, 430),
        "DETERMINISTIC VERDICT",
        "AUTHORIZED",
        color=GREEN,
        value_size=38,
    )
    rounded_panel(image, (80, 475, 1840, 775), fill=PANEL_2)
    metrics = [
        ("Approvals", f"{verification['approvals']}"),
        ("Quorum", f"{verification['quorum']}"),
        ("Confidence", f"{verification['aggregate_confidence']:.2f}"),
        ("Threshold", f"{verification['confidence_threshold']:.2f}"),
    ]
    x = 120
    for label, value in metrics:
        text(draw, (x, 520), label.upper(), size=20, color=MUTED, bold=True)
        text(draw, (x, 570), value, size=62, color=GREEN, bold=True)
        x += 420
    text(
        draw,
        (120, 690),
        "Provider-family independence claimed: false",
        size=29,
        color=AMBER,
        bold=True,
    )
    text(
        draw,
        (80, 825),
        (
            "Model outputs remain advisory. Deterministic policy checks the "
            "exact plan, evidence IDs, targets, parameters, and risk."
        ),
        size=29,
        color=INK,
        bold=True,
        max_width=1740,
    )
    claim_strip(image, "AI SELF-AUTHORIZATION: FORBIDDEN · DETERMINISTIC GATE: AUTHORITATIVE")
    image.save(destination)


def benchmark_frame(destination: Path) -> None:
    receipt = receipt_payload("context-ablation-receipt.json")
    comparison = receipt["comparison"]
    image = background()
    header(
        image,
        eyebrow="DETERMINISTIC CONTEXT ABLATION",
        title_value="DataHub-shaped context ON versus OFF",
        subtitle=(
            "120 synthetic assets · 24 scenarios · offline deterministic scorer · no LLM judge"
        ),
        evidence_badge="FIXTURE BENCHMARK",
        badge_color=AMBER,
    )
    draw = ImageDraw.Draw(image)
    metrics = [
        ("Owner accuracy", "ownerAccuracy", True),
        ("Blast-radius recall", "blastRadiusRecall", True),
        ("Unsupported claims", "unsupportedClaimRate", False),
        ("Unsafe actions", "unsafeActionRate", False),
        ("Plan completeness", "actionPlanCompleteness", True),
    ]
    base_y = 292
    for index, (label, key, higher) in enumerate(metrics):
        item = comparison[key]
        off = float(item["contextOffMean"])
        on = float(item["contextOnMean"])
        y = base_y + index * 120
        text(draw, (90, y), label, size=25, bold=True)
        draw.rounded_rectangle((470, y + 4, 1110, y + 36), radius=16, fill=(28, 43, 62))
        draw.rounded_rectangle(
            (470, y + 4, 470 + max(5, int(640 * off)), y + 36),
            radius=16,
            fill=AMBER,
        )
        draw.rounded_rectangle((1150, y + 4, 1790, y + 36), radius=16, fill=(28, 43, 62))
        draw.rounded_rectangle(
            (1150, y + 4, 1150 + max(5, int(640 * on)), y + 36),
            radius=16,
            fill=TEAL,
        )
        text(draw, (470, y + 52), f"OFF {off:.3f}", size=20, color=AMBER, bold=True)
        text(draw, (1150, y + 52), f"ON {on:.3f}", size=20, color=TEAL, bold=True)
        direction = "higher is preferred" if higher else "lower is preferred"
        text(draw, (1530, y + 52), direction, size=18, color=MUTED)
    rounded_panel(image, (80, 900, 1840, 964), fill=(29, 25, 25), outline=AMBER)
    text(
        draw,
        (105, 915),
        (
            "LIMIT: synthetic fixture, no live DataHub, no external validation, "
            "no proven model uplift."
        ),
        size=25,
        color=AMBER,
        bold=True,
    )
    claim_strip(image, "PASS IS A HARNESS RESULT · NOT PRODUCTION SAFETY OR AGI EVIDENCE")
    image.save(destination)


def close_frame(destination: Path) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    badge(draw, (90, 75), "CANDIDATE ONLY", color=TEAL)
    text(draw, (90, 180), "Real receipts where real work occurred.", size=58, bold=True)
    text(draw, (90, 260), "Visible fixtures everywhere else.", size=58, bold=True, color=CYAN)
    rounded_panel(image, (90, 410, 1830, 735), fill=PANEL_2, outline=TEAL)
    text(
        draw,
        (140, 455),
        "Public Space",
        size=24,
        color=MUTED,
        bold=True,
    )
    text(
        draw,
        (140, 500),
        "tomyimkc-ledgerlens-incident-commander.hf.space",
        size=38,
        color=TEAL,
        bold=True,
    )
    text(draw, (140, 590), "Public repository", size=24, color=MUTED, bold=True)
    text(
        draw,
        (140, 635),
        "github.com/tomyimkc/ledgerlens",
        size=38,
        color=CYAN,
        bold=True,
    )
    text(
        draw,
        (90, 820),
        "No claim of root cause, recovery, production readiness, validated uplift, or AGI.",
        size=31,
        color=AMBER,
        bold=True,
        max_width=1700,
    )
    claim_strip(image, "candidateOnly: true · canClaimAGI: false")
    image.save(destination)


def main() -> int:
    required = [
        OUT / "public-evidence.json",
        SHOTS / "01-space-hero.png",
        SHOTS / "02-space-context.png",
        SHOTS / "03-space-plan-verifier.png",
        SHOTS / "04-space-fixture-actions.png",
        SHOTS / "05-space-writeback.png",
        SHOTS / "06-space-memory.png",
        SHOTS / "07-github-issue.png",
    ]
    missing = [str(item) for item in required if not item.is_file()]
    if missing:
        raise SystemExit("Missing capture inputs:\n" + "\n".join(missing))
    FRAMES.mkdir(parents=True, exist_ok=True)

    title_frame(FRAMES / "00-title.png")
    screenshot_frame(
        SHOTS / "01-space-hero.png",
        FRAMES / "01-live-space.png",
        eyebrow="PUBLIC HUGGING FACE SPACE",
        title_value="Live host, deterministic fixture replay",
        subtitle=(
            "Reachable public product surface with external mutations disabled "
            "and the replay boundary visible."
        ),
        evidence_badge="LIVE HOST · FIXTURE",
        claim_label="MODE: FIXTURE · EXTERNAL MUTATIONS: FALSE",
        crop_y=0.08,
    )
    screenshot_frame(
        SHOTS / "02-space-context.png",
        FRAMES / "02-datahub-context.png",
        eyebrow="DATAHUB OPERATING CONTEXT",
        title_value="Ground the owner and blast radius before acting",
        subtitle=(
            "Entity, tier, lineage, and evidence pointers are recorded metadata—not causal proof."
        ),
        evidence_badge="FIXTURE CONTEXT",
        claim_label="LINEAGE: METADATA-DERIVED · ROOT CAUSE / IMPACT / RECOVERY: UNKNOWN",
        crop_y=0.5,
    )
    screenshot_frame(
        SHOTS / "03-space-plan-verifier.png",
        FRAMES / "03-policy-gate.png",
        eyebrow="PLAN + VERIFIER + DETERMINISTIC GATE",
        title_value="AI proposes and reviews; policy holds authority",
        subtitle=(
            "The exact plan fingerprint binds advisory votes to allowlisted "
            "actions and deterministic checks."
        ),
        evidence_badge="FIXTURE PLAN",
        claim_label="MODEL VARIANTS: ADVISORY · DETERMINISTIC POLICY: AUTHORIZING",
        crop_y=0.38,
    )
    fixture_execution_frame(FRAMES / "04-fixture-execution.png")
    github_frame(FRAMES / "05-github-live.png")
    datahub_frame(FRAMES / "06-datahub-live.png")
    ai_frame(FRAMES / "07-ai-verification.png")
    benchmark_frame(FRAMES / "08-benchmark.png")
    close_frame(FRAMES / "09-close.png")
    print(f"Evidence-first frames written to {FRAMES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
