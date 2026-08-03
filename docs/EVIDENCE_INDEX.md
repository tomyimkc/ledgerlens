# LedgerLens evidence index

LedgerLens is an **Autonomous Data Incident Commander**: it turns a DataHub-observed incident into a bounded response plan, deterministic authorization decision, receipted work, controlled DataHub write-back, and a handoff for the next responder.

Start with the [public fixture replay](https://tomyimkc-ledgerlens-incident-commander.hf.space/). It needs no account, token, or provider credential. The replay is deliberately synthetic; it never contacts DataHub or a provider. Its receipts start with `fixture://`.

For candid rubric gaps and the non-video scorecard, see the [winner-readiness scorecard](WINNER_READINESS.md).

## Evidence map

| ID | Claim that can be checked | How to check it | Artifact | Scope and limitation | Rubric connection |
|---|---|---|---|---|---|
| E-01 | A judge can replay the incident flow without credentials. | Open the public Space, select **Replay trigger**, and inspect the stages. | [Hosted app](https://tomyimkc-ledgerlens-incident-commander.hf.space/), `scripts/check_hosted_incident_demo.py` | Public deterministic fixture only; no live provider or DataHub call. | Technical execution; submission quality |
| E-02 | DataHub context is central to the response. | Inspect the fixture context and run the documented deterministic ablation. | `fixtures/incident_commander/catalog.json`, `benchmarks/incident_commander/context-ablation-receipt.json` | Synthetic 120-asset, 24-scenario catalog. **Both arms are scripted responders, not the LedgerLens pipeline:** context-ON copies the fixture's pre-labeled ground-truth action list, and context-OFF is a fixed generic script that appends an unsafe action in roughly half of scenarios by a stable hash. The gap is a schema/contract demonstration, not measured planner, verifier, or model capability. See `benchmarks/incident_commander/README.md`. | Meaningful DataHub use; usefulness |
| E-03 | The system reads DataHub-shaped ownership, schema, runbook, and lineage context before planning. | Run `make incident-benchmark`; review scenario-level output in the receipt. | `benchmarks/incident_commander/README.md`, `scripts/run_incident_commander_benchmark.py` | Offline fixture evidence, not a live service query. | Meaningful DataHub use |
| E-04 | The policy gate rejects unsafe or unsupported work instead of relying on model self-approval. | Run the deterministic tests. | `tests/test_verification.py`, `tests/test_incident_dashboard.py`, `tests/test_incident_integration.py` | Test evidence is not a production safety certification. | Technical execution; originality |
| E-05 | Authorization is bound to an exact reviewed plan. | Inspect the frozen-plan execution path and test cases. | `src/ledgerlens/incident_integration.py`, `src/ledgerlens/incident_dashboard.py`, `tests/test_incident_integration.py` | Applies to the implemented command path; it does not prove organizational authorization policy. | Technical execution; originality |
| E-06 | A GitHub action adapter executed one bounded rehearsal action. | Open the receipt and the linked closed issue. | `benchmarks/incident_commander/github-live-action-receipt.json` | Proves only the recorded GitHub creation/closure. Slack, PagerDuty, and Jira do not have live receipts. | Technical execution |
| E-07 | A controlled DataHub OSS document write and official-MCP retrieval occurred. | Inspect the write-back receipt and command metadata. | `benchmarks/incident_commander/datahub-live-writeback-receipt.json` | Local DataHub OSS v1.6.0 evidence; it does not prove recovery, causality, or a hosted public DataHub deployment. | Meaningful DataHub use and write-back |
| E-08 | A planner and two verifier variants produced a bounded, policy-authorized rehearsal plan. | Inspect the rehearsal receipt. | `benchmarks/incident_commander/ai-verification-receipt.json` | No provider action occurred; model labels do not establish provider-family independence. | Technical execution; originality |
| E-09 | The public fixture URL has a credential-free regression check. | Run `make hosted-smoke` or inspect the scheduled workflow artifact. | `.github/workflows/hosted-smoke.yml`, `scripts/check_hosted_incident_demo.py` | Confirms the current fixture contract, not live external integrations. | Submission quality |
| E-10 | The public package can be validated offline. | Run `make judge-check`. | `Makefile`, `.github/workflows/ci.yml`, `scripts/check_non_video_readiness.py` | Does not replace a clean-clone or public-browser check. | Submission quality |
| E-11 | The upstream contribution is a real, still-open proposal. | Open the GitHub issue and PR. | [Issue #159](https://github.com/acryldata/mcp-server-datahub/issues/159), [PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160), `docs/UPSTREAM_MCP_CONTRIBUTION.md` | Open, not merged or accepted. | Open-source bonus |
| E-12 | External-review collection is consent-safe but has no reported result. | Read the protocol and scorecard. | `docs/EXTERNAL_EVALUATION.md`, `docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md` | Infrastructure only until real, consented reviews are completed. | Submission quality; usefulness |
| E-13 | The public Space deployment uses the configured GitHub Environment without exposing tokens. | Inspect workflow and environment names/metadata. | `.github/workflows/deploy-hf-space.yml`, `docs/HOSTED_DEMO.md` | The token value is never included in repository evidence. | Submission quality; security |
| E-14 | Threat boundaries and residual risks are documented. | Read the threat model and execute its offline scan. | `SECURITY.md`, `scripts/check_secrets.py` | Not a security audit or production certification. | Technical execution; usefulness |
| E-15 | The **real** deterministic policy gate authorizes only fact-grounded actions when DataHub context is present, and refuses them when it is absent. | Run `make incident-benchmark-real-pipeline`; inspect the receipt's ON/OFF arms and OFF reason codes. | `benchmarks/incident_commander/real_pipeline_ablation.py`, `benchmarks/incident_commander/real-pipeline-ablation-receipt.json` | Runs the production `VerifierPanel`/`PolicyGate` with a fixed deterministic planner. The OFF arm fails to ground actions by construction, so this proves the fail-closed gate, not model capability or uplift; the LLM-backed planner/verifier are not exercised. | Meaningful DataHub use; technical execution; originality |
| E-17 | The published commands reproduce from a clean clone with no undeclared inputs. | Inspect the reproduction receipt; or clone fresh and run `make setup && make judge-check`. | `benchmarks/results/clean-clone-2026-08-03.json` | Reproduces the deterministic offline gates only (commit `987bd7d`, 283 tests); it does not exercise live DataHub, providers, or the hosted Space, and is not a production or independent-validation claim. | Submission quality |
| E-16 | A single run executed the whole chain — plan, verify, authorize, and one bounded action against **all four providers** — into one linked receipt. | Open the linked receipt; it records the real 020s plan, quorum verification, deterministic authorization, and each provider receipt. | `benchmarks/incident_commander/live-incident-rehearsal-receipt.json`, `scripts/run_live_incident_rehearsal.py`, `tests/test_live_incident_rehearsal.py`, `docs/LIVE_PROVIDER_REHEARSAL.md` | **Produced 2026-08-03** on a supervised run: real 020s planner (`gpt-5.6-sol`) + two verifiers reached quorum, the deterministic gate authorized, and all four adapters executed live — GitHub issue [#29](https://github.com/tomyimkc/ledgerlens/issues/29), a Slack post, a PagerDuty event, and Jira issue [KAN-2](https://tomyimkc.atlassian.net/browse/KAN-2). Each is one bounded rehearsal action, not sustained reliability; distinct model variants do not establish provider-family independence; no causality or recovery is established. | Technical execution; real-world usefulness |

## Evidence layers

Keep these layers distinct when describing LedgerLens:

1. **Public fixture evidence** — reproducible visible flow, clearly marked synthetic.
2. **Local-live evidence** — recorded DataHub OSS and GitHub operations at a named time and version.
3. **Temporary public proof** — a completed, torn-down authenticated DataHub reachability exercise; not an ongoing public service.
4. **Implementation and test evidence** — code and deterministic tests that constrain behavior, not field validation.

## Judge path

1. Open the [public fixture replay](https://tomyimkc-ledgerlens-incident-commander.hf.space/).
2. Trigger one replay and verify: DataHub context → bounded plan → verifier review → deterministic policy → synthetic receipts → write-back → next-agent handoff.
3. Confirm that every public replay receipt is `fixture://` and that cause, impact, and recovery remain unknown.
4. Use E-02 and E-07 to inspect the separate DataHub context and write-back evidence.
5. Use E-06 to distinguish the one recorded GitHub execution from the implemented-but-not-live provider adapters.
6. Run `make judge-check` for the primary local verification path.

## Release identity

The current public baseline is [`v0.2.0`](https://github.com/tomyimkc/ledgerlens/releases/tag/v0.2.0), commit `00063e40bfc785f13e6db938e0795928e4f843ba`. Any later result must identify its commit, command, environment, date, and limitation rather than inheriting that release's status.

## What this evidence does not establish

LedgerLens does not claim production incident outcomes, production readiness, independent validation, provider-family independence, user impact, lower recovery time, live Slack/PagerDuty/Jira execution, upstream acceptance, or general model uplift.
