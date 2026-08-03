#!/usr/bin/env python3
"""One linked live rehearsal: read -> plan -> verify -> authorize -> real provider fanout.

This is the missing single-run evidence bundle. Today's live evidence is spread across three
separately-run receipts (AI rehearsal, one GitHub issue, one DataHub write-back) that only
"link" by sharing an incident id. This script runs the whole chain in ONE invocation and
emits ONE receipt whose provider-action entries are real GitHub / Slack / PagerDuty / Jira
receipts.

Safety:

* Nothing executes against a real provider unless ``--confirm-live`` is passed AND every
  required credential is present in the environment. Absent either, it fails closed.
* Credentials are read only from the environment, never printed, and never written into the
  receipt (each adapter already sanitizes its own receipt).
* The planner and verifiers are the real 020s roles; the policy gate is the production gate.
  No model authorizes itself.

Scope this script covers today: the real four-provider fanout — the three provider receipts
(Slack, PagerDuty, Jira) that have never executed live, plus GitHub. The DataHub context read
uses the bundled synthetic catalog, and the controlled DataHub write-back remains the separately
receipted path (evidence E-07); wiring a live DataHub read/write-back into this same run is the
supervised-session extension documented in ``docs/LIVE_DATAHUB_PUBLIC.md`` and requires the
owner's own instance.

Credentials (environment only):

    GITHUB_TOKEN                          fine-grained PAT, Issues: read & write on one repo
    LEDGERLENS_SLACK_WEBHOOK_URL          Slack incoming webhook (one channel)
    LEDGERLENS_PAGERDUTY_ROUTING_KEY      PagerDuty Events API v2 routing key (one service)
    LEDGERLENS_JIRA_SITE_URL              e.g. https://your-site.atlassian.net
    LEDGERLENS_JIRA_EMAIL                 Atlassian account email
    LEDGERLENS_JIRA_API_TOKEN             Atlassian API token (restricted account)
    LEDGERLENS_ACTION_AUTHORIZATION_SECRET  >=32 bytes, HMAC signing secret
    SOPHIA_020S_KEY                       020s planner/verifier key
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ledgerlens.actions import (  # noqa: E402
    ActionAuthorizer,
    GitHubIssueAdapter,
    JiraIssueAdapter,
    PagerDutyEventsAdapter,
    SlackAdapter,
)
from ledgerlens.catalog_runtime import (  # noqa: E402
    CatalogContextProvider,
    incident_from_catalog,
    load_incident_catalog,
)
from ledgerlens.config import Settings  # noqa: E402
from ledgerlens.incident_integration import (  # noqa: E402
    ActionRegistryExecutor,
    OrchestratorIncidentBackend,
)
from ledgerlens.incident_models import Incident, IncidentContext  # noqa: E402
from ledgerlens.runtime_factory import build_020s_ai_roles, build_policy_gate  # noqa: E402

DEFAULT_INCIDENT = "inc-analytics-downstream_availability-01"
DEFAULT_OUTPUT = Path("benchmarks/incident_commander/live-incident-rehearsal-receipt.json")

# The four real collaboration surfaces, matching the production policy allowlist.
POLICY_TARGETS = {
    "github.issue.create": ["tomyimkc/ledgerlens"],
    "slack.message.post": ["#inc-data-platform"],
    "pagerduty.event.trigger": ["pagerduty:events-v2"],
    "jira.issue.create": ["DATAOPS"],
}


@dataclass(frozen=True)
class ProviderCredentials:
    """Credentials read from the environment; never logged or serialized."""

    github_token: str
    slack_webhook_url: str
    pagerduty_routing_key: str
    jira_site_url: str
    jira_email: str
    jira_api_token: str

    @classmethod
    def from_env(cls) -> tuple[ProviderCredentials | None, list[str]]:
        fields = {
            "github_token": "GITHUB_TOKEN",
            "slack_webhook_url": "LEDGERLENS_SLACK_WEBHOOK_URL",
            "pagerduty_routing_key": "LEDGERLENS_PAGERDUTY_ROUTING_KEY",
            "jira_site_url": "LEDGERLENS_JIRA_SITE_URL",
            "jira_email": "LEDGERLENS_JIRA_EMAIL",
            "jira_api_token": "LEDGERLENS_JIRA_API_TOKEN",
        }
        values: dict[str, str] = {}
        missing: list[str] = []
        for attr, env_name in fields.items():
            value = os.getenv(env_name)
            if not value:
                missing.append(env_name)
            else:
                values[attr] = value
        if missing:
            return None, missing
        return cls(**values), []


def build_action_executor(
    credentials: ProviderCredentials,
    authorizer: ActionAuthorizer,
    *,
    transports: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> ActionRegistryExecutor:
    """Assemble the real four-provider executor.

    ``transports`` maps an action type to an injected ``HttpTransport`` so this can be
    exercised offline in tests without live calls or real credentials.
    """

    transports = transports or {}
    adapters = {
        "github.issue.create": GitHubIssueAdapter(
            credentials.github_token,
            authorizer=authorizer,
            transport=transports.get("github.issue.create"),
            timeout=timeout,
        ),
        "slack.message.post": SlackAdapter(
            authorizer=authorizer,
            webhook_url=credentials.slack_webhook_url,
            transport=transports.get("slack.message.post"),
            timeout=timeout,
        ),
        "pagerduty.event.trigger": PagerDutyEventsAdapter(
            credentials.pagerduty_routing_key,
            authorizer=authorizer,
            transport=transports.get("pagerduty.event.trigger"),
            timeout=timeout,
        ),
        "jira.issue.create": JiraIssueAdapter(
            credentials.jira_site_url,
            authorizer=authorizer,
            email=credentials.jira_email,
            api_token=credentials.jira_api_token,
            transport=transports.get("jira.issue.create"),
            timeout=timeout,
        ),
    }
    return ActionRegistryExecutor(adapters, authorizer=authorizer)


def _automation_policy(incident: Incident) -> dict[str, Any]:
    """Map any incident onto the four real collaboration action types.

    Mirrors ``scripts/run_incident_ai_rehearsal.py`` so the 020s planner proposes only
    bounded collaboration actions, never a production mutation.
    """

    fact_ids = [
        "incident-id",
        "incident-severity",
        "root-asset",
        "primary-owner",
        "affected-field",
        "blast-radius",
        "runbook",
    ]
    common = {"evidence_fact_ids": fact_ids, "risk": "low", "requires_human_approval": False}
    return {
        "requiredActions": [
            {
                "action_type": "github.issue.create",
                "target": "tomyimkc/ledgerlens",
                "parameters": {
                    "owner": "tomyimkc",
                    "repository": "ledgerlens",
                    "title": f"{incident.incident_id}: {incident.title}",
                    "body": (
                        "LedgerLens live rehearsal incident record. Root cause, user impact, "
                        "and recovery remain unverified."
                    ),
                    "labels": ["incident", "ledgerlens", "rehearsal"],
                },
                **common,
            },
            {
                "action_type": "slack.message.post",
                "target": "#inc-data-platform",
                "parameters": {
                    "channel": "#inc-data-platform",
                    "text": (
                        f"{incident.incident_id}: LedgerLens live rehearsal. Recorded DataHub "
                        "incident context is available. Root cause and recovery unverified."
                    ),
                },
                **common,
            },
            {
                "action_type": "pagerduty.event.trigger",
                "target": "pagerduty:events-v2",
                "parameters": {
                    "summary": f"{incident.incident_id}: {incident.title}",
                    "source": "ledgerlens",
                    "severity": "critical",
                    "dedup_key": incident.incident_id,
                    "custom_details": {
                        "claimBoundary": (
                            "Metadata-derived context; causality and recovery unverified."
                        )
                    },
                },
                **common,
            },
            {
                "action_type": "jira.issue.create",
                "target": "DATAOPS",
                "parameters": {
                    "project_key": "DATAOPS",
                    "summary": f"{incident.incident_id}: verify recovery",
                    "description": (
                        "Verify a fresh DataHub assertion before resolving. Provider receipts "
                        "do not prove incident recovery."
                    ),
                    "issue_type": "Task",
                    "labels": ["incident", "ledgerlens", "rehearsal"],
                },
                **common,
            },
        ],
        "claimBoundary": {
            "candidateOnly": True,
            "canClaimAGI": False,
            "providerFamilyIndependenceClaimed": False,
        },
    }


def _with_policy(provider: CatalogContextProvider, incident: Incident) -> IncidentContext:
    context = provider(incident)
    metadata = dict(context.metadata)
    metadata["automationPolicy"] = _automation_policy(incident)
    return context.model_copy(update={"metadata": metadata})


def run_backend(
    backend: OrchestratorIncidentBackend,
    incident_id: str,
) -> tuple[Any, Any, dict[str, Any], bool]:
    """Trigger the backend, then execute if the plan authorized.

    Returns ``(prepared, result, state, executed)``. Extracted so the full trigger ->
    execute path can be exercised offline with a deterministic planner and fake adapters.
    """

    state = backend.trigger({"incident_id": incident_id})
    prepared = backend.prepared_run
    if prepared is None:
        raise RuntimeError("backend did not retain the prepared run")
    result = None
    executed = False
    if prepared.authorization.authorized:
        # execute() compares plan_hash against plan_fingerprint(state); the trigger state
        # exposes exactly that value at planner.plan_hash. Passing authorization.plan_id
        # would fail closed with "dashboard grant plan fingerprint does not match".
        plan_hash = state.get("planner", {}).get("plan_hash")
        state = backend.execute({"incident_id": incident_id, "plan_hash": plan_hash})
        result = backend.orchestration_result
        executed = True
    return prepared, result, dict(state), executed


def assemble_receipt(
    *,
    prepared: Any,
    result: Any,
    state: Any,
    settings: Settings,
    executed: bool,
) -> dict[str, Any]:
    """Build the single linked receipt from the prepared run and execution result."""

    context_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                prepared.context.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    return {
        "schemaVersion": "ledgerlens.live-incident-rehearsal.v1",
        "kind": "live-incident-rehearsal",
        "status": ("executed" if executed else "authorized-not-executed"),
        "networkUsed": True,
        "externalMutations": executed,
        "models": {
            "planner": settings.planner_model,
            "verifiers": list(settings.verifier_model_ids),
            "provider": settings.llm_base_url,
            "providerFamilyIndependenceClaimed": False,
        },
        "incident": prepared.incident.model_dump(mode="json", by_alias=True),
        "contextDigest": context_digest,
        "plan": prepared.plan.model_dump(mode="json", by_alias=True),
        "verification": prepared.verification.model_dump(mode="json", by_alias=True),
        "authorization": prepared.authorization.model_dump(mode="json", by_alias=True),
        "dashboardState": state,
        "orchestrationResult": (
            result.model_dump(mode="json", by_alias=True) if result is not None else None
        ),
        "limitations": [
            "Each provider receipt proves exactly one bounded rehearsal action, not sustained "
            "reliability, scale, or real on-call adoption.",
            "The Slack message, PagerDuty event, and Jira issue persist as small, clearly-labeled "
            "rehearsal artifacts in throwaway/rehearsal-scoped destinations.",
            "Distinct model variants were used; provider-family independence is not claimed.",
            "No incident causality, user impact, or recovery is established.",
            "The DataHub context read uses the bundled synthetic catalog; the controlled DataHub "
            "write-back remains the separately receipted E-07 path.",
        ],
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one linked live incident rehearsal: real 020s planner + verifiers + policy "
            "gate, then real GitHub/Slack/PagerDuty/Jira fanout, into one receipt."
        )
    )
    parser.add_argument("--incident-id", default=DEFAULT_INCIDENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required acknowledgment that this executes real provider actions.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not args.confirm_live:
        print("--confirm-live is required to execute real provider actions", file=sys.stderr)
        return 2
    if args.output.exists() and not args.force:
        print(f"refusing to overwrite existing receipt: {args.output}", file=sys.stderr)
        return 2
    if not os.getenv("SOPHIA_020S_KEY"):
        print("SOPHIA_020S_KEY is required", file=sys.stderr)
        return 2
    auth_secret = os.getenv("LEDGERLENS_ACTION_AUTHORIZATION_SECRET")
    if not auth_secret or len(auth_secret.encode("utf-8")) < 32:
        print(
            "LEDGERLENS_ACTION_AUTHORIZATION_SECRET (>=32 bytes) is required",
            file=sys.stderr,
        )
        return 2
    credentials, missing = ProviderCredentials.from_env()
    if credentials is None:
        print(f"missing provider credentials: {', '.join(missing)}", file=sys.stderr)
        return 2

    catalog = load_incident_catalog()
    incident = incident_from_catalog(catalog, args.incident_id)
    provider = CatalogContextProvider(catalog)
    settings = Settings.model_validate(
        {
            "ai_verification_enabled": True,
            "sophia_020s_key": os.environ["SOPHIA_020S_KEY"],
            "planner_model": "gpt-5.6-sol",
            "verifier_models": "gpt-5.6-terra,gpt-5.5",
            "verifier_quorum": 2,
            "verifier_min_confidence": 0.85,
            "llm_timeout_seconds": 60,
        }
    )
    authorizer = ActionAuthorizer(
        auth_secret.encode("utf-8"),
        issuer="ledgerlens-live-rehearsal",
    )
    executor = build_action_executor(credentials, authorizer)
    roles = build_020s_ai_roles(settings)
    executed = False
    result = None
    try:
        backend = OrchestratorIncidentBackend(
            incident_resolver=lambda payload: incident,
            context_provider=lambda value: _with_policy(provider, value),
            planner=roles.planner,
            verifier_panel=roles.verifier_panel,
            policy_gate=build_policy_gate(
                POLICY_TARGETS,
                minimum_plan_confidence=0.8,
                minimum_verifier_confidence=0.85,
                quorum=2,
            ),
            executor=executor,
            writeback=lambda run: None,
        )
        prepared, result, state, executed = run_backend(backend, incident.incident_id)
        receipt = assemble_receipt(
            prepared=prepared,
            result=result,
            state=state,
            settings=settings,
            executed=executed,
        )
    except Exception as exc:
        # A partial fanout can leave some real artifacts; record what happened rather than
        # crashing. Any already-created provider artifacts are noted in the error.
        receipt = {
            "schemaVersion": "ledgerlens.live-incident-rehearsal.v1",
            "kind": "live-incident-rehearsal",
            "status": "failed-closed",
            "networkUsed": True,
            "externalMutations": executed,
            "incidentId": incident.incident_id,
            "error": f"{type(exc).__name__}: {exc}",
            "limitations": [
                "The run did not complete the full authorized fanout.",
                "Inspect the error and any provider dashboards for partial rehearsal artifacts.",
            ],
            "candidateOnly": True,
            "canClaimAGI": False,
        }
    finally:
        roles.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": receipt["status"],
                "externalMutations": executed,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            sort_keys=True,
        )
    )
    return 0 if executed else 3


if __name__ == "__main__":
    raise SystemExit(main())
