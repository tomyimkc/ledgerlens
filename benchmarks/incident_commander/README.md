# Incident Commander context-ablation benchmark

This benchmark is self-contained and offline. It evaluates two deterministic
incident-command paths against the same synthetic, DataHub-shaped catalog:

- **DataHub context ON** reads catalog ownership, schema, documentation, lineage,
  incident policy, dashboards, and model metadata.
- **DataHub context OFF** receives only the alert envelope (incident ID, domain,
  severity, signal, and root URN) and uses a deliberately generic fallback.

The benchmark does not import LedgerLens application modules, contact DataHub,
or use an LLM judge. Its local schema and validators fail closed on dangling
lineage, cycles, missing owners or documentation, mismatched ground truth,
unsafe claim flags, or out-of-range corpus sizes.

## What this benchmark does and does not measure — read before quoting numbers

Both arms are **hand-written scripted responders**, not the LedgerLens
planner/verifier/policy pipeline. Read the mechanism before citing any figure:

- **Context ON is a ground-truth oracle.** Its action plan is
  `deepcopy(incident["safeActions"])` (`benchmark.py:140`) — it copies the
  scenario's pre-labeled correct answer verbatim, and builds its claims directly
  from the fixture's known-good context. It does not reason, plan, or verify.
- **Context OFF is a fixed generic script.** It emits the same five actions for
  every incident, guesses the owner from a per-domain default table, and returns
  an empty blast radius. In roughly half of scenarios — selected by a stable hash
  of the scenario ID, not by any model behaviour — it also appends an `UNSAFE`
  `disable_auditing` action (`benchmark.py:~199`).

Consequently the ON/OFF gap measures **how much an evidence-grounded response
schema can express when DataHub context is present versus absent**. It is a
contract- and schema-shape demonstration on synthetic fixtures.

It is **not** a measurement of model uplift, planner quality, verifier quality,
LedgerLens end-to-end capability, or any production outcome. The separation
between the arms is fixed by construction, so the size of the gap is a property
of the fixture design and carries no statistical claim about the running system.
For evidence about the actual pipeline, see the deterministic tests
(`make test`) and the live DataHub write-back receipt in `docs/EVIDENCE_INDEX.md`.

## Metrics

| Metric | Definition |
|---|---|
| Owner accuracy | Jaccard accuracy of predicted and expected accountable-owner sets |
| Blast-radius recall | Expected downstream assets recovered from full transitive lineage |
| Unsupported-claim rate | Claims with a wrong value, no evidence, or no matching evidence reference |
| Unsafe-action rate | Proposed actions whose type is explicitly forbidden for the incident |
| Duplicate-action rate | Repeated normalized `(actionType, targetUrn)` actions |
| Action-plan completeness | Required incident-policy action types present in the plan |
| Latency | Local wall-clock response construction, after warmup, with repeated samples |

Means and paired ON-minus-OFF differences include deterministic percentile
bootstrap 95% confidence intervals. Latency is diagnostic local timing, not a
production performance claim.

```yaml
candidateOnly: true
canClaimAGI: false
```

Build the checked-in fixture:

```bash
python scripts/build_incident_catalog.py
```

Run the benchmark:

```bash
python scripts/run_incident_commander_benchmark.py \
  --output artifacts/benchmarks/incident-commander.json
```

`PASS` means the catalog and scorer contracts executed and the declared
context-ON safety/correctness gates passed on this synthetic fixture. It does
not establish live DataHub compatibility, production readiness, autonomous
remediation safety, model uplift, independent validation, or AGI.

## Companion: the real-pipeline ablation

The benchmark above is a **schema/contract demonstration** with scripted
responders. A companion benchmark,
[`real_pipeline_ablation.py`](real_pipeline_ablation.py), asks the same ON/OFF
question of the **actual production pipeline**: it runs one deterministic
planner through the real
[`VerifierPanel`](../../src/ledgerlens/verification.py) and the real
[`PolicyGate`](../../src/ledgerlens/verification.py) built by the same
`runtime_factory.build_policy_gate` the application uses.

```bash
make incident-benchmark-real-pipeline
# -> benchmarks/incident_commander/real-pipeline-ablation-receipt.json
```

The **only** difference between its two arms is the `IncidentContext` supplied.
Context ON carries the DataHub-shaped facts a catalog read resolves
(`root-asset`, `primary-owner`, `blast-radius`, `runbook`); context OFF carries
only a single self-reported `root-asset` fact. The planner proposes the same
six-step response in both arms; the real gate then authorizes only the actions
whose evidence is grounded in the supplied context.

Result on the checked-in fixture (24 scenarios): the real gate authorizes
**100%** of the ON scenarios and **0%** of the OFF scenarios. The OFF refusals
carry the gate's own reason-code taxonomy — `action_references_unknown_fact`,
`verification_not_approved`, `verifier_quorum_not_met` — not a hand-written
label.

**Read this before quoting the numbers.** Because the planner is a fixed,
non-fabricating stub, the OFF arm fails to ground its owner/blast-radius/runbook
actions *by construction*. This proves the fail-closed gate behaves correctly on
a controlled input — it does **not** show that context makes the system smarter,
and it says nothing about the real LLM-backed planner/verifier, which this
benchmark deliberately does not exercise. `ownerAccuracy` and
`blastRadiusRecall` measure what the context contained, not planner skill.
