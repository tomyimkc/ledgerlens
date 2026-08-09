# LedgerLens contest handover — 2026-08-09

## Current lane

- Worktree: `/private/tmp/ledgerlens-video-refresh`
- Branch: `feat/policy-sealed-video-refresh`
- Base before this change: `origin/main` at
  `028a057fd4d5e905aa9b853dc559991ce59f8aab`
- Scope: Policy-Sealed contest-video replacement, presentation hygiene, and a fail-closed
  owner-only combined live-rehearsal harness.
- A PR and final merge state must be recorded here after publication.

## What this session changed

1. **Regenerated the contest video with the existing Grok CLI method**
   - Ten xAI `grok-imagine-video-1.5` presenter scenes with native audio/lip sync.
   - Captured LedgerLens product and evidence panels are used for functionality; the generated
     presenter is labeled **AI-GENERATED PRESENTER** throughout.
   - The reviewed narrative leads with the real split: the model may propose work, while
     deterministic policy authorizes only the exact reviewed plan.
   - The tracked scene source and reproducible packaging/verification method are in
     `docs/demo/policy-sealed-native-grok-scenes.json`,
     `docs/demo/NATIVE_GROK_VIDEO.md`, and `scripts/video/`.
2. **Removed stale video presentation framing**
   - The replacement story, caption cues, manifest, and metadata contain no `Autonomous` title.
   - Required public title:
     **LedgerLens — Policy-Sealed Incident Commander (DataHub Agent Hackathon)**.
   - The currently published YouTube watch page still needs an account-authorized upload or
     rename. Do not report this as fixed until the watch page and Devpost embed are checked in a
     clean browser.
3. **Implemented the next legitimate evidence harness**
   - `scripts/run_integrated_live_incident_rehearsal.py` performs, in one process:
     official DataHub MCP read → native model plan and advisory verification → deterministic
     exact-plan authorization → bounded GitHub/Slack/PagerDuty/Jira actions → policy-gated
     DataHub `save_document` → official MCP exact-URN read-back.
   - A receipt sets `integratedSameProcessRun: true` only if every planned provider action,
     DataHub write-back, and exact returned-URN read-back succeeds.
   - Provider-family independence, reliability, recovery, incident causality, production
     readiness, uplift, and AGI are not claimed.
4. **Added explicit mutation boundaries**
   - Read-only preflight does not require or call a model or provider.
   - Synthetic DataHub catalog ingestion requires both the Make phrase
     `CONFIRM_DATAHUB_CONTEXT_SEED=INGEST_SYNTHETIC_CONTEXT` and the script confirmation flag.
   - The combined live run requires the Make phrase
     `CONFIRM_INTEGRATED_LIVE=READ_ACT_WRITE` plus separate provider-action and DataHub-writeback
     flags.
   - If an exception occurs after execution starts, the failure receipt records the external
     mutation outcome as unknown instead of guessing.
5. **Updated judge and Devpost readiness docs**
   - The locally verified replacement video is distinguished from a completed public upload.
   - The harness is distinguished from evidence.
   - The separate E-16 provider run and E-07 DataHub run remain separate unless the combined
     harness actually completes.

## Replacement video

- Final local file:
  `/private/tmp/ledgerlens-video-refresh/artifacts/video/native-grok/ledgerlens-policy-sealed-final.mp4`
- Owner-ready copy:
  `/Users/tom/Downloads/ledgerlens-policy-sealed-20260809.mp4`
- SHA-256:
  `f622191da962be10cd217cbb811031e8a7c41a6013e406c9213209a730a4340c`
- Runtime: `150.058667` seconds
- Technical profile: H.264, 1920×1080, AAC audio, selectable English `mov_text` subtitles,
  30 caption cues.
- Local verifier: PASS.
- Representative-frame review: PASS for disclosure, evidence-panel readability, captions, and
  claim boundary.
- Public upload/title/incognito playback: **not yet verified**.

