# LedgerLens Demo Script

**Target runtime:** approximately 41 seconds

**Hard maximum:** under 3 minutes

**Language:** English

**Category:** Agents That Do Real Work

All product proof must use real capture from the running application. Grok-generated clips are
optional, clearly labeled concept visuals only.

## 0:00–0:03 — Hook

**Visual:** Short labeled concept animation: failure records accumulating, ownership and evidence
links separating.

**On-screen label:** `CONCEPT VISUAL — AI-GENERATED`

**Narration:**

> Teams record failures, but those records quickly become stale: owners disappear, evidence drifts
> away, and newer findings supersede older ones without preserving an actionable chain.

## 0:03–0:09 — Product and claim boundary

**Visual:** Real LedgerLens landing page, then architecture overview.

**Narration:**

> LedgerLens is a working DataHub prototype that turns a failure ledger into an
> evidence-grounded remediation queue. It organizes supplied metadata; it does not independently
> validate the underlying findings.

**On-screen:**

```text
candidateOnly: true
canClaimAGI: false
```

## 0:09–0:15 — DataHub metadata

**Visual:** Real DataHub UI showing an ingested finding, ownership, properties, and audit metadata.

**Narration:**

> A conservative parser rejects ambiguous rows. Valid findings receive stable DataHub URNs with
> ownership, evidence references, and audit metadata.

**Required proof:**

- command is visible;
- sanitized fixture name is visible;
- counts and parse warnings are readable;
- no token or private path is visible.

## 0:15–0:21 — Agent does real work

**Visual:** Real LedgerLens remediation queue and saved report.

**Narration:**

> The official DataHub MCP Server grounds a deterministic queue. The agent writes inspectable JSON
> and Markdown artifacts instead of returning only a chat answer.

## 0:21–0:27 — Supersession

**Visual:** Real LedgerLens supersession chain.

```text
Is this historical finding still current?
```

Then show the result and saved report.

**Narration:**

> Explicit supersession preserves history without presenting an outdated record as current.

## 0:27–0:33 — Reproducibility

**Visual:** Real deterministic and live benchmark receipts, with test and version fields readable.

**Narration:**

> Deterministic checks and live DataHub smoke results are separate receipts with their limitations,
> exact versions, and commit identity.

## 0:33–0:39 — Public package and disclosure

**Visual:** Public repository main page, Apache-2.0 license, and disclosure.

**Narration:**

> The repository is public under Apache-2.0. Pre-existing Sophia ledger material is explicitly
> disclosed; the LedgerLens integration is newly built.

## 0:39–0:41 — Close

**Visual:** Short labeled concept end transition and URL.

**Narration:**

> Working prototype. Candidate only. No AGI claim.

**End card:**

```text
LedgerLens
Turn failure records into an evidence-grounded action queue.
github.com/tomyimkc/ledgerlens
```
