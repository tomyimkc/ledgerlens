#!/usr/bin/env python3
"""Generate native lip-synced LedgerLens presenter clips via Grok Imagine.

This is the same pipeline used for the Polygraph / Arm contest video
(polygraph-video-assets/gen/generate.py + VIDEO-PRODUCTION.md):

  profile portrait → 16:9 base frames → data:image URI
    → POST https://api.x.ai/v1/videos/generations  (grok-imagine-video-1.5)
    → poll GET /v1/videos/{request_id}
    → download .video.url

No public tunnel / upload_url required. Identity comes from
artifacts/video/native-grok/presenter-reference.png (same portrait as Polygraph).
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "artifacts" / "video" / "native-grok"
AUTH = Path.home() / ".grok" / "auth.json"
INPUT = HERE / "input"
OUT = HERE / "output"
RAW = HERE / "raw"

# Identical prompt shape to polygraph-video-assets/gen/generate.py
PROMPT_TMPL = (
    "Realistic professional talking-presenter video from the supplied portrait-derived frame. "
    "Preserve the male presenter's exact facial identity, hairstyle, age, skin tone, navy shirt, "
    "and proportions, and keep him in the same position within the frame. "
    "He looks into the camera and speaks fluent natural English with accurate lip-synchronized "
    "articulation, in a {expression} manner, for exactly this speech: "
    "“{speech}” "
    "Natural blinking, breathing, subtle head motion, restrained hand gestures, stable background, "
    "gentle cinematic push-in. No captions, no added text, no logo, no extra people, no identity drift."
)


def api_key() -> str:
    return next(iter(json.loads(AUTH.read_text(encoding="utf-8")).values()))["key"]


def req(method: str, url: str, tok: str, body=None, timeout: int = 180):
    headers = {"Authorization": f"Bearer {tok}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def submit(scene: dict, tok: str, duration: int) -> dict:
    base = INPUT / scene["base"]
    if not base.is_file():
        raise FileNotFoundError(base)
    # Accept jpeg bases too
    if base.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
        uri = f"data:{mime};base64," + base64.b64encode(base.read_bytes()).decode()
    else:
        uri = data_uri(base)
    prompt = PROMPT_TMPL.format(expression=scene["expression"], speech=scene["speech"])
    result = req(
        "POST",
        "https://api.x.ai/v1/videos/generations",
        tok,
        {
            "model": "grok-imagine-video-1.5",
            "prompt": prompt,
            "image": {"url": uri},
            "duration": duration,
            "aspect_ratio": "16:9",
            "resolution": "720p",
        },
    )
    rid = str(result["request_id"])
    print(f"  {scene['id']}: submitted {rid}", flush=True)
    return {
        "id": scene["id"],
        "rid": rid,
        "speech": scene["speech"],
        "base": scene["base"],
    }


def poll_and_download(job: dict, tok: str) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for attempt in range(240):
        data = req("GET", f"https://api.x.ai/v1/videos/{job['rid']}", tok)
        status = str(data.get("status", "?"))
        if attempt % 8 == 0 or status not in {"processing", "queued", "pending"}:
            print(
                f"  {job['id']}: {status} progress={data.get('progress', '?')}",
                flush=True,
            )
        if status in {"done", "completed", "succeeded"}:
            url = (data.get("video") or {}).get("url") or data.get("url")
            if not url:
                raise RuntimeError(
                    f"{job['id']}: completed but no video url: {json.dumps(data)[:300]}"
                )
            dest = OUT / f"{job['id']}-raw.mp4"
            with urllib.request.urlopen(url, timeout=600) as response, dest.open("wb") as handle:
                handle.write(response.read())
            print(
                f"  {job['id']}: downloaded {dest.stat().st_size // 1024} KiB → {dest.name}",
                flush=True,
            )
            return {
                **job,
                "path": str(dest),
                "bytes": dest.stat().st_size,
                "status": status,
                "model": data.get("model"),
            }
        if status in {"failed", "error", "expired"}:
            raise RuntimeError(f"{job['id']}: {json.dumps(data)[:400]}")
        time.sleep(5)
    raise TimeoutError(job["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenes",
        default=str(HERE / "scenes.json"),
        help="scenes.json (speech + base frame per beat)",
    )
    parser.add_argument("--only", default="", help="comma-separated scene ids")
    parser.add_argument("--duration", type=int, default=15, choices=(5, 10, 15))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-generate even if output already exists",
    )
    args = parser.parse_args()

    spec = json.loads(Path(args.scenes).read_text(encoding="utf-8"))
    scenes = list(spec["scenes"])
    if args.only:
        want = {item.strip() for item in args.only.split(",") if item.strip()}
        scenes = [scene for scene in scenes if scene["id"] in want]
    if not args.force:
        scenes = [
            scene
            for scene in scenes
            if not (OUT / f"{scene['id']}-raw.mp4").is_file()
        ]
    if not scenes:
        print("all clips already present; nothing to do")
        return 0

    portrait = HERE / "presenter-reference.png"
    if not portrait.is_file():
        raise SystemExit(
            f"missing profile portrait: {portrait}\n"
            "Copy polygraph-video-assets/gen/presenter-reference.png there first."
        )
    for scene in scenes:
        if not (INPUT / scene["base"]).is_file():
            raise SystemExit(f"missing base frame: {INPUT / scene['base']}")

    tok = api_key()
    print(
        f"submitting {len(scenes)} native Grok clip(s) "
        f"(model=grok-imagine-video-1.5, duration={args.duration}s, "
        f"portrait={portrait.name})...",
        flush=True,
    )
    jobs = [submit(scene, tok, args.duration) for scene in scenes]
    (HERE / "submitted-jobs.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ledgerlens.native-grok-submissions.v1",
                "createdAtUtc": datetime.now(UTC).isoformat(),
                "model": "grok-imagine-video-1.5",
                "profilePortrait": str(portrait),
                "jobs": jobs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    done: list[dict] = []
    failed: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(poll_and_download, job, tok): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                done.append(future.result())
            except Exception as error:  # noqa: BLE001 — surface per-clip failure
                failed.append((job["id"], str(error)[:300]))
                print(f"  FAIL {job['id']}: {error}", flush=True)

    manifest = {
        "schemaVersion": "ledgerlens.native-grok-generation.v1",
        "createdAtUtc": datetime.now(UTC).isoformat(),
        "model": "grok-imagine-video-1.5",
        "profilePortrait": str(portrait.relative_to(ROOT)),
        "pipeline": "polygraph generate.py (data URI, no tunnel)",
        "candidateOnly": True,
        "canClaimAGI": False,
        "completed": sorted(done, key=lambda item: item["id"]),
        "failed": failed,
        "note": (
            "Native Grok audio + lip sync. AI-generated presenter from profile portrait — "
            "not a recording of the user. Human review of wording/lipsync required before publish."
        ),
    }
    path = HERE / "native-generation-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("\nCOMPLETED:", sorted(item["id"] for item in done), flush=True)
    if failed:
        print("FAILED:", failed, flush=True)
        return 1
    print(f"manifest: {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
