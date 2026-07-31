# Devpost Submission Draft

## Project name

**LedgerLens**

## Tagline

**Turn failure records into an evidence-grounded action queue.**

## Category

**Agents That Do Real Work**

## One-line summary

LedgerLens ingests a structured failure ledger into DataHub and gives an agent enough provenance,
ownership, evidence, and supersession context to write a prioritized remediation queue.

## Short description

Teams are good at recording failures and much worse at keeping those records actionable. Findings
become stale, ownership disappears, evidence receipts drift away from conclusions, and newer rows
supersede older ones without preserving a usable chain.

LedgerLens turns those records into DataHub entities. A read-only agent uses the official DataHub
MCP Server to search findings, retrieve metadata, and trace lineage, then writes a deterministic
JSON/Markdown remediation report. It flags missing owners and receipts, explains supersession, and
labels the origin and semantic meaning of every timestamp.

The result is a working prototype for auditable operational triage—not an independent validator of
the underlying findings.

## Inspiration

Research, ML, platform, and incident-response teams accumulate negative results and unresolved
findings. Those records are valuable precisely because they document what did not work, but they
often live in append-heavy Markdown, tickets, or ad hoc spreadsheets.

We wanted an agent that would not flatten that history into a confident summary. It should preserve
provenance, expose uncertainty, recognize supersession, and produce work that another person can
inspect and execute.

## What it does

LedgerLens:

1. parses a structured failure ledger conservatively;
2. rejects duplicate IDs and quarantines structurally ambiguous rows;
3. maps findings to stable DataHub dataset URNs;
4. attaches status, type, ownership, evidence references, and claim ceilings;
5. represents supersession through a documented lineage convention;
6. retrieves entities and lineage through the official DataHub MCP Server;
7. obtains additional audit context through a read-only DataHub API bridge when needed;
8. builds a prioritized remediation queue;
9. writes JSON and Markdown artifacts with DataHub references and explicit missing values.

Example questions:

- Which unresolved findings have no owner or evidence receipt?
- Is this finding still current? Show its supersession chain.
- What should each owner address next, and why?

## How we built it

### Data and parsing

The public demo uses a small sanitized fixture derived from the structure of a pre-existing
Sophia-AGI failure ledger. The parser treats every row as untrusted data. It preserves original
text, rejects duplicate IDs, detects malformed delimiters, and refuses to invent shifted fields.

### DataHub model

Each finding becomes a DataHub dataset entity with a stable URN. Structured properties and tags
carry status, finding type, parse state, and claim boundaries. Ownership maps to DataHub ownership.
Evidence receipts remain references rather than being presented as verified evidence.

Supersession uses an explicit property plus a documented lineage convention so consumers do not
confuse “newer finding supersedes older finding” with ordinary pipeline lineage.

### Agent integration

The agent uses the official DataHub MCP Server for search, entity retrieval, and lineage. Mutation
tools stay disabled. A small read-only bridge retrieves audit fields that are not available through
the MCP response, while preserving their semantics as DataHub ingestion metadata.

Filtering, missing-field detection, supersession traversal, and queue ordering are deterministic.
An optional 020s/OpenAI-compatible model can narrate retrieved facts, but it cannot change source
status, ownership, evidence, or claim ceilings.

### Reproducibility

Default CI runs on Python 3.11 and 3.12 without paid services or live DataHub. It covers lint,
unit tests, package build, secret safety, public-package checks, and deterministic fixtures. Live
DataHub smoke tests produce a separate receipt with the exact version and limitations.

## Challenges

### Provenance is not validation

DataHub can tell us when metadata was ingested and who wrote an aspect. That timestamp is useful,
but it is not the date a scientific or operational assertion became true. LedgerLens labels those
semantics instead of compressing them into a generic “verified at” field.

### Ledger text is an attack surface

A ledger row can contain malformed Markdown, unsafe links, or prompt injection. The architecture
keeps ledger prose in an untrusted data channel, disables arbitrary evidence fetching, and enforces
tool permissions outside the model prompt.

### Supersession is not ordinary lineage

DataHub lineage is a useful visualization and retrieval surface, but record supersession is not a
data transformation. LedgerLens therefore emits an explicit relationship property and documents
the convention on every relevant entity/report.

### Honest demos need two result classes

A deterministic fixture can prove parser and report behavior. Only a live smoke test can show that
a pinned DataHub deployment accepts and returns the metadata. Neither establishes the truth of the
underlying findings. We keep those receipts separate.

## Accomplishments

- A complete ledger-to-DataHub-to-agent vertical slice.
- Conservative parsing that exposes defects instead of silently shifting fields.
- An agent that produces a real remediation artifact.
- Read-only MCP defaults and explicit audit semantics.
- Deterministic reproduction without credentials.
- Public Apache-2.0 packaging and an automated real-UI demo capture workflow.

These accomplishments describe prototype mechanics only. They are not independent validation,
production-readiness, uplift, or AGI claims.

## What we learned

The most useful metadata for an agent is often not the most glamorous: stable IDs, owners, missing
fields, source locations, timestamp semantics, and explicit supersession edges. Once those are
preserved, an agent can do bounded operational work without pretending to adjudicate the truth of
the source.

We also learned that a green parser is not enough if it silently deduplicates IDs or shifts fields
on malformed rows. Failing closed is part of the product, not only test hygiene.

## What's next

- Evaluate the mapping on additional sanitized incident and experiment ledgers.
- Add configurable DataHub custom aspects after the prototype contract stabilizes.
- Expand policy tests for prompt injection and private-data handling.
- Test team workflows around remediation acceptance and closure.
- Consider a separate upstream contribution only after the contest-critical path is stable.

## Built with

- DataHub OSS
- DataHub MCP Server
- Python 3.11/3.12
- Pydantic
- Typer
- FastAPI
- Docker
- pytest
- Ruff
- optional 020s OpenAI-compatible API
- Playwright and ffmpeg for real UI capture
- Grok CLI for clearly labeled concept-video assets

## Pre-existing work disclosure

The failure-ledger concept, the original Sophia-AGI corpus, and its general provenance/no-overclaim
discipline predate this hackathon. The public demo uses a small sanitized fixture derived from that
structure.

All LedgerLens application code, DataHub mapping, agent integration, tests, packaging,
documentation, and demo automation are newly built in this public repository during the contest
period. No pre-existing DataHub adapter implementation was imported or reused.

See `DISCLOSURE.md` for the full boundary.

## Claim boundary

```yaml
candidateOnly: true
canClaimAGI: false
```

LedgerLens is a working prototype. It does not independently validate Sophia-AGI, the source
ledger, or referenced evidence.

## Submission links

Complete before submission:

- Public repository: `https://github.com/tomyimkc/ledgerlens`
- Project URL: `TODO`
- Public video (under three minutes): `TODO`
- Release tag: `TODO`
- Final commit: `TODO`
- Submission receipt: `TODO`
