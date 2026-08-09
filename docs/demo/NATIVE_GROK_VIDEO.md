# Policy-sealed native Grok video

The contest video reuses the same local generation method as the earlier Polygraph production:

```text
reviewed profile portrait
  → portrait-derived 16:9 base frames
  → xAI grok-imagine-video-1.5
  → native audio and lip sync
  → evidence-panel Remotion composition
  → technical and visual QA
```

The tracked scene source is `docs/demo/policy-sealed-native-grok-scenes.json`. It intentionally
removes the stale “Autonomous” framing and leads with the actual authority split:

> The model may propose work; deterministic policy authorizes the exact reviewed plan.

## Generate presenter clips

The generator reads the existing Grok CLI authentication file locally. Authentication material and
generated media stay outside git.

```bash
mkdir -p artifacts/video/native-grok
cp docs/demo/policy-sealed-native-grok-scenes.json \
  artifacts/video/native-grok/scenes.json

# Add the reviewed presenter portrait and four portrait-derived input frames under:
# artifacts/video/native-grok/presenter-reference.png
# artifacts/video/native-grok/input/{left-a,left-b,right-a,right-b}.png

uv run python scripts/video/generate_native_grok.py \
  --scenes artifacts/video/native-grok/scenes.json \
  --workers 4

uv run python scripts/video/assemble_native_grok.py \
  --scenes artifacts/video/native-grok/scenes.json
```

## Editorial requirements

- Public title:
  **LedgerLens — Policy-Sealed Incident Commander (DataHub Agent Hackathon)**
- Runtime below three minutes.
- Always-visible disclosure: **AI-GENERATED PRESENTER**.
- Burned English captions. The generated subtitle source is reviewed speech, not a claim of exact
  speech recognition.
- Real product screenshots occupy the proof panel. Generated presenter footage is not product
  evidence.
- The fixture label and `externalMutations: false` remain visible when the public Space is shown.
- E-16 provider work and E-07 DataHub write/read remain separate unless a new integrated receipt
  actually succeeds.
- Keep `candidateOnly: true` and `canClaimAGI: false`.
- Do not claim validated uplift, production reliability, incident recovery, or AGI.

## QA

```bash
ffprobe -v error \
  -show_entries format=duration:stream=codec_name,width,height,r_frame_rate \
  -of json path/to/final.mp4

uv run python scripts/video/package_native_grok_video.py
uv run python scripts/video/verify_native_grok_video.py \
  artifacts/video/native-grok/ledgerlens-policy-sealed-final.mp4
```

Also inspect stills near 00:03, 00:48, 01:18, 02:03, and 02:27. Reject the cut if the presenter
occludes the proof panel, the mode label is hidden, captions are clipped, or any visible title
uses “Autonomous.”

The native-Grok verifier is intentionally separate from `verify_video.py`: this cut labels the
generated presenter throughout and treats only the captured product panels as evidence. Passing
the technical verifier does not replace the still-frame review or the final public-upload check.
