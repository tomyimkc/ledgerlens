#!/usr/bin/env python3
"""Run a real planner plus verifier-panel rehearsal without external mutations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from ledgerlens.catalog_runtime import (
    CatalogContextProvider,
    incident_from_catalog,
    load_incident_catalog,
)
from ledgerlens.config import Settings
from ledgerlens.incident_integration import OrchestratorIncidentBackend
from ledgerlens.incident_models import Incident, IncidentContext
from ledgerlens.runtime_factory import build_020s_ai_roles, build_policy_gate

DEFAULT_INCIDENT = "inc-analytics-downstream_availability-01"
DEFAULT_OUTPUT = Path("benchmarks/incident_commander/ai-verification-receipt.json")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Call one 020s planner and two verifier model variants, then run the "
            "deterministic policy gate. No provider or DataHub mutation is executed."
        )
    )
    parser.add_argument("--incident-id", default=DEFAULT_INCIDENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _automation_policy(incident: Incident) -> dict[str, Any]:
    fact_ids = [
        "incident-id",
        "incident-severity",
        "root-asset",
        "primary-owner",
        "affected-field",
        "blast-radius",
        "runbook",
    ]
    common = {
        "evidence_fact_ids": fact_ids,
        "risk": "low",
        "requires_human_approval": False,
    }
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
                        "LedgerLens evidence-bounded incident record. Root cause, "
                        "user impact, and recovery remain unverified."
                    ),
                    "labels": ["incident", "ledgerlens"],
                },
                **common,
            },
            {
                "action_type": "slack.message.post",
                "target": "#inc-data-platform",
                "parameters": {
                    "channel": "#inc-data-platform",
                    "text": (
                        f"{incident.incident_id}: recorded DataHub incident context is "
                        "available. Root cause and recovery remain unverified."
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
                        "Verify a fresh DataHub assertion before resolving. Provider "
                        "receipts do not prove incident recovery."
                    ),
                    "issue_type": "Task",
                    "labels": ["incident", "ledgerlens"],
                },
                **common,
            },
        ],
        "forbiddenActions": [
            "delete_lineage",
            "disable_auditing",
            "drop_asset",
            "publish_unverified_fix",
            "production.rollback",
        ],
        "writeback": {
            "action": "datahub.incident.writeback",
            "performedAfterProviderReceipts": True,
        },
        "claimBoundary": {
            "candidateOnly": True,
            "canClaimAGI": False,
            "providerFamilyIndependenceClaimed": False,
        },
    }


def _with_policy(base: CatalogContextProvider, incident: Incident) -> IncidentContext:
    context = base(incident)
    metadata = dict(context.metadata)
    metadata["automationPolicy"] = _automation_policy(incident)
    return context.model_copy(update={"metadata": metadata})


def _disabled_executor(context: IncidentContext, action: Any) -> Any:
    del context, action
    raise RuntimeError("AI rehearsal never executes external actions")


def _disabled_writeback(result: Any) -> Any:
    del result
    raise RuntimeError("AI rehearsal never executes DataHub write-back")


def main() -> int:
    args = _arguments()
    if args.output.exists() and not args.force:
        print(f"refusing to overwrite existing receipt: {args.output}", file=sys.stderr)
        return 2
    if not os.getenv("SOPHIA_020S_KEY"):
        print("SOPHIA_020S_KEY is required", file=sys.stderr)
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
    roles = build_020s_ai_roles(settings)
    prepared = None
    exit_code = 0
    try:
        backend = OrchestratorIncidentBackend(
            incident_resolver=lambda payload: incident,
            context_provider=lambda value: _with_policy(provider, value),
            planner=roles.planner,
            verifier_panel=roles.verifier_panel,
            policy_gate=build_policy_gate(
                {
                    "github.issue.create": ["tomyimkc/ledgerlens"],
                    "slack.message.post": ["#inc-data-platform"],
                    "pagerduty.event.trigger": ["pagerduty:events-v2"],
                    "jira.issue.create": ["DATAOPS"],
                },
                minimum_plan_confidence=0.8,
                minimum_verifier_confidence=0.85,
                quorum=2,
            ),
            executor=_disabled_executor,
            writeback=_disabled_writeback,
        )
        try:
            state = backend.trigger({"incident_id": incident.incident_id})
            prepared = backend.prepared_run
            if prepared is None:
                raise RuntimeError("backend did not retain the prepared run")
            receipt: dict[str, Any] = {
                "schemaVersion": "1.0",
                "kind": "live-ai-verification-rehearsal",
                "status": ("authorized" if prepared.authorization.authorized else "blocked"),
                "networkUsed": True,
                "externalMutations": False,
                "models": {
                    "planner": settings.planner_model,
                    "verifiers": list(settings.verifier_model_ids),
                    "provider": settings.llm_base_url,
                    "providerFamilyIndependenceClaimed": False,
                },
                "incident": prepared.incident.model_dump(mode="json", by_alias=True),
                "contextDigest": (
                    "sha256:"
                    + hashlib.sha256(
                        json.dumps(
                            prepared.context.model_dump(mode="json", by_alias=True),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                ),
                "plan": prepared.plan.model_dump(mode="json", by_alias=True),
                "verification": prepared.verification.model_dump(mode="json", by_alias=True),
                "authorization": prepared.authorization.model_dump(mode="json", by_alias=True),
                "dashboardState": state,
                "limitations": [
                    "No GitHub, Slack, PagerDuty, Jira, or DataHub mutation was executed.",
                    (
                        "Distinct model variants were used; provider-family independence "
                        "is not claimed."
                    ),
                    (
                        "Authorization proves policy conformance, not incident causality "
                        "or recovery."
                    ),
                ],
                "candidateOnly": True,
                "canClaimAGI": False,
            }
            exit_code = 0 if prepared.authorization.authorized else 3
        except Exception as exc:
            receipt = {
                "schemaVersion": "1.0",
                "kind": "live-ai-verification-rehearsal",
                "status": "failed-closed",
                "networkUsed": True,
                "externalMutations": False,
                "models": {
                    "planner": settings.planner_model,
                    "verifiers": list(settings.verifier_model_ids),
                    "provider": settings.llm_base_url,
                    "providerFamilyIndependenceClaimed": False,
                },
                "incidentId": incident.incident_id,
                "error": f"{type(exc).__name__}: {exc}",
                "limitations": [
                    "The model or integration response did not satisfy the typed contract.",
                    "No external action or DataHub mutation was attempted.",
                ],
                "candidateOnly": True,
                "canClaimAGI": False,
            }
            exit_code = 3
    finally:
        roles.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary: dict[str, Any] = {
        "output": str(args.output),
        "status": receipt["status"],
        "candidateOnly": True,
        "canClaimAGI": False,
    }
    if prepared is not None:
        summary.update(
            {
                "planActions": len(prepared.plan.actions),
                "verificationApproved": prepared.verification.approved,
                "policyAuthorized": prepared.authorization.authorized,
            }
        )
    print(json.dumps(summary, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
