# LedgerLens non-video winner-readiness scorecard

**Assessment date:** August 3, 2026 (supersedes the August 1 provisional scores)
**Scope:** Non-video public repository, hosted fixture, recorded receipts, and reproducibility.
**Scoring rule:** Five core criteria are scored independently. The open-source contribution is a separate bonus, because the official rules call it a bonus even while listing criteria as equally weighted. These are internal readiness assessments, not official judging scores.
**Method note:** The August 1 draft rated the five-core average at 7.8. An adversarially-verified re-audit on August 3 — every proposed gap refuted by an independent reader of the source — found that figure optimistic (it scored the code, not what a judge can verify) and reset it to ~5.8. The scores below are the honest state **after** the August 3 improvements (real-pipeline benchmark, benchmark honesty disclosure, `examples/`, DataHub agent-context framing, and the offline-tested live provider rehearsal). They are deliberately conservative.

## Current scorecard

| Criterion | Score | Confidence | Evidence a judge can access | Remaining proof gap | Highest-value next improvement | Status |
|---|---:|---|---|---|---|---|
| A. Meaningful DataHub use and write-back | 6.5 / 10 | Medium | Context flow; **real-pipeline gate ablation (E-15)**; local DataHub OSS write-back + official-MCP retrieval (E-07); agent-context/MCP framing tied to DataHub's own Agent Context Kit | The public Space never contacts DataHub (fixture only); DataHub-in-the-loop is provable from source/receipts, not from the clickable demo | Run the supervised live-DataHub session on the owner's own instance and link its receipt | Finalist-capable |
| B. Technical execution and end-to-end functionality | 7.5 / 10 | High | Typed orchestrator; deterministic authority tests; real-pipeline `PolicyGate`/`VerifierPanel` benchmark; **produced one-run live fanout across all four providers (E-16)**; CI; hosted smoke | A single bounded rehearsal per provider; no sustained-reliability or scale evidence | Add a live DataHub read/write-back to the same run for full read→act→write-back in one receipt | Finalist-capable |
| C. Originality beyond DataHub built-ins | 7.0 / 10 | Medium | Exact-plan authorization; verifier quorum; allowlists; HMAC-bound adapters; next-agent handoff; **explicit contrast vs. DataHub's Actions Framework and generic LLM agents** (README) | No independent reviewer has assessed differentiation | Complete two consented formative reviews without overstating them | Finalist-capable |
| D. Real-world usefulness | 6.0 / 10 | Medium | Concrete on-call persona and worked incident; ownership/lineage context; bounded work with explicit unknowns; **"point it at your own DataHub" adoption path** | Synthetic incidents; no real user study or production outcome | Recruit two role-appropriate formative reviewers and publish only consented aggregate findings | Contender |
| E. Submission quality and reproducibility | 6.5 / 10 | High | Public Apache-2.0 repo; **`examples/` folder** (rules-recommended); one-command demo; CI; secret scan; readiness check; canonical evidence index; **clean-clone reproduction verified**; on-thesis repo About/topics | Final release/package alignment and the final hosted-smoke receipt from the merged final revision are not yet recorded | Run and publish final clean-clone/hosted-smoke receipts from the final revision | Contender |
| F. Open-source contribution bonus | 4.5 / 10 | High | Public upstream issue #159 and PR #160; the three Copilot review comments on #160 were addressed in `fe49bac` | PR is open, review-required, and unmerged; no maintainer acceptance | Keep the contribution accurately linked; respond only to justified maintainer feedback | Contender bonus |

**Five-core average:** **6.6 / 10**
**Bonus:** **4.5 / 10** (reported separately; not folded into the core average)

## Why the score is not higher

- The hosted judge experience proves a **fixture replay**, not a live DataHub-backed demo; DataHub-in-the-loop must be taken from source and receipts rather than seen in the clickable artifact.
- A single supervised run has now executed one bounded action against all four providers (E-16), but each is one rehearsal action — there is no sustained-reliability, scale, or real-adoption evidence.
- Both benchmarks are deterministic and synthetic. The real-pipeline benchmark exercises the production gate, but its OFF arm fails by construction — it proves the fail-closed gate, not model capability.
- External-evaluation infrastructure is ready, but no consented independent review result exists.
- The upstream contribution remains an open, unmerged PR.
- Final release, clean-clone-of-final-revision receipt, video URL, and Devpost submit remain owner-controlled, time-sensitive work.

## P0/P1/P2 gap matrix

