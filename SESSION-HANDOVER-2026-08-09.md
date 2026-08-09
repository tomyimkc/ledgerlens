# LedgerLens contest handover — 2026-08-09

## Git and release state

- Working branch: `feat/judge-seal-theater`
- Intended landing branch / PR: `feat/demo-site-how-repo-works`, PR #65
- Base reviewed: `7b221fd`
- Public demo target: `tomyimkc/ledgerlens-incident-commander` on Hugging Face Spaces
- Devpost project: `ledgerlens-autonomous-data-incident-commander`
- Before changing or merging the PR, fetch and verify the live remote head, checks, review
  threads, and competing work. The shared checkout under
  `~/Documents/GitHub/ledgerlens` contains unrelated uncommitted work and must not be used
  for cleanup or broad staging.

## What this session changed

- Added an interactive, server-evaluated **Seal Lab** to the public incident demo.
  A judge can authorize the reviewed plan, then append an unreviewed tool call and see
  the plan fingerprint change and authorization fail without executing any provider tool.
- Added deterministic denial variants for a verifier objection and an off-allowlist target.
- Exposed the evaluated fingerprint, reason codes, conditions, and gate implementation in
  a copyable redacted receipt.
- Relabeled the Agent I/O page as a recorded trace rather than a live model call.
- Added hosted-smoke and route tests for the Seal Lab, plus contest evidence entry E-19.
- Updated the public and Devpost source copy from autonomous framing to
  **Policy-Sealed Incident Commander** framing.
- Added `docs/JUDGE_CRITIQUE.md` with a hostile-judge scorecard and residual kill risks.
- Repaired pre-existing Ruff and strict-mypy failures on the feature branch so the full
  judge gate can pass.

## What is proven, and what is not

### Demonstrated

- The public fixture can call the real authorization and policy-gate code paths.
- The reviewed plan can be authorized and a one-field/tool mutation is denied.
- The lab is fail-closed and performs no external mutation.
- The public package remains `candidateOnly: true` and `canClaimAGI: false`.
- `make judge-check` passed locally with 316 tests, Ruff, strict mypy, secret scan,
  deterministic demos, readiness checks, and submission consistency checks.

### Still open

- The public Space is still a labeled fixture. It does not make live model calls and it
  does not prove continuous production reliability.
- The recorded Agent I/O trace is not chain-of-thought and should never be described as such.
- E-16 remains a one-shot live rehearsal, not evidence that incidents were solved or that
  provider-family independence was validated.
- The existing YouTube URL is present on Devpost, but its visual quality and coverage of the
  new Seal Lab were not independently audited in this session because YouTube blocked the
  automated metadata/playback path.
- The upstream DataHub MCP contribution is bonus evidence only; do not make the submission
  depend on its merge.

## Next highest-value action

If the existing video does not already make the authorization boundary obvious, replace it
only after an owner reviews a 90–150 second real-UI cut:

1. Show the unchanged DataHub context and reviewed fingerprint.
2. Authorize the reviewed plan.
3. Append one unreviewed tool call; make the fingerprint flip and **DENIED** verdict the climax.
4. Show the off-allowlist denial and reason codes.
5. Separate the fixture lab from the E-16 one-shot live receipt.
6. End on `candidateOnly: true`, `canClaimAGI: false`, and the public judge links.

Pass bar: a cold reviewer can state, within 60 seconds, that DataHub supplies the operational
map, the model proposes but cannot authorize, the deterministic gate binds authority to an
exact plan fingerprint, and the receipt preserves what was actually approved.

## Read first

1. `docs/JUDGE_CRITIQUE.md`
2. `docs/EVIDENCE_INDEX.md`
3. `src/ledgerlens/incident_dashboard.py`
4. `src/ledgerlens/templates/incident_dashboard.html`
5. `src/ledgerlens/static/incident.js`
6. `scripts/check_hosted_incident_demo.py`
7. `docs/DEVPOST_SUBMISSION.md`

## Do not break

- Plan-exact authorization and grant wiping after plan revision.
- Fail-closed `PolicyGate` behavior and allowlists.
- Fixture/live evidence separation.
- No secrets in source, generated traces, screenshots, or deployment packages.
- No AGI, validated-uplift, production-reliability, or solved-incident claims.
- `candidateOnly: true`; `canClaimAGI: false`.
