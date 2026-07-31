# LedgerLens Evidence-First Demo Video

**Target runtime:** 2:48 (168 seconds)

**Accepted runtime window:** 2:40–2:55

**Delivery:** 1920×1080, 30 fps, H.264/AAC, burned English captions, selectable English captions

## Editorial thesis

The demo separates four evidence classes instead of blending them into one product claim:

1. **Live public host, fixture replay** — the public Hugging Face Space is live, while the
   incident state and every `fixture://` action receipt shown there are deterministic replay data.
2. **Published live GitHub receipt** — public issue `tomyimkc/ledgerlens#3` proves bounded issue
   creation and closure. It does not prove incident causality or recovery.
3. **Published live DataHub OSS receipt** — the `save_document` receipt proves a controlled
   DataHub write and fresh MCP retrieval. It does not prove incident recovery.
4. **Published AI and deterministic benchmark receipts** — the AI receipt records advisory model
   variants plus deterministic authorization; the benchmark is synthetic, offline, and
   non-validating.

The claim boundary is visible throughout:

```yaml
candidateOnly: true
canClaimAGI: false
```

## Timeline

| Time | Scene | Evidence label | Visual |
|---:|---|---|---|
| 0:00–0:10 | Incident-response gap | `EVIDENCE FIRST` | LedgerLens title and evidence chain |
| 0:10–0:30 | Public hosted demo | `LIVE HOST · FIXTURE REPLAY` | Live Space hero, fixture banner, claim boundary |
| 0:30–0:50 | DataHub operating context | `LIVE HOST · FIXTURE REPLAY` | Root entity, owner, tier, lineage, unknowns |
| 0:50–1:12 | Advisory plan, deterministic authority | `FIXTURE PLAN · POLICY GATE` | Plan fingerprint, verifier panel, authorization gate |
| 1:12–1:30 | Replay execution and durable handoff | `FIXTURE RECEIPTS` | `fixture://` action cards, write-back state, next-agent memory |
| 1:30–1:50 | Real GitHub action | `LIVE EXTERNAL MUTATION` | Public closed issue plus published receipt fields |
| 1:50–2:10 | Real DataHub write-back | `LIVE DATAHUB OSS RECEIPT` | `save_document`, created URN, MCP retrieval, limitations |
| 2:10–2:28 | AI verification receipt | `LIVE AI REHEARSAL · ADVISORY` | Planner/verifier variants, quorum, deterministic authorization |
| 2:28–2:40 | Context ablation | `DETERMINISTIC FIXTURE BENCHMARK` | 120 assets, 24 scenarios, context ON/OFF metrics |
| 2:40–2:48 | Close | `CANDIDATE ONLY` | Public Space, repository, exact claim boundary |

## Capture sources

- Public Space:
  `https://tomyimkc-ledgerlens-incident-commander.hf.space/`
- Space health:
  `https://tomyimkc-ledgerlens-incident-commander.hf.space/healthz`
- Public GitHub issue:
  `https://github.com/tomyimkc/ledgerlens/issues/3`
- Published receipt files on the public `main` branch:
  - `benchmarks/incident_commander/github-live-action-receipt.json`
  - `benchmarks/incident_commander/datahub-live-writeback-receipt.json`
  - `benchmarks/incident_commander/ai-verification-receipt.json`
  - `benchmarks/incident_commander/context-ablation-receipt.json`

The capture script downloads the public receipt bytes, records their SHA-256 digests, and saves
sanitized capture metadata under ignored `artifacts/video/evidence-first/`.

## Narration and claim discipline

- Say **live host** only for reachability of the public Space; say **fixture replay** for the
  incident state shown by that Space.
- Say **real GitHub issue creation and closure** only for receipt `#3`.
- Say **live DataHub OSS write-back and retrieval** only for the published `save_document`
  receipt.
- Say **AI advisory approval plus deterministic authorization**, never AI self-authorization.
- Describe the benchmark as **synthetic, deterministic, offline, and non-validating**.
- Never imply Slack, PagerDuty, or Jira were executed live.
- Never imply root cause, user impact, recovery, production readiness, validated uplift, or AGI.

## Build

```bash
PLAYWRIGHT_PACKAGE=/path/to/playwright \
  node scripts/video/capture_evidence_first.mjs

python3 scripts/video/create_evidence_frames.py
python3 scripts/video/render_evidence_first.py

python3 scripts/video/verify_video.py \
  artifacts/video/evidence-first/ledgerlens-evidence-first.mp4
python3 scripts/video/verify_evidence_video.py \
  artifacts/video/evidence-first/ledgerlens-evidence-first.mp4
```

The capture can use a normal `playwright` installation or an explicit `PLAYWRIGHT_PACKAGE`
directory containing `index.mjs`.
