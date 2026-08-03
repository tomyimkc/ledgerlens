# LedgerLens Devpost Submission Source

## Submission identity

- **Project:** LedgerLens — Autonomous Data Incident Commander
- **Tagline:** Turn DataHub context into authorized incident work—with receipts.
- **Category:** Agents That Do Real Work
- **Repository:** `https://github.com/tomyimkc/ledgerlens`
- **License:** Apache-2.0
- **Deadline:** August 10, 2026 at 5:00 PM EDT
- **Judge-access requirement:** free access through August 31, 2026
- **Public project URL:** `https://tomyimkc-ledgerlens-incident-commander.hf.space/`
- **Space page:** `https://huggingface.co/spaces/tomyimkc/ledgerlens-incident-commander`
- **Public video URL:** `OWNER INPUT REQUIRED`
- **Current public baseline:** `v0.2.0` at merged commit
  `00063e40bfc785f13e6db938e0795928e4f843ba`
- **Final release target:** `v0.2.1` — **pending public video URL; not yet published**
- **Final release commit:** not assigned; do not invent a SHA before the final tag is cut
- **Upstream issue:** `https://github.com/acryldata/mcp-server-datahub/issues/159`
- **Upstream PR:** `https://github.com/acryldata/mcp-server-datahub/pull/160` —
  **PR #160 remains open, not merged**

## One-line pitch

LedgerLens turns a DataHub-observed incident into a bounded response plan, AI advisory
verification, deterministic authorization, receipted operational actions, DataHub write-back, and
a provenance-preserving handoff to the next recovery agent.

## Submission description

Data incidents rarely fail because teams lack another chatbot. They fail because responders must
reconstruct ownership, lineage, runbooks, criticality, evidence, and previous actions across
separate systems while an alert clock is running.

LedgerLens is an **Autonomous Data Incident Commander** built around DataHub. It runs one visible
workflow:

```text
trigger
  -> DataHub context
  -> bounded plan
  -> AI advisory verification
  -> deterministic authorization
  -> receipted actions
  -> DataHub write-back
  -> next-agent handoff
```

The trigger identifies a DataHub asset. LedgerLens retrieves the recorded owner, tier, schema,
documentation, quality signal, and bounded downstream lineage while preserving explicit unknowns.
A planner proposes only allowlisted, reversible collaboration work. Two configured verifier
variants inspect the exact plan, evidence fact IDs, action scope, and claim boundaries.

The model outputs are advisory. A deterministic policy—not model prose—checks quorum,
confidence, action type, target, parameters, risk, evidence references, and plan fingerprint. AI
cannot authorize itself or expand an allowlist.

After authorization, typed adapters can create a GitHub issue, send a Slack message, create or
annotate a PagerDuty incident, and create a Jira task. Every adapter uses preview/execute
separation, authorization binding, idempotency, bounded retries, conservative timeout handling,
and sanitized receipts. A separate disabled-by-default DataHub mutation path records the bounded
incident command receipt. The next-agent handoff preserves known facts, unknowns, completed work,
receipt references, and required recovery checks.

The stable public project URL is a deterministic, credential-free fixture replay. It labels every
simulated receipt `fixture://`, reports `externalMutations: false`, and never presents fixture work
as live provider execution.

Separate evidence receipts establish narrower live facts:

- a live 020s planner plus two verifier variants produced a quorum-approved plan that was
  authorized by deterministic policy without external mutation;
- the signed GitHub adapter created and immediately closed rehearsal issue `#3`;
- DataHub OSS v1.6.0 accepted an authorized `save_document` write-back and the official MCP
  `get_entities` path retrieved the resulting document;
- a supervised authenticated public DataHub reachability proof returned 401 without gateway
  credentials, 200 for judge access, verified Reader-only grants without metadata-mutation
  authority, and completed teardown;
- a deterministic DataHub-context ON/OFF benchmark measures owner accuracy, blast-radius recall,
  unsupported claims, unsafe actions, duplicate actions, and plan completeness;
- a consent-safe external evaluation kit is available, but no reviewer score or endorsement is
  claimed.

LedgerLens is a working prototype. It does **not** claim provider-family independence, live Slack,
PagerDuty, or Jira execution, incident causality, user impact, recovery, production readiness,
independent validation, validated uplift, or AGI.

```yaml
candidateOnly: true
canClaimAGI: false
externalValidation: false
```

## Five equally weighted core criteria, plus a separate bonus

The official rules describe the listed criteria as equally weighted and label the open-source
contribution a **bonus**. LedgerLens presents the five core criteria first and treats the upstream
contribution separately, so the bonus cannot obscure a weakness in judge access or reproducibility.

