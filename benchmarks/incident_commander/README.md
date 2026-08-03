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
