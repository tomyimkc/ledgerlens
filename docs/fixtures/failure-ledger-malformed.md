# LedgerLens malformed-row regression fixture

This file is intentionally invalid and must not be ingested as a valid ledger.

| ID | Status | Claim Impact | Required Response | Kind |
|---|---|---|---|---|
| duplicate-id-2026-07-31 | OPEN | First copy. | Reject duplicates. | instrument |
| duplicate-id-2026-07-31 | OPEN | Second copy. | Reject duplicates. | instrument |
| unsafe-pipe-2026-07-31 | OPEN | Unescaped A | B boundary. | Quarantine the ambiguous row. | methodology |
| unbalanced-backtick-2026-07-31 | OPEN | `Unclosed code span | Do not guess field boundaries. | instrument |
