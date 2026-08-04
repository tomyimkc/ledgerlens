# LedgerLens examples — read the output without running anything

This folder exists so a judge can **see what LedgerLens actually produces** without
cloning or running it. Every value below is copied from a real, checked-in artifact; each
example links to the full artifact and to the [evidence index](../docs/EVIDENCE_INDEX.md)
row that scopes what it does and does not prove.

LedgerLens is an **Autonomous Data Incident Commander**: a DataHub-observed incident is
grounded in catalog context, an AI planner proposes a bounded response, two independent
verifiers review it, and a **deterministic policy gate — not the model — authorizes only
the exact reviewed plan**. Approved actions leave receipts, and the incident state is
written back to DataHub for the next responder.

---

## 1. One incident, end to end (real OpenAI GPT-5.6 rehearsal)

Source: [`benchmarks/incident_commander/ai-verification-receipt.json`](../benchmarks/incident_commander/ai-verification-receipt.json)
· evidence [E-08](../docs/EVIDENCE_INDEX.md)

**Incident** `inc-analytics-downstream_availability-01` — *"Product Analytics: Critical data
product unavailable"*, grounded in the synthetic DataHub-shaped catalog.

**Planner** — OpenAI GPT-5.6, served through an OpenAI GPT-5.6 API key (receipt model id
`gpt-5.6-sol`) — proposed a four-action bounded response:

| # | Action type | What it does |
|---|---|---|
| 1 | `github.issue.create` | Open a bounded incident record |
| 2 | `slack.message.post` | Post a status note to the incident channel |
| 3 | `pagerduty.event.trigger` | Page the on-call responder |
| 4 | `jira.issue.create` | Open a recovery-validation task |

**Two verifiers** — OpenAI GPT-5.6 and GPT-5.5 (receipt model ids `gpt-5.6-terra`,
`gpt-5.5`) — reviewed the plan and both approved. Because all three roles run on the same
OpenAI model family, this does **not** establish provider-family independence, and the
receipt says so.

**The deterministic gate** then authorized the exact reviewed plan:

```json
"authorization": {
  "authorized": true,
  "policy_version": "incident-commander/v2",
  "reason_codes": ["authorized"]
}
```

No model authorized itself: the gate is plain Python (`src/ledgerlens/verification.py`) and
runs after the model output is frozen. This rehearsal performed **no external mutation** —
`externalMutations: false`, `candidateOnly: true`, `canClaimAGI: false`.

---

## 2. What the gate does when context is missing (real pipeline, both arms)

Source: [`benchmarks/incident_commander/real-pipeline-ablation-receipt.json`](../benchmarks/incident_commander/real-pipeline-ablation-receipt.json)
· evidence [E-15](../docs/EVIDENCE_INDEX.md)

The same production `VerifierPanel` and `PolicyGate` run over all 24 scenarios twice — once
with full DataHub context, once with only the alert envelope. The **only** difference is
the context supplied.

| Metric | DataHub context ON | DataHub context OFF |
|---|---:|---:|
| Plan authorization rate | **100%** | **0%** |
| Action grounding rate | 100% | 50% |
| Verifier approval rate | 100% | 0% |

Every OFF refusal carries the gate's **own** reason-code taxonomy — not a hand-written
label:

```json
"blockReasonDistribution": {
  "action_references_unknown_fact": 72,
  "verification_not_approved": 24,
  "verifier_quorum_not_met": 24,
  "verifier_reported_unverifiable_items": 24
}
```

Read the honesty note in the receipt and in
[`benchmarks/incident_commander/README.md`](../benchmarks/incident_commander/README.md):
the planner is a fixed, non-fabricating stub, so the OFF arm fails to ground actions *by
construction*. This proves the **fail-closed gate** works; it is **not** a claim that
context makes the system smarter.

---

## 3. One real provider execution (GitHub)

Source: [`benchmarks/incident_commander/github-live-action-receipt.json`](../benchmarks/incident_commander/github-live-action-receipt.json)
· evidence [E-06](../docs/EVIDENCE_INDEX.md)

A signed GitHub adapter created and then immediately closed a real, clearly-labeled
rehearsal issue (`executedAt 2026-07-31T08:13:22Z`, `closedAt 2026-07-31T08:13:24Z`). Its
body states plainly: *"No production incident is asserted. No root cause, user impact, or
recovery is claimed."* This proves the adapter path executes against a real provider — and
nothing more. Slack, PagerDuty, and Jira do not yet have live receipts.

---

## 4. One real DataHub write-back

Source: [`benchmarks/incident_commander/datahub-live-writeback-receipt.json`](../benchmarks/incident_commander/datahub-live-writeback-receipt.json)
· evidence [E-07](../docs/EVIDENCE_INDEX.md)

An authorized `save_document` mutation persisted an incident snapshot to a local DataHub
OSS v1.6.0 instance, followed by a fresh official-MCP read-back of the written document.
Local OSS evidence — it does not prove recovery, causality, or a hosted public deployment.

---

## Reproduce any of these

```bash
make setup
make incident-benchmark-real-pipeline   # regenerates the §2 receipt deterministically
make ai-rehearsal                       # regenerates the §1 receipt (needs an OpenAI GPT-5.6 API key)
make judge-check                        # the full evidence gate
```

The public fixture replay — no credentials — is at
<https://tomyimkc-ledgerlens-incident-commander.hf.space/>.
