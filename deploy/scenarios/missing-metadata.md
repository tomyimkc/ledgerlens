# Missing metadata investigation

Reset command:

```bash
bash deploy/bin/reset-scenario.sh missing-metadata
```

Judge path:

1. Open the remediation queue.
2. Filter visually for findings missing an owner or evidence reference.
3. Open a finding and compare the source assertion, DataHub metadata, and explicit unknowns.
4. Confirm LedgerLens does not invent missing fields.

Expected boundary: evidence references are pointers supplied by the source, not independent
verification.