| Core criterion | LedgerLens judge evidence |
|---|---|
| Meaningful Use of DataHub Tools and Write-Back | DataHub-grounded incident context, ownership, schema, documentation, quality signal, lineage-based blast radius, official MCP reads, controlled `save_document` write-back, and next-agent retrieval |
| Technical Execution and End-to-End Functionality | Typed state machine, planner/verifier contracts, fail-closed policy, signed provider authorization, idempotency, replay UI, strict mypy, deterministic tests, secret scan, hosted smoke, and readiness gates |
| Originality and Extension Beyond Built-ins | Evidence-bound authorization and receipted operational fanout rather than catalog Q&A or unrestricted model tool use |
| Real-World Usefulness | Coordinates accountable response work and durable handoff while refusing to invent cause, impact, recovery, or resolution |
| Submission Quality and Reproducibility | Public Apache-2.0 repository, one-command replay, public Space, exact receipts, context ablation, architecture/security docs, and fail-closed automation |

| Separate bonus | LedgerLens judge evidence |
|---|---|
| Open-Source Contribution Bonus | Upstream DataHub MCP provenance/audit-context issue #159 and PR #160 with focused tests; the PR remains open and no upstream merge is claimed |

## Evidence links

Start with the [canonical evidence index](EVIDENCE_INDEX.md). It separates the public fixture,
local-live receipts, temporary public proof, and test evidence so a judge does not need to infer
scope from a filename.

- Public Incident Commander:
  `https://tomyimkc-ledgerlens-incident-commander.hf.space/`
- Hosted replay source: `deploy/hf-space/`
- Hosted smoke checker: `scripts/check_hosted_incident_demo.py`
- AI verification:
  `benchmarks/incident_commander/ai-verification-receipt.json`
- Live GitHub action:
  `benchmarks/incident_commander/github-live-action-receipt.json`
- Live DataHub write-back:
  `benchmarks/incident_commander/datahub-live-writeback-receipt.json`
- DataHub context ON/OFF:
  `benchmarks/incident_commander/context-ablation-receipt.json`
- Local live DataHub smoke:
  `benchmarks/results/live-datahub-smoke-2026-07-31.json`
- Supervised public DataHub proof:
  `benchmarks/results/live-public-proof-2026-07-31.json`
- Public-proof design and teardown:
  `docs/LIVE_DATAHUB_PUBLIC.md`
- Consent-safe external evaluation:
  `docs/EXTERNAL_EVALUATION.md`
- Architecture and security: `ARCHITECTURE.md`, `SECURITY.md`
- Pre-existing-work disclosure: `DISCLOSURE.md`
- Candid non-video rubric scorecard and gap matrix: `docs/WINNER_READINESS.md`

## Public deployment and live-proof status

The public demo runs on a Hugging Face Space slot the author already owned. It was renamed to
`tomyimkc/ledgerlens-incident-commander` with explicit authorization and redeployed as the
LedgerLens Docker fixture replay on `cpu-basic`; the slot's previous unrelated contents were
preserved rather than destroyed. Only the hosting slot is pre-existing — the deployed application
is built from this repository. This reuse is disclosed in
[`DISCLOSURE.md`](../DISCLOSURE.md#pre-existing-material).

The public replay currently exposes a secret-free contract:

- `/` redirects to `/incident`;
- `/healthz` reports fixture mode, no external mutations, `candidateOnly: true`, and
  `canClaimAGI: false`;
- replay produces exactly four `fixture://` provider receipts;
- write-back reaches `recorded`;
- next-agent memory reaches `ready`;
- authorization reports `authority: deterministic-policy` and `ai_can_authorize: false`.

The repository includes a daily and manually dispatchable hosted smoke workflow. It requires no
repository secret and uploads only a sanitized JSON receipt.

The supervised public DataHub proof was temporary by design. The tunnel, gateway, relay, and
remote stack were stopped; volumes and private receipts were preserved. There is no durable public
DataHub judge URL, and the temporary proof must not be described as a production deployment.

## Non-video readiness status

The non-video release guard is:

```bash
make non-video-readiness
```

It fails closed when required receipts or claim flags drift, CI loses strict mypy or DataHub
dependencies, the hosted smoke contract disappears, the old failure-ledger product copy returns,
or documentation falsely claims that `v0.2.1` is already published.

A historical July 31, 2026 non-video judge-gate receipt recorded **254 deterministic tests**, strict
mypy over 36 source files, Ruff lint/format checks, the secret scan, public-package checks, the
DataHub-context benchmark, and the readiness guard. It applies only to that recorded revision.
Re-run the gates after any final release-only edit rather than copying its count. The hosted public
smoke also passed against the live fixture URL.

## Final owner/video boundary

- [ ] Add the public under-three-minute video URL.
- [x] Add and verify the public project URL.
- [x] Keep the hosted replay explicitly labeled fixture/replay.
- [x] Publish the supervised live-public DataHub proof and teardown receipt.
- [x] Publish the external evaluation kit without inventing results.
- [x] Describe Slack, PagerDuty, and Jira as implemented but not executed live.
- [x] Open upstream issue #159 and PR #160; state that PR #160 remains open, not merged.
- [ ] Publish final `v0.2.1` only after the public video URL is recorded.
- [ ] Record the real final release SHA after the tag is cut.
- [ ] Complete owner account/team/eligibility review.
- [ ] Click final Submit and save the submission receipt.