| Priority | Gap | Rubric affected | Why it matters | Exact change or owner action | Acceptance evidence | Disposition |
|---|---|---|---|---|---|---|
| P0 | Headline benchmark mechanism was undisclosed (scripted responders). | A, E | A judge inspecting the code could read the gap as manufactured. | Disclose the mechanism beside the numbers on every surface; add a real-pipeline benchmark. | `benchmarks/incident_commander/README.md`; E-15. | **Done (PR #23/#24)** |
| P0 | Public demo shows no DataHub involvement. | A | The one clickable artifact never touches DataHub. | Run a supervised live-DataHub session on the owner's own instance; link the receipt. | Live receipt + `docs/LIVE_DATAHUB_PUBLIC.md`. | Owner-only |
| P0 | Only GitHub had a produced live provider receipt. | B, D | "Agents that do real work" wants demonstrated action. | Run the one-run rehearsal across all four providers with scoped credentials. | E-16 receipt: GitHub #29, Slack, PagerDuty, Jira KAN-2. | **Done** — produced 2026-08-04 |
| P0 | Final submission lacks owner video URL, eligibility confirmation, and submit receipt. | E | Required material and eligibility cannot be automated. | Owner completes checklist; do not evaluate the video itself. | Devpost and owner receipts. | Owner-only |
| P1 | Judges may not hunt for receipts. | A, B, E, F | Evidence must be one click away. | Canonical evidence index + `examples/` folder linked from README. | E-01..E-16; `examples/README.md`. | **Done** |
| P1 | Submission did not speak DataHub's own vocabulary. | A, C, D | DataHub-team judges reward their own framing. | Cite the Agent Context Kit and the "context problem" framing, accurately. | README/ARCHITECTURE. | **Done (PR #24)** |
| P1 | No completed consented external review. | C, D, E | Credibility/usability evidence is thin. | Recruit two role-appropriate reviewers; retain raw records privately. | Consent-safe aggregate only if permitted. | Owner/external |
| P1 | Upstream PR has no maintainer result. | F | Bonus is weaker without a reviewed contribution. | Monitor and respond to maintainers; never pressure or claim acceptance. | Upstream PR state. | External |
| P1 | Final clean-clone/hosted-smoke receipt from the final revision. | B, E | Reproducibility must match the submitted commit. | Re-run clean-clone + hosted smoke on the final revision and link them. | Receipts referenced from the evidence index. | Final-release action |
| P2 | Durable public DataHub OSS environment. | A, B, E | Deepens reproduction but adds cost/operational risk. | Build only with owner-approved infrastructure and security gates. | Separate deployment receipt. | Deferred |

## Unified non-video judge walkthrough

1. **Problem:** A data incident needs ownership, lineage, safe scope, and a durable handoff—not a generic chat answer. (DataHub frames this as a context problem.)
2. **Public replay:** Open the hosted fixture, trigger the replay, and follow its large visible stages.
3. **DataHub role:** Inspect owner, asset, schema/runbook, and lineage context. Explain that this metadata grounds scope but does not prove cause or impact.
4. **Authority boundary:** Show that models propose and review; deterministic policy binds authorization to the exact plan and allowlists — and how that differs from DataHub's Actions Framework and a generic LLM agent.
5. **Work and receipts:** Show clearly marked `fixture://` action receipts, write-back, and next-agent handoff.
6. **Real pipeline, not scripts:** Point to the real-pipeline benchmark (E-15) and the offline-tested one-run provider fanout (E-16); read the `examples/` folder without running anything.
7. **Separate live evidence:** Use the evidence index to inspect the local DataHub write-back/MCP retrieval receipt and the GitHub rehearsal receipt.
8. **Reproduce:** Run `make judge-check`. A pass validates deterministic code and artifacts; it does not claim production validation.
9. **Bonus:** Link to upstream issue #159 and PR #160, noting that it is open and unmerged.

## Candid winner-readiness verdict

**Finalist-capable, with remaining owner-only risks.**

The authority-boundary and DataHub-centrality story is strong, and the August 3 work removed the integrity risk in the flagship benchmark, added evidence that exercises the real pipeline, and made the submission speak DataHub's own language. It is not yet winner-safe because the two highest-value proofs — a live DataHub-backed demo and produced live provider receipts — are built but not yet *run*, and there is no completed external review or merged upstream PR. The remaining distance to winner is now dominated by owner-controlled, real-world artifacts rather than engineering.

## Why LedgerLens still may not win

A judge may treat the public fixture as a polished simulation rather than proof of operational impact. Until the owner runs the supervised live-DataHub session and the one-run provider rehearsal, the live story remains one closed GitHub issue plus one local DataHub write-back. The synthetic benchmarks, the absence of a completed external review, and the unmerged upstream PR limit the externally verifiable story. Strong, honest documentation reduces this risk but cannot replace those artifacts.
