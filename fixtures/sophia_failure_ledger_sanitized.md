# Sanitized Failure Ledger Fixture

This public fixture is synthetic. It preserves the structural edge cases of a
Sophia-style failure ledger without copying private data or claiming that any
finding has been independently validated.

| ID | Status | Claim impact | Required response | Kind |
|---|---|---|---|---|
| cache-receipt-missing-2026-07-20 | OPEN (createdAt=2026-07-20T09:30:00Z) | A cache refresh lacks a durable receipt. Evidence: https://example.org/evidence/cache-refresh.json; | Owner: platform-team; attach a receipt before closing. | instrument |
| schema-check-resolved-2026-07-21 | RESOLVED 2026-07-21 (updatedAt=2026-07-21T14:05:00Z) | The schema check rejected an invalid fixture as intended. | Owner: data-quality; retain Evidence: fixtures/evidence/schema-check.json; | methodology |
| stale-cache-rule-2026-07-18 | SUPERSEDED by cache-rule-v2-2026-07-22 | The original cache rule omitted an expiry field. | Retain as historical context only. | instrument |
| cache-rule-v2-2026-07-22 | OPEN (createdAt=2026-07-22T08:00:00Z) | The replacement rule records expiry and source. | Owners: platform-team, governance-team; Supersedes: stale-cache-rule-2026-07-18; Receipt: https://example.org/evidence/cache-rule-v2; | instrument |
| missing-owner-and-evidence-2026-07-23 | OPEN | A reproducible output exists, but responsibility and evidence metadata are absent. | Assign an owner and attach an evidence receipt. | methodology |
| safe-pipes-2026-07-24 | OPEN | The literal expression \|delta\| and code span `left | right` must remain in one cell. | Owner: parser-team; preserve escaped and code-span pipes. Evidence: fixtures/evidence/safe-pipes.json; | instrument |
| duplicate-fixture-id-2026-07-25 | OPEN | First occurrence of a deliberately duplicated identifier. | Owner: fixture-team; reject both duplicate rows. | methodology |
| duplicate-fixture-id-2026-07-25 | RESOLVED 2026-07-26 | Second occurrence of a deliberately duplicated identifier. | Owner: fixture-team; do not silently choose one row. | methodology |
| unsafe-unescaped-pipe-2026-07-26 | OPEN | The parser must preserve alpha | beta instead of guessing a shifted boundary. | Owner: parser-team; fail this row loudly. | instrument |
| unbalanced-backticks-2026-07-27 | OPEN | A code span starts with `alpha | beta but never closes. | Owner: parser-team; mark the complete ambiguous middle as malformed. | instrument |
