# Supersession trace

Reset command:

```bash
bash deploy/bin/reset-scenario.sh supersession
```

Judge path:

1. Open the earlier parser finding.
2. Follow its supersession chain to the current fixture-suite finding.
3. Compare the DataHub lineage edge with the explicit LedgerLens supersession property.
4. Confirm the UI states that supersession preserves history and does not validate either record.

Expected boundary: the lineage edge is a documented LedgerLens convention, not an ordinary data
transformation.
