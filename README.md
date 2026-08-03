# LedgerLens

## Autonomous Data Incident Commander

[![CI](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml/badge.svg)](https://github.com/tomyimkc/ledgerlens/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)

**LedgerLens turns a DataHub-observed data incident into bounded, auditable response work.**

### The problem, concretely

It is 02:14. A freshness assertion fails on the table behind the company revenue dashboard, and an
on-call data engineer gets paged for a dataset she did not build. Before she can do anything useful
she has to answer questions the catalog already knows: who owns this, what broke, what is downstream,
which of those consumers matter, is there a runbook, and did someone already respond an hour ago.
She assembles that by hand from the catalog, lineage, Slack scrollback, and memory — every time,
under time pressure.

An LLM agent can draft that response in seconds. The reason most teams will not let one touch
production is not draft quality: it is that the same model that proposes the action also decides
the action is safe to run.

This is the gap DataHub itself frames as central to agentic data work. As DataHub co-founder and
CTO Shirshanka Das put it at the April 2026 DataHub Town Hall, *"This is not an LLM problem. It is
a context problem."* ([source](https://datahub.com/blog/trusted-context-for-talk-to-data-april-2026-town-hall-highlights/))
LedgerLens takes that literally: the trusted context is DataHub's metadata graph, and the authority
to act is bound to that context, not to the model's confidence.

**LedgerLens splits those two jobs.** The model proposes and checks the response. A deterministic
policy — ordinary Python, not a prompt — decides whether it may execute, and authorizes only the
exact plan that was reviewed. Every approved action leaves a receipt, and the incident state is
written back to DataHub so the next responder starts from verified facts instead of scrollback.

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
- [Live Incident Commander](https://tomyimkc-ledgerlens-incident-commander.hf.space/)
- [Hugging Face Space](https://huggingface.co/spaces/tomyimkc/ledgerlens-incident-commander)
- [v0.2.0 public baseline](https://github.com/tomyimkc/ledgerlens/releases/tag/v0.2.0)
- [Upstream DataHub MCP issue #159](https://github.com/acryldata/mcp-server-datahub/issues/159)
- [Upstream DataHub MCP PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160)
- [Judge-ready submission package](docs/DEVPOST_SUBMISSION.md)
- [Canonical evidence index](docs/EVIDENCE_INDEX.md)
- [Non-video winner-readiness scorecard](docs/WINNER_READINESS.md)
- [Submission data ledger](docs/SUBMISSION_LEDGER.md)
- [Supervised live DataHub public proof](docs/LIVE_DATAHUB_PUBLIC.md)
- [Live provider rehearsal setup](docs/LIVE_PROVIDER_REHEARSAL.md)
- [Consent-safe external evaluation kit](docs/EXTERNAL_EVALUATION.md)
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

## Why this is not DataHub's Actions Framework, and not a generic LLM agent

DataHub already ships an **Actions Framework**: it subscribes to metadata change events and fires
pre-written automations. That is the right tool when you know in advance exactly what should happen.
It does not decide what a *novel* incident needs, and it has nothing to decide about — the response
is fixed at configuration time by a human.

A generic LLM agent has the opposite problem. It can propose a response to an unfamiliar incident,
but it also decides for itself whether that response is safe to run. Its plan can drift between the
moment a human reviews it and the moment it executes.

LedgerLens is the middle path, and the mechanism is the contribution:

| | DataHub Actions Framework | Generic LLM agent | LedgerLens |
|---|---|---|---|
| Chooses the response | Human, at config time | Model, at run time | Model proposes, at run time |
| Approves the response | Human, at config time | Model approves itself | **Deterministic policy, not the model** |
| Handles a novel incident | No — only pre-wired rules | Yes | Yes |
| Binds approval to a specific plan | N/A | No | **Yes — exact plan fingerprint** |
| Rejects ungrounded claims | N/A | Best-effort in the prompt | **Fail-closed, with reason codes** |

Concretely: the plan a verifier reviewed is hashed, and only that exact fingerprint can execute. Edit
one action parameter after review and authorization fails closed
([`src/ledgerlens/verification.py`](src/ledgerlens/verification.py),
[`tests/test_verification.py`](tests/test_verification.py)). The model never holds the authority to
approve its own work — that is enforced in deterministic Python, not requested in a prompt.

## Run the judge demo

The public deterministic replay is live at:

```text
https://tomyimkc-ledgerlens-incident-commander.hf.space/
```

It redirects directly to the Incident Commander and requires no account, payment, API key, or
provider credential.

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

# Reproduce the DataHub context ON/OFF numbers this submission reports.
make incident-benchmark
```

`make incident-benchmark` is the benchmark behind every figure in this submission. It also runs
inside `make judge-check`. Read
[the mechanism disclosure](benchmarks/incident_commander/README.md) before quoting its numbers:
both arms are scripted responders, so the ON/OFF gap demonstrates what an evidence-grounded schema
can express with and without catalog context — it does not measure planner, verifier, or model
capability.

The original deterministic failure-ledger workflow remains available:

```bash
make demo
make benchmark
```

Those two targets belong to LedgerLens's earlier failure-ledger workflow. They are **not** the
Incident Commander evidence this submission is judged on — use `make incident-demo` and
`make incident-benchmark` for that.

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

LedgerLens reaches this context through the **same Model Context Protocol (MCP) surface that
DataHub's own [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context)
wraps** — the kit of guides, SDKs, and an MCP server DataHub ships for building agents against its
graph. LedgerLens speaks that MCP protocol directly (`src/ledgerlens/mcp_client.py`) rather than
vendoring the `datahub-agent-context` SDK, and its one upstream contribution
([PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160), open, unmerged) proposes an
opt-in audit-context field for that same MCP server. The point is alignment, not adoption: this is
the agent-context path DataHub is itself investing in.

## Pointing LedgerLens at your own DataHub (prototype stage)

Everything in this repository is credential-free and synthetic by default. To read from a real
catalog instead, copy `.env.example` to `.env` and set:

| Variable | Purpose |
|---|---|
| `DATAHUB_GMS_URL` | Your DataHub GMS endpoint |
| `DATAHUB_GMS_TOKEN` | A DataHub personal access token (read-only is enough to start) |
| `DATAHUB_MCP_URL` or `DATAHUB_MCP_COMMAND` | The official DataHub MCP server, for the read path |
| `LEDGERLENS_LLM_ENABLED=true` + `SOPHIA_020S_KEY` | Enable the planner/verifier models (off by default) |

Write-back stays off until you deliberately set `LEDGERLENS_MUTATIONS_ENABLED=true`, and any action
execution additionally requires `LEDGERLENS_ACTION_AUTHORIZATION_SECRET`. Start with
[`docs/DATAHUB_QUICKSTART.md`](docs/DATAHUB_QUICKSTART.md), which stands up DataHub OSS locally so
you can try this against a real instance without touching production.

**Be clear about what is not ready.** This is prototype-stage software:

- Slack, PagerDuty, and Jira adapters are implemented and tested, but no live credential wiring or
  workspace-onboarding flow ships here — only GitHub has a recorded live execution receipt.
- Entity allowlists, action policy, and the incident-policy table are tuned for the bundled synthetic
  catalog and would need to be written for your domain model.
- There is no multi-tenancy, no RBAC integration with your DataHub roles, and no operational runbook
  for running this continuously.
- Nothing here has been validated against a production incident. Treat it as a working demonstration
  of the authority model, not an on-call tool you can adopt as-is.

## Official judging criteria mapping

The official rules list five core criteria as equally weighted and call the open-source contribution a
**bonus**. LedgerLens therefore reports a five-core average and the open-source contribution
separately; the bonus must not hide a weak core submission.

| Core criterion | LedgerLens judge evidence |
|---|---|
| Meaningful Use of DataHub Tools and Write-Back | DataHub-grounded incident context, lineage-based blast radius, official MCP read path, controlled MCP mutation adapter, and visible write-back stage |
| Technical Execution and End-to-End Functionality | Typed incident models, planner/verifier interfaces, fail-closed policy, idempotent provider adapters, write-back receipts, replay UI, tests, and one-command demo |
| Originality and Extension Beyond Built-ins | Adds evidence-bound authorization, multi-stage verification, provider fanout, receipt semantics, and next-agent handoff beyond a default catalog Q&A agent |
| Real-World Usefulness | Coordinates accountable owners and durable incident records while refusing to invent cause, impact, or recovery |
| Submission Quality and Reproducibility | Public Apache-2.0 repository, deterministic fixture, exact commands, claim boundaries, architecture, security documentation, and a clear evidence index |

| Separate bonus | LedgerLens evidence |
|---|---|
| Open-Source Contribution Bonus | A narrowly scoped upstream DataHub MCP provenance proposal; [PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160) is open and unmerged, and no acceptance is claimed |

Use the [evidence index](docs/EVIDENCE_INDEX.md) for direct artifact navigation and the
[non-video scorecard](docs/WINNER_READINESS.md) for candid rubric gaps. The paste-ready Devpost
copy and owner checklist are in [docs/DEVPOST_SUBMISSION.md](docs/DEVPOST_SUBMISSION.md).

## What is evidenced today

| Surface | Safe statement | Not established |
|---|---|---|
| Hosted Incident Commander fixture | The stable public Hugging Face replay exposes `/healthz`, runs the complete visible state transition, returns exactly four `fixture://` provider receipts, records fixture write-back, prepares next-agent memory, and reports deterministic authority with `ai_can_authorize: false` | Live provider execution or a live DataHub mutation from the hosted replay |
| Temporary public DataHub reachability | A supervised authenticated proof exposed DataHub OSS v1.6.0 through a temporary TLS tunnel; unauthenticated access returned 401, judge login returned 200, Reader grants were verified without metadata-mutation authority, and teardown completed with the former URL returning 503 | A durable public DataHub judge URL, production security, or ongoing availability |
| Provider action layer | All four adapters implement typed previews, authorization binding, idempotency, retries, and sanitized receipts; the published GitHub receipt records creation and immediate closure of rehearsal issue `#3` | Slack, PagerDuty, or Jira live execution; production permissions |
| DataHub write-back layer | A published local DataHub OSS v1.6.0 receipt records an authorized `save_document` mutation and fresh official-MCP retrieval of the resulting document | Incident causality, user impact, recovery, or production readiness |
| Verifier layer | A published live 020s rehearsal records one planner, two verifier variants, four bounded actions, quorum approval, and deterministic authorization with no external mutation | Provider-family independence, independent validation, or validated uplift |
| Benchmarks | The synthetic DataHub-context ON/OFF ablation records owner accuracy, blast-radius recall, unsupported claims, unsafe actions, duplicate actions, and plan completeness | Production reliability, scientific validity, or general performance uplift. **Both arms are scripted responders, not the LedgerLens pipeline:** context-ON copies the fixture's pre-labeled ground-truth actions, and context-OFF is a fixed generic script that adds an unsafe action in about half of scenarios by a stable hash of the scenario ID. The gap shows what an evidence-grounded schema can express with and without catalog context; it does not measure planner, verifier, or system capability. See the [mechanism disclosure](benchmarks/incident_commander/README.md). |
| External evaluation | The repository provides a consent-safe 7–10 minute scorecard and aggregation tool, and public recruitment is open | Any reviewer result, endorsement, external validation, or official judging score |

Evidence details:

- [`benchmarks/results/live-public-proof-2026-07-31.json`](benchmarks/results/live-public-proof-2026-07-31.json)
- [`docs/LIVE_DATAHUB_PUBLIC.md`](docs/LIVE_DATAHUB_PUBLIC.md)
- [`docs/EXTERNAL_EVALUATION.md`](docs/EXTERNAL_EVALUATION.md)

The temporary DataHub public proof has been torn down. The Hugging Face fixture replay is the only
stable public application URL. Any public screenshot or video must keep the mode label and receipt
scheme visible.

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
scripts/check_hosted_incident_demo.py
scripts/check_non_video_readiness.py
docs/DEVPOST_SUBMISSION.md        judge-facing submission source
```

## Submission requirements and current gaps

The repository is public, licensed under the [Apache License 2.0](LICENSE), and released as
[`v0.2.0`](https://github.com/tomyimkc/ledgerlens/releases/tag/v0.2.0) from merged commit
`00063e4`. The hosted replay is deployed, a supervised authenticated DataHub reachability proof
has been completed and torn down, and the repository contains live GitHub, live DataHub
write-back, AI-verification, benchmark, provenance, and external-evaluation evidence packages.

The final `v0.2.1` tag is intentionally **pending the public video URL** and must not be described
as published yet. Run the fail-closed non-video gate with:

```bash
make non-video-readiness
```

Before final submission, the owner must publish the under-three-minute video URL, cut `v0.2.1`
from the final merged commit, review the Devpost account/team details, click final Submit, and save
the submission receipt. The Space must remain free and reachable through August 31, 2026.

Deployment instructions are maintained separately in
[docs/HOSTED_DEMO.md](docs/HOSTED_DEMO.md). That document distinguishes the stable fixture replay
from the completed temporary DataHub proof and does not claim a durable public DataHub deployment.

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
