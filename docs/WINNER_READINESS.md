# LedgerLens non-video winner-readiness scorecard

**Assessment date:** August 9, 2026 (supersedes the August 3 scorecard)
**Scope:** Non-video public repository, hosted fixture, recorded receipts, and reproducibility.
**Scoring rule:** Five core criteria are scored independently. The open-source contribution is a separate bonus, because the official rules call it a bonus even while listing criteria as equally weighted. These are internal readiness assessments, not official judging scores.
**Method note:** The August 1 draft rated the five-core average at 7.8. An adversarial
re-audit on August 3 found that figure optimistic because it scored code rather than judge-visible
proof. The August 9 refresh includes the produced E-16 rehearsal, public video URL, recorded Agent
I/O page, interactive server-evaluated Seal Lab, and E-20 DataHub Context Cut. It remains
conservative because the public incident state is a fixture and no production outcome or
independent validation is claimed.

## Current scorecard

| Criterion | Score | Confidence | Evidence a judge can access | Remaining proof gap | Highest-value next improvement | Status |
|---|---:|---|---|---|---|---|
| A. Meaningful DataHub use and write-back | 7.5 / 10 | Medium | Context flow; **tool-specific DataHub evidence contracts + public Context Cut (E-20)**; real-pipeline gate ablation (E-15); local DataHub OSS write-back + official-MCP retrieval (E-07); Agent Context Kit framing | The public Space still does not contact DataHub; E-20 is a synthetic controlled ablation over a recorded plan | Add live DataHub read/write-back to the same supervised run only on an owner-controlled instance | Finalist-capable |
| B. Technical execution and end-to-end functionality | 7.8 / 10 | High | Typed orchestrator; plan-exact gate; per-tool fact contracts; abstention support; deterministic tests; E-15; **one-run live fanout across all four providers (E-16)**; CI; hosted smoke | A single bounded rehearsal per provider; no sustained-reliability or scale evidence | Add a live DataHub read/write-back to the same run for full read→act→write-back in one receipt | Finalist-capable |
| C. Originality beyond DataHub built-ins | 8.0 / 10 | Medium | Exact-plan authorization; verifier quorum; HMAC-bound adapters; next-agent handoff; **Seal Lab + Context Cut** make plan authority and DataHub necessity falsifiable in-browser | No independent reviewer has assessed differentiation | Complete two consented formative reviews without overstating them | Winner-contending concept |
| D. Real-world usefulness | 6.2 / 10 | Medium | Concrete on-call persona; ownership/lineage context; bounded work with explicit unknowns; one four-provider rehearsal; "point it at your own DataHub" path | Synthetic incidents; no real user study or production outcome | Recruit two role-appropriate formative reviewers and publish only consented aggregate findings | Contender |
| E. Submission quality and reproducibility | 7.8 / 10 | High | Public Apache-2.0 repo/Space/video; Seal Lab; Context Cut; recorded Agent I/O; examples; one-command rebuild; CI; secret scan; evidence index; clean-clone receipt | Public YouTube playback still needs a final incognito check; final release/package alignment and merged hosted smoke are time-sensitive | Run final merged hosted smoke, verify public video/project URLs in a clean browser, and record the release SHA | Finalist-capable |
| F. Open-source contribution bonus | 4.5 / 10 | High | Public upstream issue #159 and PR #160; the three Copilot review comments on #160 were addressed in `fe49bac` | PR is open, review-required, and unmerged; no maintainer acceptance | Keep the contribution accurately linked; respond only to justified maintainer feedback | Contender bonus |

**Five-core average:** **7.5 / 10**
**Bonus:** **4.5 / 10** (reported separately; not folded into the core average)

## Why the score is not higher

- The hosted judge experience remains a **fixture replay**, not a live DataHub-backed demo. E-20
  makes DataHub evidence load-bearing in the clickable artifact, but the context itself is synthetic.
- A single supervised run has now executed one bounded action against all four providers (E-16), but each is one rehearsal action — there is no sustained-reliability, scale, or real-adoption evidence.
- Both benchmarks and E-20 context cuts are deterministic and synthetic. E-20 holds a recorded
  model plan fixed and does not show adaptive re-planning.
- External-evaluation infrastructure is ready, but no consented independent review result exists.
- The upstream contribution remains an open, unmerged PR.
- The 170-second local source video was inspected for duration, captions, and representative
  frames. Public YouTube playback still requires a final clean/incognito-browser check.

## P0/P1/P2 gap matrix

