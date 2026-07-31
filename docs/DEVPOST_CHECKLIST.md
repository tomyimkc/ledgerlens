# DataHub Agent Hackathon Submission Checklist

Official deadline:

- **August 10, 2026 at 5:00 PM EDT**
- **August 11, 2026 at 5:00 AM HKT**

Operational deadline with a 24-hour buffer:

- **August 9, 2026 at 5:00 PM EDT**
- **August 10, 2026 at 5:00 AM HKT**

The repository automation can complete and verify code, evidence, documentation, and outreach.
The owner must complete account, team, eligibility, public-video, final-release, and final-submit
actions.

## Project identity

- [ ] Devpost account is active.
- [ ] Owner has joined the DataHub Agent Hackathon.
- [ ] Team members and representative details are correct.
- [ ] Eligibility restrictions have been reviewed.
- [ ] Contest-period project eligibility has been confirmed by the owner.
- [x] Category is **Agents That Do Real Work**.
- [x] Project name is **LedgerLens — Autonomous Data Incident Commander**.
- [x] Tagline is “Turn DataHub context into authorized incident work—with receipts.”

## Meaningful DataHub use

- [x] DataHub context grounds the root entity, owner, tier, schema, documentation, quality signal,
      and bounded lineage.
- [x] Official DataHub MCP reads are implemented and evidenced.
- [x] DataHub mutation is disabled by default and requires deterministic authorization.
- [x] A live DataHub OSS v1.6.0 `save_document` write-back receipt is published.
- [x] The written document was retrieved through official MCP `get_entities`.
- [x] Next-agent memory preserves DataHub references, known facts, unknowns, and required checks.
- [x] The fixture, local-live, and temporary-public DataHub result classes are clearly separated.
- [x] Ingestion and observation timestamps are not called validation timestamps.

## Autonomous incident-command execution

- [x] The visible chain is trigger → DataHub context → bounded plan → AI advisory verification →
      deterministic authorization → receipted actions → DataHub write-back → next-agent handoff.
- [x] AI output cannot authorize itself or expand action/target allowlists.
- [x] The exact plan fingerprint, evidence IDs, action schema, risk, quorum, and confidence are
      checked by deterministic policy.
- [x] GitHub, Slack, PagerDuty, and Jira adapters implement preview/execute separation,
      authorization binding, idempotency, bounded retries, and sanitized receipts.
- [x] A live GitHub create-and-close action receipt is published.
- [x] Slack, PagerDuty, and Jira remain explicitly described as implemented but not executed live.
- [x] DataHub write-back and next-agent handoff occur only after authorization.

## Public repository and CI

- [x] Repository is public: `https://github.com/tomyimkc/ledgerlens`.
- [x] Root `LICENSE` is Apache-2.0.
- [x] `DISCLOSURE.md` separates pre-existing Sophia material from newly built contest work.
- [x] Repository and tracked evidence pass the secret scan.
- [x] No private ledger rows, credentials, tokens, or raw evaluator records are tracked.
- [x] CI covers Python 3.11 and 3.12.
- [x] CI installs DataHub, web, video, and development dependencies needed by the gates.
- [x] CI runs Ruff, strict mypy, deterministic tests, public-package checks, secret scan,
      non-video readiness, package build, and non-root container build.
- [x] July 31, 2026 local judge gate passed 252 deterministic tests and strict mypy over 36 source
      files.
- [x] `make check` includes strict type checking.
- [x] `make demo-ui` uses only supported CLI flags.
- [x] `make non-video-readiness` fails closed on evidence, claim, CI, product-copy, or release
      drift.
- [ ] Final `v0.2.1` release tag is published after the public video URL is recorded.

## Functional and evidence verification

- [x] Deterministic fixture receipt is separate from live DataHub receipts.
- [x] DataHub-context ON/OFF benchmark receipt reports `PASS`.
- [x] Live DataHub OSS smoke receipt reports `PASS`.
- [x] Live AI planner/verifier receipt preserves `externalMutations: false`.
- [x] Live GitHub action receipt records execution and closure.
- [x] Live DataHub write-back receipt records mutation and fresh MCP retrieval.
- [x] Supervised public DataHub proof receipt reports `PASS`.
- [x] Public-proof teardown reports complete and the former temporary URL returned 503.
- [x] No paid resource was provisioned for the public DataHub proof.
- [x] `candidateOnly: true` is preserved.
- [x] `canClaimAGI: false` is preserved.
- [x] `externalValidation: false` is preserved where the receipt schema includes it.
- [x] No claim equates provider receipts with incident causality, impact, recovery, or resolution.
- [x] Malformed, duplicate, prompt-injection, authorization, and adapter failure paths are tested.

