# Benchmark and Result Discipline

LedgerLens is a working prototype whose benchmarks cover mechanics and integration. It does not
benchmark the truth of the underlying ledger and cannot independently validate Sophia-AGI.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Result classes

### A. Deterministic fixture benchmark

Runs on the public sanitized fixture without:

- live DataHub;
- paid APIs;
- an LLM;
- external network calls.

It may establish:

- parser behavior on declared fixture cases;
- duplicate/malformed-row handling;
- stable URN and metadata mapping;
- supersession traversal;
- missing-field detection;
- deterministic remediation ordering;
- JSON/Markdown output shape;
- prompt-injection containment tests.

It may not establish:

- compatibility with a live DataHub release;
- behavior on a private/full ledger;
- production performance;
- correctness of source findings;
- independent validation.

Run:

```bash
make benchmark
```

Default receipt:

```text
artifacts/benchmarks/deterministic-fixture.json
```

### B. Live DataHub smoke

Runs only when an operator explicitly starts the pinned DataHub OSS quickstart.

It may establish:

- the selected DataHub version became healthy;
- fixture metadata was accepted;
- expected entities and lineage could be retrieved;
- MCP and audit-bridge calls completed;
- a remediation report was produced from live metadata.

It may not establish:

- source truth;
- independent evidence review;
- production readiness;
- multi-tenant security;
- performance at scale.

Run:

```bash
make datahub-up
make live-smoke
```

Default receipt:

```text
artifacts/benchmarks/live-datahub-smoke.json
```

## Required receipt fields

Every published receipt must include:

```json
{
  "schemaVersion": "1.0",
  "benchmarkKind": "deterministic-fixture or live-datahub-smoke",
  "status": "PASS, FAIL, or NOT_RUN",
  "candidateOnly": true,
  "canClaimAGI": false,
  "externalValidation": false,
  "startedAtUtc": "ISO-8601",
  "finishedAtUtc": "ISO-8601",
  "durationSeconds": 0.0,
  "gitCommit": "sha or unknown",
  "gitDirty": false,
  "command": [],
  "environment": {},
  "checks": [],
  "artifacts": [],
  "limitations": []
}
```

The `artifacts` array lists outputs produced by the benchmarked command. The receipt must not
hash or list itself; use a detached manifest if receipt-file integrity must be distributed
separately.

Live receipts additionally require:

- DataHub OSS version;
- DataHub CLI version;
- MCP package/version;
- endpoint identity with secrets removed;
- proof that live mode was selected.

## Status semantics

| Status | Meaning |
|---|---|
| `PASS` | Every declared check completed under the recorded mode |
| `FAIL` | At least one declared check failed |
| `NOT_RUN` | Template or planned result; no execution occurred |

Never convert `NOT_RUN` into `PASS` because a fixture file exists. Never describe deterministic
fixture success as a live DataHub result.

## Timing

Wall-clock time is recorded for regression visibility, not as a performance leaderboard. A single
local run without controlled hardware, repetitions, warmup, and uncertainty is not a throughput
claim.

If performance is presented:

1. state hardware and OS;
2. run at least five measured repetitions after warmup;
3. report median and range or confidence interval;
4. fix input size and DataHub state;
5. keep functional pass/fail separate from timing.

## Publishing results

Use the templates in `docs/results/` as immutable examples. Write actual receipts under ignored
`artifacts/benchmarks/` during development. Publish only sanitized receipts that:

- correspond to a committed revision;
- have a documented command;
- match the named result class;
- preserve failures;
- contain no credentials or private paths;
- state limitations;
- pass `make public-check`.

Render a human-readable summary with:

```bash
make benchmark-summary
```

## Contest presentation

For the demo, present both classes on one slide:

| Deterministic fixture | Live DataHub smoke |
|---|---|
| Reproducible in CI | Explicit local integration gate |
| No credentials | Pinned DataHub version |
| Parser and report mechanics | Real entity/MCP round trip |
| Not a live result | Not independent validation |

This distinction is part of LedgerLens's value: the agent reports what was actually measured.
