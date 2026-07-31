# Synthetic incident catalog

`catalog.json` is a deterministic, public, synthetic DataHub-shaped graph. It
contains 120 assets across analytics, customer, finance, and ML, plus team
ownership, schemas, documentation, lineage, dashboards, models, data products,
24 incidents, and 24 benchmark scenarios.

All people, systems, addresses, URLs, and incidents are fictional. URLs use the
reserved `.invalid` domain. Rebuild the fixture with:

```bash
python scripts/build_incident_catalog.py --seed 20260731
```

The builder validates the complete graph before atomically replacing the file.
The fixture is candidate-only and cannot support an AGI claim.
