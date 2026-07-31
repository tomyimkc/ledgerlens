# Automated Demo Recording

The recording scaffold separates **real product proof** from optional generated concept footage.

## Tools

- Node.js and npm
- Playwright 1.62.1
- ffmpeg
- a running LedgerLens UI
- a running DataHub OSS quickstart for live shots
- Grok CLI 0.2.114 or newer for optional concept assets

Tool versions should be recorded in the video receipt.

## 1. Prepare deterministic and live demo state

```bash
make setup
make demo
make datahub-up
make live-smoke
```

Verify all screens manually before recording. Never substitute deterministic fixture output for a
live DataHub shot.

## 2. Install isolated capture tools

```bash
make video-tools
```

This installs Playwright into ignored `artifacts/video-tools/`; it does not modify project
dependencies or `pyproject.toml`.

## 3. Configure the capture plan

```bash
cp docs/demo/capture-plan.example.json artifacts/video/capture-plan.json
```

Edit selectors and waits to match the final UI. The plan supports:

- `goto`
- `click`
- `fill`
- `press`
- `waitFor`
- `wait`
- `screenshot`

Environment placeholders such as `${LEDGERLENS_DEMO_URL}` are expanded at runtime.

## 4. Capture real UI

```bash
LEDGERLENS_DEMO_URL=http://localhost:8000 \
DATAHUB_FRONTEND_URL=http://localhost:9002 \
make capture-demo
```

Outputs:

```text
artifacts/video/real-ui-capture.webm
artifacts/video/screenshots/
artifacts/video/capture-receipt.json
```

The script uses a clean Chromium profile and records a real browser session. It does not mock
network responses.

## 5. Generate optional Grok concept assets

Review prompts under `docs/demo/grok/`, then run:

```bash
make grok-assets
```

Grok CLI opens each `/imagine-video` prompt. Save approved clips under:

```text
artifacts/video/grok/
```

Generated clips must be abstract and must not imitate product functionality. The render script
adds a generated-visual label when those clips are included.

## 6. Narration and captions

Record or generate English narration from `DEMO_SCRIPT.md`. Save:

```text
artifacts/video/narration.wav
artifacts/video/captions.srt
```

Check names, commands, and result numbers against the final receipts before rendering.

## 7. Render

```bash
make render-video
```

The default render requires the real UI capture and can produce a proof-only video without Grok
assets. Optional concept clips are accepted only through an explicit manifest.

Output:

```text
artifacts/video/ledgerlens-demo.mp4
artifacts/video/render-receipt.json
```

## 8. Verify

```bash
make verify-video
```

Verify manually as well:

- duration under 180 seconds;
- 1920×1080 output;
- readable English captions;
- no secret or private path;
- generated clips labeled;
- DataHub and LedgerLens functionality shown only through real capture;
- public upload works in an incognito browser.
