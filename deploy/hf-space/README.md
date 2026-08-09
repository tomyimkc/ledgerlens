---
title: LedgerLens Incident Commander
emoji: 🚨
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
short_description: DataHub incident plans sealed by deterministic policy.
---

# LedgerLens — Policy-Sealed Incident Commander

LedgerLens turns DataHub-shaped incident context into a bounded response plan, model-variant
verification, deterministic authorization, receipted operational fanout, DataHub write-back, and
next-agent memory.

This public Space runs the **deterministic fixture replay**:

- no live DataHub request;
- no GitHub, Slack, PagerDuty, or Jira mutation;
- no paid model call;
- every simulated external receipt uses `fixture://`;
- AI output is advisory and deterministic policy remains the authority.

Open the **Seal Lab** to submit controlled plan, verifier, and target changes to the real
server-side gate without executing any provider tool.

```yaml
candidateOnly: true
canClaimAGI: false
```

Source and live evidence receipts are published in `tomyimkc/ledgerlens`, release `v0.2.0`.

The previous Sophia Governance Gate Space is preserved on branch
`backup/governance-gate-20260731`.