| Priority | Gap | Rubric affected | Why it matters | Exact change or owner action | Acceptance evidence | Disposition |
|---|---|---|---|---|---|---|
| P0 | Headline benchmark mechanism was undisclosed (scripted responders). | A, E | A judge inspecting the code could read the gap as manufactured. | Disclose the mechanism beside the numbers on every surface; add a real-pipeline benchmark. | `benchmarks/incident_commander/README.md`; E-15. | **Done (PR #23/#24)** |
| P0 | Public demo shows no DataHub involvement. | A | The one clickable artifact never touches DataHub. | Run a supervised live-DataHub session on the owner's own instance; link the receipt. | Live receipt + `docs/LIVE_DATAHUB_PUBLIC.md`. | Owner-only |
| P0 | Only GitHub had a produced live provider receipt. | B, D | "Agents that do real work" wants demonstrated action. | Run the one-run rehearsal across all four providers with scoped credentials. | E-16 receipt: GitHub #29, Slack, PagerDuty, Jira KAN-2. | **Done** — produced 2026-08-03 |
| P0 | Final submission video/project URLs and eligibility need a last clean-browser review. | E | A recorded URL is not the same as verified playback and account eligibility. | Owner performs the last clean-browser/account review before the deadline. | Public playback plus Devpost project state. | Video URL + published state done; final owner review remains |
| P1 | Judges may not hunt for receipts. | A, B, C, E | Evidence must be felt before a judge leaves the page. | Put Seal Lab and DataHub Context Cut immediately after the uniqueness pitch. | E-19 and E-20; `examples/README.md`. | **Implemented; public deployment pending** |
| P1 | Submission did not speak DataHub's own vocabulary. | A, C, D | DataHub-team judges reward their own framing. | Cite the Agent Context Kit and the "context problem" framing, accurately. | README/ARCHITECTURE. | **Done (PR #24)** |
| P1 | No completed consented external review. | C, D, E | Credibility/usability evidence is thin. | Recruit two role-appropriate reviewers; retain raw records privately. | Consent-safe aggregate only if permitted. | Owner/external |
| P1 | Upstream PR has no maintainer result. | F | Bonus is weaker without a reviewed contribution. | Monitor and respond to maintainers; never pressure or claim acceptance. | Upstream PR state. | External |
| P1 | Final clean-clone/hosted-smoke receipt from the final revision. | B, E | Reproducibility must match the submitted commit. | Re-run clean-clone + hosted smoke on the final revision and link them. | Receipts referenced from the evidence index. | Final-release action |
| P2 | Durable public DataHub OSS environment. | A, B, E | Deepens reproduction but adds cost/operational risk. | Build only with owner-approved infrastructure and security gates. | Separate deployment receipt. | Deferred |

## Unified non-video judge walkthrough

1. **Problem:** A data incident needs ownership, lineage, safe scope, and a durable handoff—not a generic chat answer. (DataHub frames this as a context problem.)
2. **Public replay:** Open the hosted fixture, trigger the replay, and follow its large visible stages.
3. **DataHub role:** Inspect owner, asset, schema/runbook, and lineage context. Explain that this metadata grounds scope but does not prove cause or impact.
4. **Authority boundary:** Use Seal Lab to show exact-plan binding.
5. **DataHub necessity:** Use Context Cut to remove owner or lineage while holding the model plan fixed; current policy denies because required catalog facts are absent.
6. **Work and receipts:** Show clearly marked `fixture://` action receipts, write-back, and next-agent handoff.
7. **Real pipeline, not scripts:** Point to E-15 and the one-run provider fanout E-16.
8. **Separate live evidence:** Inspect the local DataHub write-back/MCP retrieval receipt and E-16.
9. **Reproduce:** Run `make judge-check`; it rebuilds E-20 without credentials before the gates.
10. **Bonus:** Link to upstream issue #159 and PR #160, noting that it is open and unmerged.

## Candid winner-readiness verdict

**Finalist-capable, with remaining public-proof and final-release risks.**

The authority-boundary and DataHub-centrality story is now judge-testable: Seal Lab tests plan
drift, while Context Cut tests whether owner/lineage evidence is actually required. E-16 establishes
one bounded supervised four-provider run. It is not winner-safe because the clickable context is
still synthetic, the live run is one rehearsal, and there is no completed external review or
merged upstream PR.

## Why LedgerLens still may not win

A judge may still treat the public fixture as a polished simulation rather than proof of
operational impact. The one supervised provider rehearsal and local DataHub write-back are narrow
evidence, not sustained operation or recovery. The synthetic benchmarks, absence of a completed
external review, and unmerged upstream PR limit the externally verifiable story. The Seal Lab
improves inspectability; it does not erase those gaps.
