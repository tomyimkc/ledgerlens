# LedgerLens submission ledger

A single durable record of what exists, where it lives, and how to verify it — so any later
session or reviewer can reconstruct the submission state without re-deriving it. This is a
data log, not a claim surface; every claim boundary is stated in
[`docs/EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) and [`docs/WINNER_READINESS.md`](WINNER_READINESS.md).

```yaml
candidateOnly: true
canClaimAGI: false
externalValidation: false
```

**Last updated:** 2026-08-09 · **Repo state at update:** final contest feature branch, pending merge

## 1. Identity and public surfaces

| Field | Value |
|---|---|
| Project | LedgerLens — Policy-Sealed Incident Commander |
| Category | Agents That Do Real Work |
| Repository | https://github.com/tomyimkc/ledgerlens (public, Apache-2.0) |
| Public app | https://tomyimkc-ledgerlens-incident-commander.hf.space/ (HTTP 200, fixture replay) |
| HF Space page | https://huggingface.co/spaces/tomyimkc/ledgerlens-incident-commander |
| Deadline | 2026-08-10 17:00 EDT · judge access free through 2026-08-31 |
| Public baseline | v0.2.0 @ `00063e40bfc785f13e6db938e0795928e4f843ba` |
| Final release | v0.2.1 — **not yet published** (cut from the final merged submission revision) |
| Video URL | https://youtu.be/D0SVpDWOrUw |
| Upstream bonus | issue #159 (open) · PR #160 (open, unmerged) — acryldata/mcp-server-datahub |

## 2. Evidence map (see EVIDENCE_INDEX.md for full scope/limits)

| ID | Claim | Primary artifact |
|---|---|---|
| E-01 | Credential-free judge replay | hosted Space, `scripts/check_hosted_incident_demo.py` |
| E-02 | DataHub context is central (scripted schema demo) | `benchmarks/incident_commander/context-ablation-receipt.json` |
| E-04 | Policy gate rejects unsafe/unsupported work | `tests/test_verification.py` |
| E-05 | Authorization bound to exact reviewed plan | `tests/test_incident_dashboard.py` |
| E-06 | GitHub adapter executed a bounded action | `benchmarks/incident_commander/github-live-action-receipt.json` |
| E-07 | Controlled DataHub OSS write-back + MCP read-back | `benchmarks/incident_commander/public-datahub-live-writeback-receipt.json` |
| E-08 | Planner + two verifiers produced a policy-authorized plan | `benchmarks/incident_commander/public-ai-verification-receipt.json` |
| E-11 | Real, still-open upstream contribution | issue #159, PR #160 |
| E-12 | External-review kit ready, no result claimed | `docs/EXTERNAL_EVALUATION.md` |
| **E-15** | **Real** `PolicyGate`/`VerifierPanel` authorizes only fact-grounded actions | `benchmarks/incident_commander/real-pipeline-ablation-receipt.json` |
| **E-16** | One run executed a bounded action against **all four providers** | `benchmarks/incident_commander/public-live-incident-rehearsal-receipt.json` |
| **E-19** | Interactive server-side Seal Lab refuses controlled plan/scope drift | public Space, `/incident/api/seal-lab` |
| **E-20** | DataHub Context Cut withdraws authority when required facts disappear | public Space, `/incident/api/context-cut/full-map` |
| **E-21** | Repeated credential-free samples check the deployed fixture and policy labs | `.github/workflows/hosted-continuity.yml` |

## 3. Produced live artifacts (bounded rehearsal, 2026-08-03)

One authorized run drove real OpenAI GPT-5.6 planner → two verifiers (quorum) → deterministic gate →
four adapters. Each is **one bounded rehearsal action** — not sustained reliability, production
operation, incident causality, or recovery.

| Provider | Live artifact |
|---|---|
| GitHub | issue #29 created (the E-16 receipt records creation; the issue was then closed manually after the run, outside the automated receipt) |
| Slack | message posted via incoming webhook |
| PagerDuty | Events API v2 event (dedup_key = incident id) |
| Jira | issue [KAN-2](https://tomyimkc.atlassian.net/browse/KAN-2) |

Judge-facing receipt:
`benchmarks/incident_commander/public-live-incident-rehearsal-receipt.json` — a
presentation-safe derivative bound to the archived source receipt by SHA-256. It contains no
credential or PII and is explicitly not a new run.

## 4. Campaign PR log

| PR | Commit | What it added |
|---|---|---|
| #22 | `aff0387` | Non-video winner-readiness: evidence index, scorecard, fail-closed gates |
| #23 | `f230e8f` | Benchmark honesty disclosure; moved stale Space-name disclosure to DISCLOSURE.md; judge-clarity fixes; 4 authority-boundary tests |
| #24 | `c168cd9` | Real-pipeline benchmark (E-15); `examples/` folder; DataHub Agent Context Kit + "context problem" framing |
| #25 | `f4a2328` | One-run live provider rehearsal (offline-tested) + owner setup guide |
| #26 | `499136c` | Honest post-audit scorecard refresh (five-core 6.6) |
| #27 | `3bf2ac8` | Fix: correct plan fingerprint to the execute() grant (would have no-op'd a real run) |
| #30 | `987bd7d` | Produced live four-provider rehearsal receipt (E-16); configurable Jira project/issue-type |

## 5. How to reproduce (one line each)

```bash
make judge-check                       # current offline gate: lint, mypy, 316 tests, both benchmarks, readiness
make incident-benchmark-real-pipeline  # E-15: real gate authorizes 100% ON / 0% OFF
make incident-demo                     # local credential-free replay
```

Clean-clone reproduction receipt: `benchmarks/results/clean-clone-2026-08-03.json`
(fresh clone of `987bd7d`: `make setup` 2.23s, `make judge-check` 16.9s, 283 tests).

Live rehearsal (owner credentials in gitignored `.env`, see `docs/LIVE_PROVIDER_REHEARSAL.md`):

```bash
uv run python scripts/run_live_incident_rehearsal.py --confirm-live
```

## 6. Internal readiness snapshot (not official scores)

Five-core average **7.5 / 10**, bonus **4.5 / 10** (separate). Verdict: **finalist-capable**.
Full per-criterion breakdown in [`docs/WINNER_READINESS.md`](WINNER_READINESS.md).

## 7. Owner-only remaining checklist

- [x] Record the public under-three-minute video URL.
- [ ] Cut and publish `v0.2.1` from the final merged submission commit; record the real SHA.
- [ ] Complete Devpost account/team/eligibility review.
- [x] Devpost project is in published state; re-check the final page before the deadline.
- [ ] (Optional, higher value) Supervised live-DataHub session against the owner's own instance for an in-run read→write-back.
- [ ] (Optional) Two consented external reviews via `docs/EXTERNAL_EVALUATION.md`; publish only consented aggregate.
- [ ] (Owner discretion) Revoke the throwaway provider credentials used for E-16; the receipt does not depend on live keys.
