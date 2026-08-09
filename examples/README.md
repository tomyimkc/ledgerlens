# LedgerLens examples — read the output without running anything

This folder exists so a judge can **see what LedgerLens actually produces** without
cloning or running it. Every value below is copied from a real, checked-in artifact; each
example links to the full artifact and to the [evidence index](../docs/EVIDENCE_INDEX.md)
row that scopes what it does and does not prove.

LedgerLens is a **Policy-Sealed Data Incident Commander**: a DataHub-observed incident is
grounded in catalog context, an AI planner proposes a bounded response, two distinct model
variants review it, and a **deterministic policy gate — not the model — authorizes only
the exact reviewed plan**. Distinct model IDs are not presented as provider-family
independence. Approved actions leave receipts, and the incident state can be written back
to DataHub for the next responder.

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

## 2. Same recorded model plan, DataHub facts cut one at a time

Source: [`benchmarks/incident_commander/context-cut-agent-trace.json`](../benchmarks/incident_commander/context-cut-agent-trace.json)
· evidence [E-20](../docs/EVIDENCE_INDEX.md)

The recorded four-tool model plan is held fixed. The planner and verifiers are not called
again. The current `PolicyGate` evaluates that exact typed plan against four synthetic
context variants:

| Context | Policy result | What changed |
|---|---|---|
| Full DataHub map | **AUTHORIZED** | owner, lineage, asset, severity, and runbook facts present |
| Ownership removed | **DENIED** | per-tool owner evidence contracts cannot be satisfied |
| Lineage removed | **DENIED** | blast-radius evidence required by notification/page tools is absent |
| Alert only | **DENIED** | only incident ID and severity remain |

This is a controlled authorization ablation: it proves DataHub facts are load-bearing for
the implemented policy, not that the model would re-plan well under missing context.
The public Space replays these decisions server-side and executes no tools.

---

## 3. What the gate does when context is missing (real pipeline, both arms)

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

## 4. One linked four-provider rehearsal

Source: [`benchmarks/incident_commander/live-incident-rehearsal-receipt.json`](../benchmarks/incident_commander/live-incident-rehearsal-receipt.json)
· evidence [E-16](../docs/EVIDENCE_INDEX.md)

On August 3, 2026, one supervised run executed one clearly labeled rehearsal action
against each configured provider: GitHub issue `#29`, one Slack message, one PagerDuty
event, and Jira issue `KAN-2`.

This is one bounded action per provider. It does not establish sustained operation,
production permissions, provider-family independence, incident causality, or recovery.

For the earlier GitHub-only creation/closure receipt, see
[`github-live-action-receipt.json`](../benchmarks/incident_commander/github-live-action-receipt.json)
and evidence E-06.

---

## 5. One real DataHub write-back

Source: [`benchmarks/incident_commander/datahub-live-writeback-receipt.json`](../benchmarks/incident_commander/datahub-live-writeback-receipt.json)
· evidence [E-07](../docs/EVIDENCE_INDEX.md)

An authorized `save_document` mutation persisted an incident snapshot to a local DataHub
OSS v1.6.0 instance, followed by a fresh official-MCP read-back of the written document.
Local OSS evidence — it does not prove recovery, causality, or a hosted public deployment.

---

## Reproduce any of these

```bash
make setup
make context-cut-trace                  # rebuilds §2 without network or credentials
make incident-benchmark-real-pipeline   # regenerates the §3 receipt deterministically
make ai-rehearsal                       # regenerates the §1 receipt (needs an OpenAI GPT-5.6 API key)
make judge-check                        # the full evidence gate
```

The public fixture replay — no credentials — is at
<https://tomyimkc-ledgerlens-incident-commander.hf.space/>.
