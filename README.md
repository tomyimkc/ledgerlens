# LedgerLens

## Autonomous Data Incident Commander

[![CI](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml/badge.svg)](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)

**LedgerLens turns a DataHub-observed data incident into bounded, auditable response work.**

The working prototype follows one visible chain:

```text
DataHub incident + catalog context
  -> planner
  -> verifier variants
  -> deterministic authorization policy
  -> GitHub / Slack / PagerDuty / Jira action fanout
  -> DataHub write-back
  -> next-agent memory
```

It is entered in the DataHub Agent Hackathon category **Agents That Do Real Work**.
The official deadline is **August 10, 2026 at 5:00 PM EDT**. The submission must include a
public project URL, a public Apache-2.0 repository, an English text description, and a public
demo video under three minutes. LedgerLens's release plan keeps judge access free through
**August 31, 2026**.

- [Official competition](https://datahub.devpost.com/)
- [Official rules and judging criteria](https://datahub.devpost.com/rules)
- [v0.2.0 grand-prize release](https://github.com/tomyimkc/ledgerlens/releases/tag/v0.2.0)
- [Upstream DataHub MCP issue #159](https://github.com/acryldata/mcp-server-datahub/issues/159)
- [Upstream DataHub MCP PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160)
- [Judge-ready submission package](docs/DEVPOST_SUBMISSION.md)
- [Architecture and trust boundaries](ARCHITECTURE.md)

> **Claim boundary:** the public one-command Incident Commander demo is a deterministic fixture
> replay. Its `fixture://` action, write-back, and memory receipts are not live provider receipts.
> Provider adapters and controlled DataHub mutation paths are implemented, but this README does
> not claim that a current hosted run contacted GitHub, Slack, PagerDuty, Jira, or DataHub unless
> a separately published run receipt proves it.

```yaml
candidateOnly: true
canClaimAGI: false
```

## What judges see

LedgerLens presents one incident workspace instead of a chatbot transcript:

1. **DataHub context** — the root asset, owner, tier, schema, documentation, freshness assertion,
   and downstream lineage are collected with source labels and explicit unknowns.
2. **Planner proposal** — a bounded plan proposes collaboration records and metadata write-back,
   not production rollback or an unproven root-cause fix.
3. **Verifier variants** — structured verifier outputs check evidence coverage, unknowns, and
   action scope. Distinct configured model identifiers do not establish provider-family
   independence.
4. **Deterministic policy** — exact action type, target, parameters, risk, evidence references,
   quorum, confidence, and plan fingerprint must pass before execution.
5. **Action fanout** — typed adapters support GitHub issue creation, Slack messages, PagerDuty
   events/notes, and Jira issues with previews, idempotency, bounded retries, and sanitized
   receipts.
6. **DataHub write-back** — an explicit, disabled-by-default mutation path records a bounded
   incident snapshot and receipt against allowlisted DataHub entities.
7. **Next-agent memory** — the handoff preserves known facts, unknowns, completed work, receipt
   references, and the next verification actions.

AI output is advisory. It cannot authorize itself, expand target allowlists, relabel unknowns as
facts, or raise the claim ceiling.

## Run the judge demo

Prerequisites:

- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/)

From a clean clone:

```bash
git clone https://github.com/tomyimkc/ledgerlens.git
cd ledgerlens
make setup
make incident-demo
```

`make incident-demo` opens <http://127.0.0.1:8000/incident>. Click **Replay trigger** once. In
autonomous replay mode, the verifier result, deterministic authorization, bounded fanout,
DataHub write-back, and next-agent memory complete in one visible sequence.

The demo is intentionally offline and credential-free:

- no live DataHub request;
- no provider API call;
- no paid model call;
- every simulated receipt starts with `fixture://`;
- the UI states that causality, user impact, recovery, and incident resolution remain unverified.

Headless and manual variants:

```bash
# Launch without opening a browser.
make incident-demo-headless

# Require an operator to type the exact plan-bound confirmation before fanout.
make incident-demo-manual

# Validate the CLI, synthetic catalog, claim ceiling, shell syntax, and local doc targets.
make judge-check
```

The original deterministic failure-ledger workflow remains available:

```bash
make demo
make benchmark
```

## DataHub is the operating context, not decoration

LedgerLens uses DataHub on both sides of the incident:

| Stage | DataHub role | Why it matters |
|---|---|---|
| Detect and ground | Assertion/incident signal, asset URN, ownership, schema, tier, docs, lineage | The plan is tied to catalog evidence rather than guessed from alert prose |
| Bound blast radius | Downstream lineage and criticality metadata | Response scope can name affected assets while preserving uncertainty about actual user impact |
| Authorize | DataHub evidence references are required by deterministic policy | Unsupported actions fail closed |
| Record | Allowlisted DataHub MCP mutation tools can write a receipt-bearing incident snapshot | The catalog retains what was attempted, by which policy, and with which limitations |
| Continue | The next-agent handoff links known facts, unknowns, actions, and write-back references | A recovery verifier can continue without reconstructing the incident from chat history |

The fixture replay demonstrates this contract with synthetic DataHub-shaped data. A live claim
requires a published receipt that identifies the DataHub version, run mode, time, and limitations.

## Official judging criteria mapping

The six official criteria are equally weighted at **16.67% each**.

| Official criterion | LedgerLens judge evidence |
|---|---|
| Meaningful Use of DataHub Tools and Write-Back | DataHub-grounded incident context, lineage-based blast radius, official MCP read path, controlled MCP mutation adapter, and visible write-back stage |
| Technical Execution and End-to-End Functionality | Typed incident models, planner/verifier interfaces, fail-closed policy, idempotent provider adapters, write-back receipts, replay UI, tests, and one-command demo |
| Originality and Extension Beyond Built-ins | Adds evidence-bound authorization, multi-stage verification, provider fanout, receipt semantics, and next-agent handoff beyond a default catalog Q&A agent |
| Real-World Usefulness | Coordinates accountable owners and durable incident records while refusing to invent cause, impact, or recovery |
| Submission Quality and Reproducibility | Public Apache-2.0 repository, deterministic fixture, exact commands, claim boundaries, architecture, security documentation, and a timed under-three-minute script |
| Open-Source Contribution Bonus | Apache-2.0 project plus a narrowly scoped upstream DataHub MCP provenance proposal; no upstream merge is claimed until publicly evidenced |

The paste-ready Devpost copy, URL fields, evidence checklist, and 2:50 demo script are in
[docs/DEVPOST_SUBMISSION.md](docs/DEVPOST_SUBMISSION.md).

## What is evidenced today

| Surface | Safe statement | Not established |
|---|---|---|
| Incident Commander fixture | The replay UI exercises the complete visible state transition and labels every receipt as synthetic | Live provider execution or a live DataHub mutation |
| Provider action layer | All four adapters implement typed previews, authorization binding, idempotency, retries, and sanitized receipts; the published GitHub receipt records creation and immediate closure of rehearsal issue `#3` | Slack, PagerDuty, or Jira live execution; production permissions |
| DataHub write-back layer | A published local DataHub OSS v1.6.0 receipt records 577 catalog proposals, an authorized `save_document` mutation, and fresh MCP retrieval of the resulting document | Hosted/public availability or incident recovery |
| Verifier layer | A published live 020s rehearsal records one planner, two verifier variants, four bounded actions, quorum approval, and deterministic authorization with no external mutation | Provider-family independence, independent validation, or validated uplift |
| Benchmarks | The synthetic DataHub-context ON/OFF ablation records owner accuracy, blast-radius recall, unsupported claims, unsafe actions, duplicate actions, and plan completeness | Production reliability, scientific validity, or general performance uplift |

Any public screenshot or video must keep the mode label and receipt scheme visible.

## Local DataHub OSS smoke path

The repository also retains an explicit local DataHub OSS integration smoke path:

```bash
make setup
make datahub-up
make live-smoke
make datahub-down
```

This is a development/testing smoke, not the public Incident Commander provider fanout. Its result
must be described only by the generated receipt and its stated limitations. DataHub setup details
are in [docs/DATAHUB_QUICKSTART.md](docs/DATAHUB_QUICKSTART.md).

## Repository map

```text
src/ledgerlens/incident_*.py      incident models and judge dashboard
src/ledgerlens/orchestrator.py    fail-closed workflow state machine
src/ledgerlens/verification.py    verifier aggregation and deterministic policy
src/ledgerlens/actions/           GitHub, Slack, PagerDuty, and Jira adapters
src/ledgerlens/datahub_writeback.py
src/ledgerlens/mcp_mutations.py   controlled DataHub write-back
fixtures/incident_commander/      synthetic public incident catalog
benchmarks/incident_commander/    deterministic DataHub-context ablation
scripts/demo_incident_commander.sh
docs/DEVPOST_SUBMISSION.md        judge-facing submission source
```

## Submission requirements and current gaps

The repository is public, licensed under the [Apache License 2.0](LICENSE), and released as
[`v0.2.0`](https://github.com/tomyimkc/ledgerlens/releases/tag/v0.2.0) from merged commit
`00063e4`. Before final submission, the owner still must publish the hosted demo and
under-three-minute video URLs in [docs/DEVPOST_SUBMISSION.md](docs/DEVPOST_SUBMISSION.md), then
verify judge access in an incognito browser. The hosted environment must remain free through
August 31, 2026.

Deployment instructions are maintained separately in
[docs/HOSTED_DEMO.md](docs/HOSTED_DEMO.md); this packaging does not claim that deployment is live.

## Disclosure, security, and contribution

- [DISCLOSURE.md](DISCLOSURE.md) separates pre-existing Sophia-AGI source material from newly built
  LedgerLens contest work.
- [SECURITY.md](SECURITY.md) covers untrusted incident text, credentials, authorization, and
  mutation boundaries.
- [CONTRIBUTING.md](CONTRIBUTING.md) documents development and claim discipline.
- [docs/UPSTREAM_MCP_CONTRIBUTION.md](docs/UPSTREAM_MCP_CONTRIBUTION.md) contains the upstream
  contribution plan; it is a proposal, not a claimed merged contribution.

LedgerLens is a working prototype. It does not establish independent validation, production
readiness, provider-family independence, validated uplift, promotion, incident recovery, or AGI.