## Public access and reproducibility

- [x] Public project URL works without an account:
      `https://tomyimkc-ledgerlens-incident-commander.hf.space/`.
- [x] Public replay is visibly labeled `FIXTURE / REPLAY`.
- [x] Public `/healthz` reports fixture mode, no external mutations, and the claim ceiling.
- [x] Public trigger returns exactly four synthetic provider receipts.
- [x] Public write-back reaches `recorded` and next-agent memory reaches `ready`.
- [x] Public authorization reports deterministic authority and `ai_can_authorize: false`.
- [x] A scheduled/manual hosted smoke workflow requires no repository secret.
- [x] Hosted smoke uploads only a sanitized JSON receipt.
- [x] Temporary authenticated DataHub reachability proof is documented with teardown.
- [x] Documentation states that no durable public DataHub judge URL exists.
- [ ] Owner keeps the Hugging Face Space free and reachable through August 31, 2026.
- [ ] Owner verifies final project and video URLs in a clean/incognito browser.

## External evaluation and open source

- [x] Consent-safe 7–10 minute evaluation protocol is published.
- [x] Data-engineer and incident-responder scorecard roles are defined.
- [x] Aggregate, anonymous-comment, and attribution consent are separate.
- [x] Aggregation fails closed and excludes non-consented public records.
- [x] Raw evaluator records are required to remain private.
- [x] Public recruitment issue #10 is open.
- [ ] One data engineer completes the formative review.
- [ ] One incident responder completes the formative review.
- [ ] Any public aggregate is published only after explicit consent.
- [x] Upstream DataHub MCP issue #159 is open.
- [x] Upstream DataHub MCP PR #160 is open with focused tests.
- [ ] Upstream maintainers approve/review/merge PR #160.
- [x] Submission copy states that PR #160 remains open, not merged.

## Devpost text and evidence

- [x] English project description reflects the Autonomous Data Incident Commander.
- [x] “How we built it” names DataHub OSS and the official MCP Server.
- [x] AI verification is separated from deterministic authorization.
- [x] Real GitHub and DataHub receipts are linked.
- [x] Supervised authenticated public DataHub proof and teardown are linked.
- [x] Synthetic DataHub-context ON/OFF benchmark is linked.
- [x] Upstream MCP provenance/audit-context proposal is linked.
- [x] Pre-existing-work disclosure is explicit.
- [x] Apache-2.0 is stated.
- [x] Working-prototype and no-independent-validation boundaries are explicit.
- [x] No planned feature is described as already working.
- [x] No reviewer score, testimonial, endorsement, or official competition score is invented.
- [x] Public project URL is recorded.
- [ ] Public video URL is recorded.

## Video — deliberately deferred in this non-video pass

- [ ] Final public runtime is below three minutes.
- [ ] Narration and captions are in English.
- [ ] Product functionality is shown through real UI/terminal capture.
- [ ] Any generated footage is clearly labeled and does not imitate product functionality.
- [ ] No private path, credential, account detail, notification, or extension is visible.
- [ ] Video is public on YouTube, Vimeo, or Youku.
- [ ] Video link works in a clean/incognito browser.
- [ ] Captions are legible at 1080p.

## Final release and submission — owner boundary

- [x] DataHub version is recorded as `v1.6.0`.
- [x] Deterministic fixture receipt path is recorded.
- [x] Live DataHub smoke receipt path is recorded.
- [x] Supervised public-proof receipt path is recorded.
- [x] Public project URL is recorded.
- [ ] Public video URL is recorded.
- [ ] Final merged commit SHA is recorded without invention.
- [ ] Final `v0.2.1` release tag is cut after the video URL is available.
- [ ] Owner reviews account, team, eligibility, and complete submission copy.
- [ ] Owner clicks final Submit.
- [ ] Submission receipt is saved.
- [ ] Receipt timestamp is before the operational deadline.
- [ ] Final Devpost page works in an incognito browser.
