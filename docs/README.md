# LedgerLens documentation index

LedgerLens is an **Autonomous Data Incident Commander** for DataHub. This folder holds the
judge-facing evidence and the internal working notes. Start with the evidence index.

## Start here

| Document | What it is |
|---|---|
| [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | **Canonical evidence map.** Every checkable claim, how to check it, the artifact, and its explicit limitation. Read this first. |
| [WINNER_READINESS.md](WINNER_READINESS.md) | Candid, adversarially re-audited self-scorecard — including the gaps that are still open and owner-only. |

## Judge-facing evidence

| Document | What it is |
|---|---|
| [HOSTED_DEMO.md](HOSTED_DEMO.md) | The public fixture replay (credential-free) and how it is deployed. |
| [LIVE_PROVIDER_REHEARSAL.md](LIVE_PROVIDER_REHEARSAL.md) | The one recorded run that executed a bounded action across all four providers (E-16). |
| [LIVE_DATAHUB_PUBLIC.md](LIVE_DATAHUB_PUBLIC.md) | The completed, torn-down DataHub reachability exercise — not an ongoing service. |
| [DATAHUB_QUICKSTART.md](DATAHUB_QUICKSTART.md) | Run the pinned DataHub OSS quickstart locally and point LedgerLens at it. |
| [BENCHMARKS.md](BENCHMARKS.md) | The deterministic context-ablation and real-pipeline benchmarks and what they do and do not measure. |
| [UPSTREAM_MCP_CONTRIBUTION.md](UPSTREAM_MCP_CONTRIBUTION.md) | The open-source contribution plan behind upstream Issue #159 / PR #160 (open, not merged). |
| [EXTERNAL_EVALUATION.md](EXTERNAL_EVALUATION.md) | The consent-safe external-review protocol. Infrastructure only until real reviews exist. |
| [SUBMISSION_LEDGER.md](SUBMISSION_LEDGER.md) | The submission ledger: what is claimed, where the artifact is, and its scope. |
| [DEVPOST_SUBMISSION.md](DEVPOST_SUBMISSION.md) | The Devpost submission **source of record** (copy used for the form). |

## Internal working notes — not judge-facing

These are working documents kept for provenance. They are **not** part of the evidence
package and may lag the shipped state; prefer the documents above.

| Document | What it is |
|---|---|
| [GRAND_PRIZE_PLAN.md](GRAND_PRIZE_PLAN.md) | Internal strategy planning. |
| [DEVPOST_CHECKLIST.md](DEVPOST_CHECKLIST.md) | Internal owner submission checklist. |
| [DEVPOST_WRITEUP.md](DEVPOST_WRITEUP.md) | Superseded early Devpost draft — use `DEVPOST_SUBMISSION.md` instead. |

## Reproduce

From the repository root:

```bash
make setup       # provision the pinned toolchain with uv
make judge-check  # run the judge-facing quality and evidence gates
```

Everything reproducible here is deterministic and offline. Live DataHub, live providers, and
the hosted Space are covered by the separately linked receipts, each with its own scope and
limitation in the evidence index.
