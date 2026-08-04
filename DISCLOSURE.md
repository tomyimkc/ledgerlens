# Pre-existing Work and Contest-Period Disclosure

## Summary

LedgerLens is a newly created, public Apache-2.0 project for the DataHub Agent Hackathon. It uses
pre-existing Sophia-AGI ideas and selected sanitized source material as **input**, while the
LedgerLens implementation is newly built during the contest period.

LedgerLens is a working prototype, not independent validation of Sophia-AGI or its failure ledger.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Pre-existing material

The following existed before LedgerLens:

1. **The failure-ledger concept.** Sophia-AGI maintains a structured record of failures, null
   results, unresolved defects, evidence receipts, and required responses.
2. **The original Sophia-AGI corpus.** LedgerLens incorporates ideas and selected sanitized source
   material from the author's separate open-source research project,
   [Sophia-AGI](https://github.com/tomyimkc/sophia-agi) (a candidate-only project;
   `canClaimAGI: false`). The source ledger and related provenance discipline are pre-existing
   research/project material used as **input**, not imported implementation code.
3. **General no-overclaim methodology.** Concepts such as candidate-only status, explicit claim
   ceilings, preserved negative results, and evidence-receipt references predate this contest.
4. **Historical infrastructure observations.** Earlier exploratory work reported that a DataHub
   OSS quickstart could run and identified possible packaging/MCP-surface limitations. LedgerLens
   revalidates current behavior rather than treating those observations as current proof.
5. **A reused Hugging Face Space slot.** The public demo is hosted on a Space account slot the
   author already owned, previously used for an unrelated personal project
   (`tomyimkc/sophia-governance-gate`). With the owner's explicit authorization it was renamed to
   `tomyimkc/ledgerlens-incident-commander` and redeployed; the prior contents were preserved on
   the `backup/governance-gate-20260731` branch rather than destroyed. Only the hosting slot is
   pre-existing — every byte of the deployed LedgerLens application was written during the contest
   period and is built from this repository by
   [`.github/workflows/deploy-hf-space.yml`](.github/workflows/deploy-hf-space.yml).

Only material that is safe and eligible for public redistribution may be included in this
repository. The bundled fixture is intentionally small and sanitized.

## Newly created in LedgerLens

The following contest-period work is newly built in this repository:

- conservative ledger parsing and normalized schemas;
- DataHub entity, property, ownership, tag, and lineage mapping;
- ingestion and read-only retrieval integration;
- official DataHub MCP Server integration;
- read-only audit metadata bridge;
- deterministic fixture backend;
- remediation-queue agent and report generation;
- CLI and web demonstration surfaces;
- deterministic and live-smoke tests;
- benchmark receipts and result presentation;
- Docker, CI, documentation, security, and public packaging;
- demo script, real UI capture automation, Grok prompt assets, and video assembly scaffolding.

## No reused adapter implementation

No prior DataHub ledger adapter implementation is imported, copied, vendored, or treated as
implementation truth. LedgerLens is implemented from the public project contract and revalidated
interfaces.

This distinction matters: a historical document or claim is not artifact evidence. The project
does not state that a working adapter predated this repository.

## AI-assisted development

AI coding assistants may be used for implementation, review, documentation, test generation, and
demo asset planning. Human/operator review remains responsible for:

- licensing and disclosure;
- secret handling;
- public release;
- contest eligibility;
- interpreting benchmark receipts;
- the final Devpost submission.

Grok CLI `/imagine-video` may be used for clearly labeled concept visuals. Product functionality
must be shown through real captures of the running LedgerLens/DataHub interfaces, never synthetic
imitation.

## Data and privacy

The public fixture must not contain:

- private identities or contact information;
- API keys or access tokens;
- private repository paths that reveal secrets;
- confidential evidence receipts;
- private prompts, holdouts, or unpublished evaluation material.

Operators may point LedgerLens at a private ledger locally, but private source text must not be
sent to an external LLM unless the operator has explicitly reviewed and authorized that transfer.

## Claim boundary

LedgerLens can demonstrate that:

- a fixture was parsed according to deterministic rules;
- metadata was emitted to or retrieved from a particular DataHub deployment;
- a report was generated from those records;
- missing or conflicting metadata was surfaced.

LedgerLens cannot demonstrate that:

- the underlying finding is true or false;
- referenced evidence independently validates a claim;
- an ingestion timestamp is a scientific validation timestamp;
- Sophia-AGI has achieved validated uplift or AGI;
- the prototype is production-ready.

## License boundary

LedgerLens code and original project documentation are available under Apache-2.0. Pre-existing
Sophia-AGI material remains subject to its source repository's licensing and provenance. Any
incorporated fixture row must be reviewed for redistribution eligibility and attributed in the
fixture metadata.
