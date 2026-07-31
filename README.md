# LedgerLens

**Turn failure records into an evidence-grounded action queue.**

[![CI](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml/badge.svg)](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)

LedgerLens is a **working prototype** that ingests structured failure-ledger records into
[DataHub OSS](https://docs.datahub.com/docs/quickstart/), exposes provenance and supersession
context through the official
[DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp/), and lets an
agent produce an auditable remediation queue.

It is being built for the **DataHub Agent Hackathon** category
**Agents That Do Real Work**. The work product is not merely a chat answer: LedgerLens writes a
deterministic JSON/Markdown triage artifact containing DataHub entity references, ownership,
evidence-receipt pointers, missing-metadata warnings, and supersession state.

> **Claim boundary:** LedgerLens organizes and retrieves supplied metadata. It does not prove
> that a ledger finding is correct, independently validate Sophia-AGI, promote research results,
> or demonstrate AGI.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Why LedgerLens

Failure logs, incident registers, model cards, and experiment ledgers become hard to act on when:

- newer records supersede older conclusions without deleting history;
- ownership is missing or inconsistent;
- evidence receipts exist but are disconnected from the finding;
- malformed rows silently shift fields;
- an agent treats untrusted ledger prose as instructions;
- an ingestion timestamp is mistaken for a validation timestamp.

LedgerLens maps those records into DataHub entities and gives an agent **read-only,
provenance-aware tools** for answering operational questions:

1. Which unresolved findings are stale, unowned, or missing evidence receipts?
2. Is a finding still current, or has a newer record superseded it?
3. What is the highest-priority remediation queue by owner and finding type?
4. Which fields came from the source ledger, which came from DataHub, and which are absent?

## What the prototype includes

- A conservative ledger parser that rejects duplicate IDs and reports malformed rows.
- Stable DataHub dataset URNs for findings.
- DataHub properties, tags, ownership, evidence references, and documented supersession lineage.
- Official DataHub MCP tools for search, entity retrieval, and lineage.
- A read-only audit bridge for DataHub fields not exposed through MCP.
- Deterministic fixture mode that needs no API key and no live DataHub deployment.
- Optional LLM narration through an OpenAI-compatible endpoint, with **020s configured first**.
- JSON and Markdown remediation reports with claim ceilings preserved.
- Public-package, secret-safety, parser, and deterministic fixture checks.

See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries and
[SECURITY.md](SECURITY.md) for the threat model.

## Quick start: deterministic mode

The default developer path does **not** require DataHub, Docker, an LLM, or paid services.

Prerequisites:

- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/tomyimkc/ledgerlens.git
cd ledgerlens
make setup
make demo
make check
```

`make demo` runs the bundled sanitized fixture through the deterministic workflow and writes
artifacts under `artifacts/demo/`. The output is reproducible and must not be described as a live
DataHub result.

To inspect the CLI:

```bash
uv run ledgerlens --help
```

## Full DataHub OSS path

The live integration is explicit and separate from the deterministic path. DataHub is not
embedded in this repository. The helper wraps the official quickstart and pins
**DataHub OSS v1.6.0** by default.

Prerequisites:

- Docker with at least 8 GB memory available
- the DataHub CLI (`acryl-datahub`)

```bash
make setup
make datahub-up
make live-smoke
```

The quickstart UI is normally available at <http://localhost:9002> and GMS at
<http://localhost:8080>. Use `make datahub-status` to inspect health and
`make datahub-down` when finished.

The official quickstart is a development/testing environment, not a production deployment.
Detailed steps and failure recovery are in [docs/DATAHUB_QUICKSTART.md](docs/DATAHUB_QUICKSTART.md).

## Optional 020s LLM narration

Deterministic tool execution remains available without an LLM. To enable optional natural-language
narration, copy the environment template and provide credentials locally:

```bash
cp .env.example .env
# Set SOPHIA_020S_KEY only in .env or your shell.
export LEDGERLENS_LLM_ENABLED=true
```

Never commit `.env`, API keys, DataHub tokens, private ledger rows, or generated reports containing
sensitive material. CI runs without paid services and without live credentials.

## Example workflow

```bash
# Deterministic fixture ingestion and report generation
make demo

# Benchmark the deterministic fixture path
make benchmark

# After starting the pinned DataHub quickstart
make live-smoke

# Prepare real UI capture for the public demo
make video-tools
make capture-demo
```

Expected agent questions:

```text
Which unresolved findings have no owner or evidence receipt?
Is finding X still current? Show its supersession chain.
Build a prioritized remediation queue grouped by owner and save it.
```

The answer must distinguish:

- **source assertion** — text supplied by the ledger;
- **DataHub metadata** — ownership, tags, lineage, or audit data stored in DataHub;
- **agent inference** — a bounded prioritization or summary;
- **unknown** — absent or malformed information that must not be invented.

## Benchmarks and results

LedgerLens reports two result classes separately:

| Result class | What it establishes | What it does not establish |
|---|---|---|
| Deterministic fixture | Parser, mapping, ordering, report, and safety behavior on public fixtures | Live DataHub compatibility or real-corpus correctness |
| Live DataHub smoke | A pinned OSS deployment accepted entities and returned expected metadata | Scientific validity, production readiness, or independent validation |

Run:

```bash
make benchmark
make benchmark-summary
```

### Latest local verification — July 31, 2026

These measurements establish prototype operation on the recorded local environment only:

| Gate | Measured result |
|---|---|
| Deterministic suite | **124 passed**; Python 3.11/3.12 compatibility is enforced in CI |
| DataHub quickstart | OSS v1.6.0, ARM64-native, **58.447 s** warm restart |
| Live ingestion | **4 datasets**, **38 proposals**, **11 tags**, **1 supersession edge** |
| Live agent | **3 actionable findings**, **0 grounding conflicts**, audit metadata recovered |
| Official MCP | **6 read-only tools**; search p50 **406.381 ms** over 10 local trials |
| 020s transport smoke | `gpt-5.6-sol`, exact bounded response, **34 tokens**, **5.560 s** |
| Contest video gate | Final proof-complete cut pending; renderer enforces burned captions and generated footage below 15% |

Receipts are under [`benchmarks/results/`](benchmarks/results/) and
[`docs/results/`](docs/results/). They do not establish source-finding truth, independent
validation, production-scale reliability, model uplift, or AGI.

Templates, required fields, and publication rules are documented in
[docs/BENCHMARKS.md](docs/BENCHMARKS.md). Results remain candidate-only unless their stated gate
passes; no benchmark in this project can set `canClaimAGI` to true.

## Demo and video

The under-three-minute demo uses **real UI capture** for every product claim. Grok CLI
`/imagine-video` may create clearly labeled concept transitions, but generated footage must never
imitate or replace DataHub, terminal, test, or LedgerLens UI evidence.

- [Demo script](docs/demo/DEMO_SCRIPT.md)
- [Storyboard and shot plan](docs/demo/STORYBOARD.md)
- [Real-capture instructions](docs/demo/RECORDING.md)
- [Grok prompt files](docs/demo/grok/)

## Repository map

```text
src/ledgerlens/        application, parser, DataHub, agent, and report code
tests/                 unit and public-package checks
docs/                  setup, benchmark, demo, and Devpost materials
scripts/               quickstart, safety, benchmark, and recording automation
.github/workflows/     offline-first CI
```

## Disclosure

The **failure-ledger concept and source corpus predate the contest** and come from the Sophia-AGI
project. They are input material, not newly created contest work. All LedgerLens contest-period
application code, DataHub mapping, agent integration, tests, packaging, documentation, and demo
automation are newly built in this repository.

No prior adapter implementation is imported, copied, or treated as implementation truth. See
[DISCLOSURE.md](DISCLOSURE.md) for the full boundary.

## Contributing and security

- [CONTRIBUTING.md](CONTRIBUTING.md) — development workflow and claim discipline
- [SECURITY.md](SECURITY.md) — prompt injection, secrets, malformed input, read-only defaults
- [ARCHITECTURE.md](ARCHITECTURE.md) — trust boundaries and provenance semantics

## License

LedgerLens is licensed under the [Apache License 2.0](LICENSE).

The Sophia-AGI source material is pre-existing and is disclosed separately. Contributors must
confirm that any new fixture material is safe and legally eligible for public redistribution.
