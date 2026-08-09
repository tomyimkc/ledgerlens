# LedgerLens hostile-judge critique

**Assessment date:** August 9, 2026  
**Scope:** Contest hardening branch after Seal Lab and DataHub Context Cut implementation.
This is an internal readiness assessment, not a judging result.

## Thirty-second verdict

LedgerLens now has two judge-testable ideas rather than one long explanation:

1. **Seal Lab:** mutate the reviewed plan and the current server gate refuses drift, a verifier
   objection, or an off-allowlist target before any tool runs.
2. **DataHub Context Cut:** hold one recorded model plan fixed, remove ownership or lineage, and
   the current server policy withdraws authority because the tool's required catalog facts are
   absent.

That combination is distinctive: **the model proposes work, DataHub supplies the facts that make
specific tools eligible, and deterministic policy binds authority to the exact plan.** It is more
defensible than generic human approval and more DataHub-native than a tool-calling demo with a
catalog logo.

## Three strengths

1. **Authority is structurally outside the model.** Plan fingerprints, target/parameter
   allowlists, verifier quorum, per-tool evidence contracts, and fail-closed reason codes are
   ordinary typed Python.
2. **DataHub is now visibly load-bearing.** Owner, lineage, asset, severity, and runbook fact IDs
   are not just shown in a panel; E-20 lets a judge remove them and watch authority disappear.
3. **Evidence classes are unusually explicit.** Fixture replay, recorded-model output, live
   deterministic replay, local-live DataHub work, and one supervised provider rehearsal remain
   separate. The public page never needs a secret.

## Five residual kill risks

1. **The clickable context is still synthetic.** Context Cut proves the implemented evidence
   contract, not a live DataHub request or production metadata quality.
2. **Adaptive re-planning is not demonstrated publicly.** E-20 deliberately fixes the recorded
   plan; the planner and verifiers are not re-run per cut. The code now supports an empty
   abstention and exposes evidence requirements to the tool-using planner, but no fresh adaptive
   model trace was produced in this hardening pass, so none is claimed.
3. **Live work remains narrow.** E-16 is one supervised action per provider on August 3, 2026,
   not sustained reliability, scale, adoption, or incident recovery.
4. **External judgment is absent.** The consent-safe reviewer protocol exists, but no completed
   review can be reported until real people participate and consent.
5. **Submission edges remain time-sensitive.** The public YouTube title still uses “Autonomous,”
   final incognito playback is owner-visible, the upstream DataHub MCP PR is open/unmerged, and
   the final release/deployment SHA must match the submitted artifact.

## Scorecard guess

| Criterion | Current guess | Skeptical reason |
|---|---:|---|
| Meaningful use of DataHub | 7.5 / 10 | Context Cut makes facts load-bearing, but the public DataHub context remains synthetic. |
| Technical execution | 7.8 / 10 | Strong typed/gated implementation and one live fanout; no sustained operation. |
| Originality | 8.0 / 10 | Exact-plan authority plus per-tool DataHub fact contracts is memorable and falsifiable. |
| Real-world usefulness | 6.2 / 10 | Credible on-call shape; no user study or production outcome. |
| Submission quality | 7.8 / 10 | Two interactive proofs, evidence map, video source, and one-command gates; final public checks remain. |
| Open-source bonus | 4.5 / 10 | Relevant upstream proposal, still review-required and unmerged. |

**Five-core estimate:** **7.5 / 10.** Winner-contending concept, not winner-safe evidence.

## Big bet shipped: DataHub Context Cut

The Context Cut is intentionally a controlled authorization ablation, not model theater:

1. source one already-published recorded model plan and verifier panel;
2. keep the exact typed plan and seal fixed;
3. remove one synthetic DataHub fact class at a time;
4. run the current `ledgerlens.verification.PolicyGate` server-side;
5. show which tool evidence contracts become ineligible and why;
6. execute no model or provider tool on the Space.

The full map authorizes. Removing ownership, lineage, or most catalog facts denies. Because the
planner is not re-run, the proof supports only the narrow claim that DataHub facts are required
for authorization of that plan.

## Next highest-value bet

Do not add another dashboard. The remaining winner delta is external packaging:

1. get two role-appropriate formative reviewers using the consent-safe 7–10 minute protocol;
2. update or replace the public video so its title and first minute show **Policy-Sealed**,
   Seal Lab, then Context Cut;
3. if an owner-controlled DataHub instance is available, record one combined
   read → plan → authorize → bounded action → write-back receipt;
4. otherwise keep the public Space synthetic rather than weakening its safety boundary.

## Claim boundary

```yaml
candidateOnly: true
canClaimAGI: false
externalMutations: false
```

The submission may claim implemented deterministic authorization behavior, one bounded supervised
provider rehearsal, and a local DataHub write/read-back receipt. It must not claim AGI, validated
uplift, production reliability, incident recovery, provider-family independence, adaptive
re-planning in E-20, or upstream acceptance.
