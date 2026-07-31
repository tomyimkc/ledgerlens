# LedgerLens Devpost Submission Source

## Submission identity

- **Project:** LedgerLens — Autonomous Data Incident Commander
- **Category:** Agents That Do Real Work
- **Repository:** `https://github.com/tomyimkc/ledgerlens`
- **License:** Apache-2.0
- **Deadline:** August 10, 2026 at 5:00 PM EDT
- **Judge-access requirement:** free access through August 31, 2026
- **Public demo URL:** `OWNER INPUT REQUIRED`
- **Public video URL:** `OWNER INPUT REQUIRED`
- **Final release/tag:** `OWNER INPUT REQUIRED`

## One-line pitch

LedgerLens turns a DataHub-observed incident into an evidence-grounded plan, independent
model-variant verification, deterministic authorization, receipted operational actions, DataHub
write-back, and a provenance-preserving handoff to the next recovery agent.

## Submission description

Data incidents rarely fail because teams lack another chatbot. They fail because responders must
reconstruct ownership, lineage, runbooks, criticality, evidence, and previous actions across
separate systems while an alert clock is running.

LedgerLens is an **Autonomous Data Incident Commander** built around DataHub. It starts from a
DataHub assertion or incident signal, retrieves the root asset and bounded downstream lineage,
preserves explicit unknowns, and asks a planner for a reversible response plan. Two distinct
configured verifier variants review the exact plan. A deterministic policy gate—not model prose—
checks quorum, confidence, evidence fact IDs, action types, targets, parameters, risk, and the plan
fingerprint.

Only then can LedgerLens fan out typed, HMAC-authorized actions to GitHub, Slack, PagerDuty, and
Jira. Each adapter uses preview/execute separation, idempotency, bounded retries, conservative
ambiguous-timeout handling, and secret-safe receipts. A separate disabled-by-default mutation path
records the bounded incident snapshot and receipts back into DataHub, where the next recovery
verifier can inherit known facts, unknowns, completed work, provenance, and required next checks.

The public replay is deterministic and credential-free. It labels every synthetic receipt
`fixture://` and does not claim live provider execution. Separate receipts record the live 020s
planner-plus-two-verifier rehearsal, the real GitHub issue creation/closure evidence, 577 accepted
DataHub catalog proposals, a controlled `save_document` write-back, and fresh MCP retrieval of the
created document.

LedgerLens does **not** claim provider-family independence, incident causality, user impact,
recovery, validated uplift, production readiness, or AGI.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Six equally weighted judging criteria

| Criterion | Judge evidence |
|---|---|
| Meaningful DataHub use and write-back | Root entity, ownership, schema-shaped properties, runbook, SLO, quality checks, downstream lineage, controlled MCP write-back, and next-agent retrieval contract |
| Technical execution and end-to-end functionality | Typed state machine, real planner/verifier JSON contracts, deterministic gate, action adapters, receipts, idempotency, dashboard, tests, and deployment package |
| Originality beyond built-ins | Evidence-bound authorization and operational fanout rather than catalog Q&A alone |
| Real-world usefulness | Coordinates accountable response work while preserving unknown cause, impact, and recovery |
| Submission quality and reproducibility | Apache-2.0 repo, one-command replay, 120-asset fixture, 24 scenarios, DataHub-context ablation, exact scripts, and claim boundaries |
| Open-source contribution bonus | Upstream MCP `get_entities` aspect audit-context patch and tests are prepared; no merge is claimed until the public PR is accepted |

## Evidence links to include

- Incident Commander screenshot/video
- `benchmarks/incident_commander/ai-verification-receipt.json`
- `benchmarks/incident_commander/github-live-action-receipt.json`
- deterministic DataHub context ON/OFF receipt
- public hosted demo health receipt
- upstream MCP issue and PR
- final Git commit and release

## Under-three-minute video script (target 2:50)

### 0:00–0:18 — Problem

> A critical data alert gives responders a symptom, not the owner, blast radius, safe action scope,
> or a durable handoff. LedgerLens turns DataHub context into bounded incident work.

Show the Incident Commander hero, visible `FIXTURE / REPLAY` banner, and `candidateOnly` boundary.

### 0:18–0:48 — DataHub context

Click **Replay trigger**. Show root entity, owner, tier, runbook/evidence pointers, downstream
assets, and the statement that lineage is metadata-derived and not causal proof.

### 0:48–1:15 — Plan

Show the plan fingerprint and four provider actions plus DataHub write-back. Emphasize that no
production rollback or incident resolution is proposed.

### 1:15–1:43 — Verify and authorize

Show the verifier panel and deterministic gate. Say:

> Model variants are advisory. They cannot expand allowlists or authorize themselves. The exact
> plan, targets, parameters, risk, evidence IDs, quorum, and confidence must pass deterministic
> policy.

### 1:43–2:12 — Do work and preserve receipts

Show GitHub, Slack, PagerDuty, and Jira receipt cards, followed by DataHub write-back. Keep
`fixture://` visible in the replay. Cut briefly to the separately published closed GitHub issue
receipt and the live AI-verification receipt; do not imply the other providers were live.

### 2:12–2:34 — Next-agent memory

Show known facts, unknowns, completed actions, provenance, and next recovery checks.

### 2:34–2:50 — Why it wins

> DataHub is the incident operating context and the durable memory layer. LedgerLens adds
> verifier-gated, policy-bound action fanout with receipts—real work without turning model
> confidence into arbitrary authority.

End on the repository, Apache-2.0 badge, public demo URL, and exact claim boundary.

## Owner-only final checklist

- [ ] Add public project and video URLs.
- [ ] Keep the hosted demo free and reachable through August 31, 2026.
- [ ] Verify judge access in a clean/incognito browser.
- [ ] Confirm video duration is below three minutes.
- [ ] Publish final release/tag and commit SHA.
- [ ] Open the upstream MCP issue and PR; link them only after they are public.
- [ ] Confirm Slack, PagerDuty, and Jira are described as implemented adapters unless live receipts
      are obtained.
- [ ] Run `make judge-check`.
