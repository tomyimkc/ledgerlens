# Result Templates

These files are templates, not completed benchmark receipts.

- `deterministic-fixture-template.json` — offline fixture/unit benchmark
- `live-datahub-smoke-template.json` — explicit live DataHub integration smoke

Both start with `status: "NOT_RUN"`. Copy a template to ignored `artifacts/benchmarks/` and use the
benchmark runner to create a real receipt.

Do not edit a template to claim a run occurred.

```yaml
candidateOnly: true
canClaimAGI: false
```
