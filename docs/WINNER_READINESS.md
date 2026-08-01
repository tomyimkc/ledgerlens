# LedgerLens non-video winner-readiness scorecard

**Assessment date:** August 1, 2026
**Scope:** Non-video public repository, hosted fixture, recorded receipts, and reproducibility.
**Scoring rule:** Five core criteria are scored independently. The open-source contribution is a separate bonus, because the official rules call it a bonus even while listing criteria as equally weighted. These are internal readiness assessments, not official judging scores.

## Current scorecard

| Criterion | Score | Confidence | Evidence a judge can access | Remaining proof gap | Highest-value next improvement | Status |
|---|---:|---|---|---|---|---|
| A. Meaningful DataHub use and write-back | 8.0 / 10 | Medium | Fixture flow, context ablation, local DataHub OSS write-back and official-MCP retrieval receipt | Public Space is fixture-only; no durable public DataHub instance | Make E-02/E-07 the first links in Devpost and screenshots | Finalist-capable |
| B. Technical execution and end-to-end functionality | 8.0 / 10 | Medium | Typed orchestrator, deterministic authority tests, adapters, receipt model, CI, hosted smoke | Only GitHub has a live provider receipt; no current public deployment revision receipt | Re-run all gates on final commit and link the resulting hosted-smoke artifact | Finalist-capable |
| C. Originality beyond DataHub built-ins | 8.5 / 10 | Medium | Exact-plan authorization, verifier quorum, allowlists, HMAC-bound adapters, next-agent handoff | No independent reviewer has assessed differentiation | Complete two consented formative reviews without overstating them | Finalist-capable |
| D. Real-world usefulness | 7.0 / 10 | Low | Clear incident workflow, ownership/lineage context, safe bounded work, explicit unknowns | Synthetic incidents and no real user study or production outcome | Recruit two role-appropriate formative reviewers and publish only consented aggregate findings | Contender |
| E. Submission quality and reproducibility | 7.5 / 10 | Medium | Public Apache-2.0 repo, public Space, one-command demo, CI, secret scan, readiness check | Final clean-clone receipt and final release/package alignment are not yet recorded | Run and publish final clean-clone/hosted smoke receipts from the merged final revision | Contender |
| F. Open-source contribution bonus | 6.0 / 10 | Medium | Public upstream issue #159 and PR #160 with a focused scope | PR is open and blocked; no maintainer acceptance or merge | Keep the contribution accurately linked; respond only to justified maintainer feedback | Contender bonus |

**Five-core average:** **7.8 / 10**
**Bonus:** **6.0 / 10** (reported separately; not folded into the core average)

## Why the score is not higher

- The hosted judge experience proves a **fixture replay**, not a full public DataHub deployment.
- The strongest live provider evidence is one closed GitHub rehearsal; Slack, PagerDuty, and Jira remain implemented but unexecuted live adapters.
- The benchmark is deterministic and synthetic with an intentionally generic context-off baseline.
- External evaluation infrastructure is ready, but no consented independent review result exists.
- Final release, clean-clone receipt, and Devpost-owner actions remain time-sensitive work.

## P0/P1/P2 gap matrix

| Priority | Gap | Rubric affected | Why it matters | Exact change or owner action | Acceptance evidence | Disposition |
|---|---|---|---|---|---|---|
| P0 | Judge cannot quickly distinguish fixture, local-live, and temporary-public evidence. | A, B, E | A fixture can be misread as live integration. | Add and link a canonical evidence index. | `docs/EVIDENCE_INDEX.md`; readiness test. | Automated in this change |
| P0 | Documentation can drift from the official bonus interpretation. | E, F | Folding a bonus into a six-way average hides core weaknesses. | Make five-core-plus-bonus framing canonical. | This scorecard and Devpost copy. | Automated in this change |
| P0 | Final claims can outpace actual release/proof state. | A–F | Misleading claims can disqualify a strong project. | Extend readiness guard with canonical claim and identity checks. | `make non-video-readiness`. | Automated in this change |
| P0 | Final submission still lacks owner-controlled video URL, eligibility confirmation, and submit receipt. | E | Required submission material and eligibility cannot be automated. | Owner completes checklist; do not evaluate the video itself. | Devpost and owner receipts. | Owner-only |
| P1 | Judge navigation requires browsing several documents. | A, B, E, F | Judges may not hunt for receipts. | Link the evidence index from README/Devpost/public package gates. | Link tests and `make judge-check`. | Automated in this change |
| P1 | Current hosted demo needs routine public contract verification. | B, E | Judge access depends on a live public URL. | Existing scheduled credential-free hosted smoke; run it again on final revision. | GitHub Actions smoke artifact. | Existing + final-release action |
| P1 | Benchmark baseline can be misunderstood. | A, D | Large fixture gains may look like model uplift. | State generic-baseline and synthetic limitations beside benchmark links. | Benchmark README and evidence index. | Existing + linked |
| P1 | No completed consented external review. | C, D, E | Credibility and usability evidence are thin. | Recruit two role-appropriate reviewers; retain raw records privately. | Consent-safe aggregate only if permitted. | Owner/external |
| P1 | Upstream PR has no maintainer result. | F | Bonus is weaker without reviewed contribution. | Monitor and respond to maintainers; never pressure or claim acceptance. | Upstream PR state. | External |
| P2 | Durable public DataHub OSS environment. | A, B, E | Could deepen judge reproduction, but adds cost and operational risk. | Build only with owner-approved infrastructure and security gates. | Separate deployment receipt. | Deferred |
| P2 | Additional live provider integrations. | B, D | More live receipts improve realism but create credential/safety burden. | Only execute with scoped credentials and a bounded rehearsal plan. | Published sanitized receipt. | Deferred |

## Unified non-video judge walkthrough

1. **Problem:** A data incident needs ownership, lineage, safe scope, and a durable handoff—not a generic chat answer.
2. **Public replay:** Open the hosted fixture, trigger the replay, and follow its large visible stages.
3. **DataHub role:** Inspect owner, asset, schema/runbook, and lineage context. Explain that this metadata grounds scope but does not prove cause or impact.
4. **Authority boundary:** Show that models propose and review; deterministic policy binds authorization to the exact plan and allowlists.
5. **Work and receipts:** Show clearly marked `fixture://` action receipts, write-back, and next-agent handoff.
6. **Separate live evidence:** Use the evidence index to inspect the local DataHub write-back/MCP retrieval receipt and the GitHub rehearsal receipt.
7. **Reproduce:** Run `make judge-check`. Explain that it validates deterministic code and artifacts; a pass does not claim production validation.
8. **Bonus:** Link to upstream issue #159 and PR #160, noting that it is open and unmerged.

## Candid winner-readiness verdict

**Finalist-capable, with remaining owner-only risks.**

LedgerLens has an unusually strong authority-boundary and DataHub-centrality story. It is not yet winner-safe because public reproducibility and independent usability evidence are weaker than the implementation. The highest-value next action after this package is **a clean-clone verification and public hosted-smoke receipt from the final merged revision**, followed by two consented formative reviews if time permits.

## Why LedgerLens still may not win

A judge may treat the public fixture as a polished simulation rather than proof of operational impact. The synthetic benchmark, absence of live Slack/PagerDuty/Jira demonstrations, no completed external review, and unmerged upstream PR limit the externally verifiable story. Strong documentation reduces this risk but cannot replace those evidence gaps.
