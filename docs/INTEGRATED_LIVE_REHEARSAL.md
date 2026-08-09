# Supervised integrated live rehearsal

This owner-only harness targets the remaining evidence gap without weakening the product's
authority boundary:

```text
official DataHub MCP read
  → native model plan and advisory verifier panel
  → deterministic exact-plan authorization
  → one bounded GitHub, Slack, PagerDuty, and Jira action
  → policy-gated DataHub save_document
  → official MCP get_entities read-back
```

The command is not part of the public fixture and is not run in default CI. It can create
persistent rehearsal artifacts in all four providers and one document in an owner-controlled
DataHub instance.

## Claim boundary

Even a successful receipt proves only one supervised, bounded, same-process rehearsal. It does
not prove incident causality, user impact, recovery, sustained operation, provider reliability,
production readiness, independent validation, model-family independence, or AGI.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Safety properties

- Two explicit CLI confirmations are required: one for provider actions and one for DataHub
  write-back.
- The Make target adds a third operator phrase:
  `CONFIRM_INTEGRATED_LIVE=READ_ACT_WRITE`.
- If the owner-controlled instance lacks an entity satisfying the context contract, the separate
  seed target requires `CONFIRM_DATAHUB_CONTEXT_SEED=INGEST_SYNTHETIC_CONTEXT`. The ingested
  catalog is explicitly marked synthetic and is not counted as the combined-run receipt.
- `make integrated-live-preflight` performs only the DataHub reads needed to build context. It
  makes no model call, provider call, or mutation.
- Provider adapters receive only the frozen plan authorized by the deterministic gate.
- DataHub `save_document` receives a separate exact-call authorization from the write-back policy.
- A run is marked `integratedSameProcessRun: true` only when every planned provider action
  succeeded, DataHub write-back succeeded, and the exact returned document URN was retrieved
  through official MCP.
- Failure receipts are sanitized and fail closed. If execution began, inspect the owner-controlled
  provider destinations for partial rehearsal artifacts before retrying.
- Secrets are read from environment variables and are never serialized into the receipt.

## Required environment

Use native provider configuration. Do not put secrets in the repository, command history,
screenshots, or issue text.

```text
OPENAI_API_KEY or ANTHROPIC_API_KEY
LEDGERLENS_ACTION_AUTHORIZATION_SECRET  # at least 32 bytes
GITHUB_TOKEN
LEDGERLENS_SLACK_WEBHOOK_URL
LEDGERLENS_PAGERDUTY_ROUTING_KEY
LEDGERLENS_JIRA_SITE_URL
LEDGERLENS_JIRA_EMAIL
LEDGERLENS_JIRA_API_TOKEN
LEDGERLENS_JIRA_PROJECT_KEY
LEDGERLENS_JIRA_ISSUE_TYPE
DATAHUB_GMS_URL
DATAHUB_GMS_TOKEN
DATAHUB_MCP_COMMAND
```

The default planner/verifier configuration is OpenAI-native. If only `ANTHROPIC_API_KEY` is
present, the harness selects the native Anthropic client but requires explicit
`LEDGERLENS_PLANNER_MODEL` and `LEDGERLENS_VERIFIER_MODELS` values rather than guessing model
names. Mixed-provider runs must also set `LEDGERLENS_PLANNER_PROVIDER` and
`LEDGERLENS_VERIFIER_PROVIDER` explicitly. Distinct model labels do not establish provider-family
independence.

## Procedure

1. Start or select an owner-controlled DataHub instance. Keep it loopback-only or otherwise
   access-controlled.
   If the deployment wrapper enforces a free-space check, place its temporary state directory on
   a filesystem with at least 20 GiB available; do not delete unrelated images, volumes, models,
   or repositories merely to satisfy the rehearsal.
2. If using an SSH tunnel, bind it to a local-only port, for example:

   ```bash
   ssh -N -L 18080:127.0.0.1:8080 owner-controlled-host
   export DATAHUB_GMS_URL=http://127.0.0.1:18080
   ```

3. Export the DataHub service token without printing it.
4. Run the read-only preflight. If and only if it reports that the selected root is absent or
   lacks required owner/runbook/schema context, review the 120-asset synthetic catalog and, with
   explicit owner authorization, seed that context:

   ```bash
   CONFIRM_DATAHUB_CONTEXT_SEED=INGEST_SYNTHETIC_CONTEXT \
     make integrated-live-seed-context
   ```

   This is a live DataHub metadata mutation, but it is setup—not evidence that an incident
   occurred, that the metadata is production-derived, or that provider actions succeeded.
5. Verify the read-only path:

   ```bash
   make integrated-live-preflight
   ```

   The generated `artifacts/integrated-live-rehearsal/preflight.json` must show:

   ```json
   {
     "ready": true,
     "externalMutations": false,
     "providerToolsExecuted": false,
     "candidateOnly": true,
     "canClaimAGI": false
   }
   ```

6. Export the provider credentials without printing them. Review the provider destinations,
   incident ID, Jira project/type, policy targets, and the expected rehearsal artifacts.
7. Only after the owner explicitly authorizes the run:

   ```bash
   CONFIRM_INTEGRATED_LIVE=READ_ACT_WRITE make integrated-live-rehearsal
   ```

8. Monitor the process through completion. Do not infer success from a provider notification.
   Inspect the linked JSON receipt and require all of:

   ```json
   {
     "status": "executed-writeback-readback",
     "providerActionsSucceeded": true,
     "integratedSameProcessRun": true,
     "candidateOnly": true,
     "canClaimAGI": false
   }
   ```

9. Verify the owner-controlled provider surfaces, exact DataHub document URN, and receipt
   limitations. Redact a presentation-safe derivative before publishing.
10. Stop the SSH tunnel by interrupting its own terminal session. Stop the private DataHub stack
   using its normal stack command; do not delete volumes merely to finish the rehearsal.

## Failure handling

- Exit `2`: prerequisites, confirmation, or read-only DataHub context failed before provider
  execution.
- Exit `3`: execution was attempted but the complete integrated proof did not succeed. When an
  exception prevents receipt reconciliation, `externalMutations` and `providerToolsExecuted` are
  recorded as `null`, with `externalMutationsMayHaveOccurred: true`, rather than guessing.
- A failed-closed receipt never promotes the evidence ladder. Treat it as diagnostic evidence and
  inspect for partial provider artifacts before deciding whether to retry.
