# LedgerLens Evidence-First Demo Video

**Target runtime:** 2:50 (170 seconds)

**Accepted runtime window:** 2:40–2:55

**Delivery:** 1920×1080, 30 fps, H.264/AAC, burned English captions, selectable English captions

## Editorial thesis

The demo separates evidence classes instead of blending them into one product claim:

1. **Live public host, fixture replay** — the public Hugging Face Space is live, while the
   incident state and every `fixture://` action receipt shown there are deterministic replay data.
2. **Published four-provider live rehearsal (E-16)** — one authorized run executed a single bounded
   action against GitHub (issue #29), Slack, PagerDuty, and Jira (KAN-2). Each is one rehearsal
   action; it proves the adapter path, not sustained operation, causality, or recovery.
3. **Published live DataHub OSS receipt** — the `save_document` receipt proves a controlled
   DataHub write and fresh MCP retrieval. It does not prove incident recovery.
4. **Real-pipeline policy-gate ablation (E-15)** — the production `PolicyGate`/`VerifierPanel`, run
   with a deterministic stub planner, authorizes every context-on scenario and refuses every
   context-off scenario with its own reason codes. It proves the fail-closed gate, not model uplift;
   it is synthetic, offline, and non-validating.

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
| 1:30–1:52 | Real four-provider fanout (E-16) | `LIVE BOUNDED REHEARSAL` | One authorized run: GitHub #29, Slack, PagerDuty, Jira KAN-2 receipts |
| 1:52–2:10 | Real DataHub write-back | `LIVE DATAHUB OSS RECEIPT` | `save_document`, created URN, MCP retrieval, limitations |
| 2:10–2:28 | AI verification receipt | `LIVE AI REHEARSAL · ADVISORY` | Planner/verifier variants, quorum, deterministic authorization |
| 2:28–2:42 | Real-pipeline context ablation (E-15) | `PRODUCTION POLICY GATE` | Real gate: 100% authorized ON / 0% OFF with reason codes |
| 2:42–2:50 | Close | `CANDIDATE ONLY` | Public Space, repository, exact claim boundary |

## Capture sources

- Public Space:
  `https://tomyimkc-ledgerlens-incident-commander.hf.space/`
- Space health:
  `https://tomyimkc-ledgerlens-incident-commander.hf.space/healthz`
- Public GitHub issue (E-16 rehearsal): `https://github.com/tomyimkc/ledgerlens/issues/29`
- Public Jira issue (E-16 rehearsal): `https://tomyimkc.atlassian.net/browse/KAN-2`
- Published receipt files on the public `main` branch:
  - `benchmarks/incident_commander/live-incident-rehearsal-receipt.json` (E-16, four providers)
  - `benchmarks/incident_commander/real-pipeline-ablation-receipt.json` (E-15, real gate)
  - `benchmarks/incident_commander/datahub-live-writeback-receipt.json`
  - `benchmarks/incident_commander/ai-verification-receipt.json`
  - `benchmarks/incident_commander/context-ablation-receipt.json`

The capture script downloads the public receipt bytes, records their SHA-256 digests, and saves
sanitized capture metadata under ignored `artifacts/video/evidence-first/`.

## Narration and claim discipline

- Say **live host** only for reachability of the public Space; say **fixture replay** for the
  incident state shown by that Space.
- Say **one bounded rehearsal action per provider** for the E-16 four-provider run (GitHub #29,
  Slack, PagerDuty, Jira KAN-2). Never say sustained, repeated, or production execution.
- Say **live DataHub OSS write-back and retrieval** only for the published `save_document`
  receipt.
- Say **AI advisory approval plus deterministic authorization**, never AI self-authorization.
- Describe the ablation as run through the **real production policy gate** with a deterministic
  stub planner — it proves the fail-closed gate, not model capability or uplift — and as
  synthetic, deterministic, offline, and non-validating.
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
