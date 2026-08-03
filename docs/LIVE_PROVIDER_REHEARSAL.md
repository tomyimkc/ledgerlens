# Live provider rehearsal — owner setup

This guide is for the **owner only**. It lists the least-privilege credentials the one-run
live rehearsal ([`scripts/run_live_incident_rehearsal.py`](../scripts/run_live_incident_rehearsal.py))
needs, exactly how to obtain each, and how to supply them without any secret touching the
repository, chat, logs, or a receipt.

The rehearsal runs the real pipeline — 020s planner + two verifiers + the deterministic
policy gate — and then executes one bounded action against each of GitHub, Slack, PagerDuty,
and Jira, emitting **one linked receipt**. It refuses to do anything unless `--confirm-live`
is passed **and** every credential below is present. The adapters sanitize their own
receipts; no credential is ever serialized.

> These receipts each prove **one bounded rehearsal action**, not sustained reliability,
> scale, or real on-call adoption. Use throwaway or rehearsal-scoped destinations.

## Credentials

All values are read from the environment only. Put them in a local `.env` (already
git-ignored) or export them in your shell. **Never** paste them into a commit, an issue, a
PR, chat, or a screenshot.

### 1. Slack — Incoming Webhook (one channel)

Least-privilege: a webhook is bound by Slack to a single channel and can only post; it
cannot read or list anything.

1. Create a throwaway workspace, or a private `#inc-data-platform` channel in one you own.
2. Go to <https://api.slack.com/apps> → **Create New App** → **From scratch**.
3. **Incoming Webhooks** → toggle **Activate**.
4. **Add New Webhook to Workspace** → pick the channel → **Allow**.
5. Copy the webhook URL.

```bash
export LEDGERLENS_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T..."
```

Revoke the specific webhook after recording. Note: a webhook-mode receipt carries only
`{mode, delivery}` — a judge cannot independently click through to the message, so the
receipt says so.

### 2. PagerDuty — Events API v2 routing key (one service, no-op escalation)

Least-privilege: an integration/routing key can only send events to its one service; it
cannot read or change your account.

1. Free/trial account → **Services** → **New Service** (e.g. "LedgerLens Rehearsal").
2. Set the escalation policy to a **no-op** one so nobody is actually paged.
3. Add an **Events API v2** integration → copy the **Integration/Routing Key**.

```bash
export LEDGERLENS_PAGERDUTY_ROUTING_KEY="R0..."
```

### 3. Jira Cloud — restricted API token (one project)

Least-privilege: use a **dedicated, low-privilege account** (not your admin account),
restricted by the project permission scheme to "Create Issues" on one project.

1. Create a Jira Cloud site and a `DATAOPS` project.
2. Create/pick a dedicated account with only create-issue permission on `DATAOPS`.
3. On that account: <https://id.atlassian.com/manage-profile/security/api-tokens> →
   **Create API token** → copy it.

```bash
export LEDGERLENS_JIRA_SITE_URL="https://your-site.atlassian.net"
export LEDGERLENS_JIRA_EMAIL="rehearsal-account@example.com"
export LEDGERLENS_JIRA_API_TOKEN="ATATT..."
```

A Jira token inherits the account's permissions, so the **account's restricted project
role is the real boundary**, not the token. Unlike Slack/PagerDuty, a Jira receipt carries a
browsable issue URL a judge with project read access can independently open.

### 4. GitHub — fine-grained PAT (already proven)

Least-privilege: a fine-grained PAT scoped to `tomyimkc/ledgerlens`, **Issues: Read &
write** only.

```bash
export GITHUB_TOKEN="github_pat_..."
```

### 5. Action authorization secret (HMAC signing, ≥32 bytes)

Not a provider credential — the HMAC key the executor uses to sign each action grant.

```bash
export LEDGERLENS_ACTION_AUTHORIZATION_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
```

### 6. Planner/verifier key

```bash
export SOPHIA_020S_KEY="..."
```

## Run it

```bash
uv run python scripts/run_live_incident_rehearsal.py --confirm-live \
  --output benchmarks/incident_commander/live-incident-rehearsal-receipt.json
# Then scan the receipt for accidental secret exposure before committing it:
uv run python scripts/check_secrets.py
```

Exit `0` means the plan was authorized and all four provider actions executed;
`3` means authorized but not executed; `2` means it failed closed on a missing
prerequisite. The linked receipt records the plan, verifier quorum, authorization, and
each real provider receipt.

## What this does and does not establish

- **Does:** the real pipeline authorizes a bounded plan and executes one action per provider,
  leaving sanitized, linked receipts.
- **Does not:** prove incident causality, user impact, recovery, production readiness,
  provider-family independence, or sustained reliability. The DataHub context read uses the
  bundled synthetic catalog; a live DataHub read/write-back in the same run is the supervised
  self-hosted session in [`docs/LIVE_DATAHUB_PUBLIC.md`](LIVE_DATAHUB_PUBLIC.md), which uses
  **your own** DataHub instance — never DataHub's public demo, whose terms of service forbid
  programmatic access.
