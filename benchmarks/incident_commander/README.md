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
