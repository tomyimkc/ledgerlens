# DataHub Agent Hackathon Submission Checklist

Official deadline:

- **August 10, 2026 at 5:00 PM EDT**
- **August 11, 2026 at 5:00 AM HKT**

Operational deadline with a 24-hour buffer:

- **August 9, 2026 at 5:00 PM EDT**
- **August 10, 2026 at 5:00 AM HKT**

The owner must complete account, team, eligibility, and final-submit actions.

## Eligibility and project identity

- [ ] Devpost account is active.
- [ ] Owner has joined the DataHub Agent Hackathon.
- [ ] Team members and representative details are correct.
- [ ] Eligibility restrictions have been reviewed.
- [ ] Project was newly created during the submission period.
- [ ] Category is **Agents That Do Real Work**.
- [ ] Project name is **LedgerLens**.
- [ ] Tagline is “Turn failure records into an evidence-grounded action queue.”

## Required DataHub components

- [ ] Project uses DataHub OSS.
- [ ] Project uses at least one approved agent component.
- [ ] Official DataHub MCP Server is shown in code and demo.
- [ ] Live demo uses a pinned DataHub version.
- [ ] Mutation tools are disabled by default.
- [ ] The writeup explains the read-only audit bridge without implying MCP exposes those fields.

## Public repository

- [ ] Repository is public: `https://github.com/tomyimkc/ledgerlens`.
- [ ] Root `LICENSE` is Apache-2.0.
- [ ] Default branch contains the final submission.
- [ ] README setup works from a clean clone.
- [ ] CI is green on Python 3.11 and 3.12.
- [ ] Release tag is published.
- [ ] Repository and history pass secret review.
- [ ] No private ledger rows, API keys, tokens, or unpublished holdouts are present.
- [ ] `DISCLOSURE.md` is linked from README.
- [ ] Pre-existing Sophia material is disclosed in the Devpost text.
- [ ] No claim says a prior adapter implementation existed.

## Functional verification

- [ ] `make setup` succeeds from a clean clone.
- [ ] `make check` succeeds.
- [ ] `make demo` produces deterministic JSON and Markdown artifacts.
- [ ] `make benchmark` produces a deterministic receipt.
- [ ] DataHub quickstart starts from the documented command.
- [ ] Fixture ingestion succeeds against the pinned DataHub version.
- [ ] MCP search/entity/lineage round trip succeeds.
- [ ] Audit metadata retrieval is labeled by semantic and channel.
- [ ] Remediation report includes URNs, owner state, receipt state, and supersession.
- [ ] Missing fields remain unknown and are not invented.
- [ ] Live DataHub receipt is separate from deterministic fixture receipt.

## Claim and safety review

- [ ] “Working prototype” appears in README and submission.
- [ ] “Not independent validation” appears in README and submission.
- [ ] `candidateOnly: true` is preserved.
- [ ] `canClaimAGI: false` is preserved.
- [ ] No AGI, validated uplift, promotion, or production-readiness claim appears.
- [ ] Evidence receipts are described as references, not endorsements.
- [ ] Ingestion timestamps are not called validation timestamps.
- [ ] Ledger prompt injection is demonstrated or tested.
- [ ] Malformed and duplicate row handling is demonstrated or tested.

## Demo video

- [ ] Final runtime is below 3:00; target is 2:40.
- [ ] Narration and captions are in English.
- [ ] Product functionality is shown through real UI/terminal capture.
- [ ] Grok-generated footage is limited to clearly labeled concept visuals.
- [ ] Generated footage never imitates DataHub or LedgerLens functionality.
- [ ] DataHub UI visibly shows ingested fixture entities.
- [ ] Agent visibly traces supersession.
- [ ] Agent visibly writes a remediation artifact.
- [ ] Deterministic test/result receipt is shown accurately.
- [ ] No private path, account detail, key, token, notification, or browser extension is visible.
- [ ] Video is public on YouTube, Vimeo, or Youku.
- [ ] Video link works in an incognito browser.
- [ ] Captions are legible at 1080p.

## Devpost content

- [ ] English project description is complete.
- [ ] Public project URL works.
- [ ] Public repository URL works.
- [ ] Public video URL works.
- [ ] Screenshots are clear and safe.
- [ ] “How we built it” names DataHub OSS and MCP.
- [ ] “Challenges” covers provenance semantics and prompt injection.
- [ ] Pre-existing-work disclosure is explicit.
- [ ] Apache-2.0 is stated.
- [ ] Technology list is accurate.
- [ ] No planned feature is described as already working.

## Final release and submission

- [ ] Record final commit SHA: `________________`.
- [ ] Record release tag: `________________`.
- [ ] Record DataHub version: `________________`.
- [ ] Record deterministic receipt path: `________________`.
- [ ] Record live-smoke receipt path: `________________`.
- [ ] Record video URL: `________________`.
- [ ] Record project URL: `________________`.
- [ ] Owner reviews the complete submission.
- [ ] Owner clicks final Submit.
- [ ] Submission receipt is saved.
- [ ] Receipt timestamp is before the operational deadline.
- [ ] Final Devpost page works in an incognito browser.
