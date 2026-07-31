# LedgerLens sanitized failure-ledger fixture

This fixture is public, deterministic, and synthetic/sanitized. It preserves the structure needed
to demonstrate LedgerLens without publishing the full pre-existing Sophia-AGI ledger.

```yaml
sourceProject: sophia-agi
sourceMaterial: pre-existing failure-ledger concept and schema
fixtureAuthorship: newly re-authored for LedgerLens on 2026-07-31
transformation: synthetic rows; no private ledger prose or receipt content copied
redistribution: owner-approved for this Apache-2.0 public fixture
candidateOnly: true
canClaimAGI: false
```

The first identifier preserves a disclosed historical finding name for continuity. Its prose,
owners, receipt paths, and outcomes below are fixture material and must not be treated as a copy
of, or evidence for, the private/pre-existing source ledger.

| ID | Status | Claim Impact | Required Response | Kind |
|---|---|---|---|---|
| ledger-validator-blind-spots-2026-07-26 | SUPERSEDED; Owner: Provenance Engineering; receipt: fixture/receipts/parser-regression-v1.json | Historical parser behavior is unverified in this fixture. | Use the strict parser fixture suite; supersededBy: strict-parser-fixture-suite-2026-07-31 | methodology |
| strict-parser-fixture-suite-2026-07-31 | OPEN; Owner: Ledger Adapter; receipt: fixture/receipts/strict-parser-cases.json | No integration result is implied until a receipt is attached. | Run deterministic parser checks; supersedes: ledger-validator-blind-spots-2026-07-26 | engineering |
| mcp-audit-surface-gap-2026-07-26 | OPEN; Owner: DataHub Integration; receipt: fixture/receipts/mcp-audit-surface.json | MCP field coverage must be rechecked against the pinned release. | Verify current MCP fields and label any audit bridge. | infrastructure |
| unowned-evidence-receipt-2026-07-31 | UNVERIFIED | This synthetic row has incomplete provenance metadata. | Assign an owner and attach a reviewable evidence receipt. | governance |