## Owner-controlled DataHub preflight

- A private DataHub stack was started on `pro6000-cf`; access was tunneled only to local
  `127.0.0.1:18080`.
- The official-MCP read-only preflight failed closed because the selected root entity had no
  recorded owner.
- Read-only discovery found no existing LedgerLens entity satisfying both owner and
  `ledgerlens.runbookUrl` context requirements.
- No model, provider action, DataHub mutation, or evidence promotion occurred.
- A visibly synthetic context seed can satisfy the contract, but it is setup only and needs
  explicit owner authorization.

## Explicit authorizations still required

Do not infer either authorization from a general request to improve evidence.

1. DataHub setup mutation:

   > I authorize `INGEST_SYNTHETIC_CONTEXT` into the owner-controlled DataHub.

2. Supervised provider actions plus DataHub write-back:

   > I authorize the supervised `READ_ACT_WRITE` rehearsal against the reviewed provider
   > destinations.

After both authorizations:

1. ingest the visibly synthetic catalog;
2. rerun read-only preflight and require `ready: true`;
3. review sanitized targets and readiness;
4. start the combined rehearsal and monitor its terminal through completion;
5. inspect all provider surfaces and the exact DataHub document URN;
6. publish only a redacted derivative if the same-process receipt is complete.

One successful run remains one supervised bounded rehearsal. It must not be generalized into
reliability or production evidence.

## Verification completed

- `make check`: PASS.
- `make judge-check`: PASS.
- 338 deterministic non-live tests: PASS.
- Ruff lint and format: PASS.
- Strict mypy over 38 source files: PASS.
- Build, secret scan, public-package gate, non-video readiness, submission consistency, context
  benchmark, and real-pipeline benchmark: PASS.
- Native-Grok video technical verifier: PASS.
- `git diff --check`: PASS.
- The generated timestamp/machine-only context benchmark receipt was restored rather than added
  to this change.

These checks establish candidate prototype behavior and reproducibility only.

## Residual owner/external risks

1. **Public video:** upload the owner-ready MP4 or replace the existing YouTube content, set the
   exact Policy-Sealed title, and verify watch-page and Devpost-embed playback without sign-in.
2. **Combined evidence:** the harness is ready, but the current DataHub context contract is not.
   No combined run may be claimed until the two explicit owner authorizations and a complete
   receipt exist.
3. **External review:** two consented formative reviews remain absent.
4. **Release alignment:** cut the final release only from the actual merged submission revision
   and rerun hosted checks against that revision.
5. **External dependency:** upstream DataHub MCP review/merge remains outside this repository's
   control and is bonus evidence only.

## Operational cleanup

- Stop the SSH tunnel by interrupting its own terminal session, not by killing arbitrary PIDs.
- Stop the private DataHub stack with its normal `deploy/live-proof/stack.sh stop` command.
- Do not delete DataHub volumes or unrelated Docker state merely to finish this session.

## Read first

1. `docs/JUDGE_CRITIQUE.md`
2. `docs/EVIDENCE_INDEX.md`
3. `docs/INTEGRATED_LIVE_REHEARSAL.md`
4. `docs/demo/NATIVE_GROK_VIDEO.md`
5. `docs/DEVPOST_SUBMISSION.md`
6. `docs/WINNER_READINESS.md`

## Do not break

- Authority remains outside the model.
- Authorization remains bound to the exact reviewed plan fingerprint.
- Policy remains fail-closed on missing DataHub facts, verifier objections, or off-allowlist work.
- Fixture, recorded-model, local-live, bounded-provider, and repeated-hosted evidence remain
  separate.
- No secrets enter source, receipts, screenshots, logs, deployment payloads, or Devpost copy.
- No AGI, validated-uplift, production-reliability, provider-reliability, recovery,
  solved-incident, model-family-independence, or upstream-acceptance claims.
- `candidateOnly: true`; `canClaimAGI: false`.
