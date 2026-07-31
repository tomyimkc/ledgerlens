# Baseline remediation queue

Reset command:

```bash
bash deploy/bin/reset-scenario.sh baseline
```

Judge path:

1. Open LedgerLens and confirm the live DataHub/MCP status.
2. Inspect the queue grouped by priority and owner.
3. Download the JSON or Markdown triage artifact.
4. Confirm every item retains `candidateOnly: true` and `canClaimAGI: false`.

Expected boundary: this scenario demonstrates live metadata retrieval and deterministic
prioritization. It does not validate the underlying findings.
