#!/usr/bin/env python3
"""Run planner (sol) + verifiers (terra, …) via 020s and write a public agent I/O trace.

Captures system prompts, user prompts, tool catalog context, model JSON outputs, and
the deterministic policy decision — without external mutations and without API keys.

Usage:
  export LEDGERLENS_LLM_API_KEY=…   # or SOPHIA_020S_KEY
  # optional: LEDGERLENS_LLM_BASE_URL=https://api.020s.com/v1
  # optional: LEDGERLENS_PLANNER_MODEL=gpt-5.6-sol
  # optional: LEDGERLENS_VERIFIER_MODELS=gpt-5.6-terra,gpt-5.5
  uv run python scripts/run_agent_io_trace.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
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
DEFAULT_OUTPUT = Path("src/ledgerlens/static/agent-io-trace.json")
DEFAULT_BENCH = Path("benchmarks/incident_commander/agent-io-trace.json")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", default=DEFAULT_INCIDENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--also-benchmark",
        type=Path,
        default=DEFAULT_BENCH,
        help="Optional second copy under benchmarks/ (empty path to skip).",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=12000,
        help="Truncate large context JSON in the published trace for readability.",
    )
    return parser.parse_args()


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


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
                    "summary": f"{incident.incident_id}: recover freshness",
                    "description": "Track recovery verification separately from root cause.",
                    "issue_type": "Task",
                    "labels": ["incident", "ledgerlens"],
                },
                **common,
            },
        ]
    }


def _with_policy(
    provider: CatalogContextProvider,
    incident: Incident,
) -> IncidentContext:
    context = provider(incident)
    metadata = dict(context.metadata)
    metadata["automationPolicy"] = _automation_policy(incident)
    return context.model_copy(update={"metadata": metadata})


def _disabled_executor(context: IncidentContext, action: Any) -> dict[str, Any]:
    del context, action
    raise RuntimeError("agent I/O trace never executes provider tools")


def _disabled_writeback(result: Any) -> dict[str, Any]:
    del result
    raise RuntimeError("agent I/O trace never executes DataHub write-back")


def _truncate(value: Any, max_chars: int) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return value if not isinstance(value, str) else text
    if isinstance(value, str):
        return text[: max_chars - 20] + "…[truncated]"
    return {
        "_truncated": True,
        "chars": len(text),
        "preview": text[: max_chars - 40] + "…",
    }


def _sanitize_records(
    records: list[dict[str, Any]],
    *,
    max_context_chars: int,
) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for index, raw in enumerate(records, start=1):
        inp = dict(raw.get("input") or {})
        context = inp.get("context")
        # Prefer showing tool catalog + slim incident fields for the demo page.
        slim_context = context
        if isinstance(context, dict):
            slim_context = {
                "hasAgentToolCatalog": "agentToolCatalog" in context,
                "agentToolCatalog": context.get("agentToolCatalog"),
                "incidentContextSummary": _summarize_incident_context(
                    context.get("incidentContext") or context
                ),
                "candidatePlanSummary": _summarize_plan(context.get("candidatePlan")),
            }
        clean.append(
            {
                "step": index,
                "role": raw.get("role"),
                "model": raw.get("model"),
                "provider": raw.get("provider"),
                "temperature": raw.get("temperature"),
                "input": {
                    "system": inp.get("system"),
                    "userPrompt": inp.get("userPrompt"),
                    "context": _truncate(slim_context, max_context_chars),
                },
                "output": raw.get("output"),
                "error": raw.get("error"),
            }
        )
    return clean


def _summarize_incident_context(ctx: Any) -> dict[str, Any] | None:
    if not isinstance(ctx, dict):
        return None
    incident = ctx.get("incident") or {}
    facts = ctx.get("facts") or []
    return {
        "incidentId": incident.get("incidentId") or incident.get("incident_id"),
        "title": incident.get("title"),
        "severity": incident.get("severity"),
        "factCount": len(facts) if isinstance(facts, list) else 0,
        "factIds": [
            f.get("factId") or f.get("fact_id")
            for f in (facts if isinstance(facts, list) else [])
            if isinstance(f, dict)
        ][:12],
    }


def _summarize_plan(plan: Any) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    actions = plan.get("actions") or []
    return {
        "planId": plan.get("planId") or plan.get("plan_id"),
        "summary": plan.get("summary"),
        "confidence": plan.get("confidence"),
        "actions": [
            {
                "actionType": a.get("actionType") or a.get("action_type"),
                "target": a.get("target"),
            }
            for a in actions
            if isinstance(a, dict)
        ],
    }


def main() -> int:
    _load_dotenv()
    args = _arguments()
    if args.output.exists() and not args.force:
        print(f"refusing to overwrite existing trace: {args.output}", file=sys.stderr)
        return 2

    llm_key = os.getenv("LEDGERLENS_LLM_API_KEY") or os.getenv("SOPHIA_020S_KEY")
    if not llm_key:
        print("LEDGERLENS_LLM_API_KEY or SOPHIA_020S_KEY is required", file=sys.stderr)
        return 2

    catalog = load_incident_catalog()
    incident = incident_from_catalog(catalog, args.incident_id)
    provider = CatalogContextProvider(catalog)
    settings = Settings.model_validate(
        {
            "ai_verification_enabled": True,
            "llm_api_key": llm_key,
            "llm_base_url": os.getenv("LEDGERLENS_LLM_BASE_URL", "https://api.020s.com/v1"),
            "llm_model": os.getenv("LEDGERLENS_LLM_MODEL", "gpt-5.6-sol"),
            "planner_model": os.getenv("LEDGERLENS_PLANNER_MODEL", "gpt-5.6-sol"),
            "verifier_models": os.getenv(
                "LEDGERLENS_VERIFIER_MODELS",
                "gpt-5.6-terra,gpt-5.5",
            ),
            "verifier_quorum": 2,
            "verifier_min_confidence": 0.85,
            "llm_timeout_seconds": float(os.getenv("LEDGERLENS_LLM_TIMEOUT_SECONDS", "90")),
        }
    )
    action_targets = {
        "github.issue.create": ["tomyimkc/ledgerlens"],
        "slack.message.post": ["#inc-data-platform"],
        "pagerduty.event.trigger": ["pagerduty:events-v2"],
        "jira.issue.create": ["DATAOPS"],
    }
    llm_records: list[dict[str, Any]] = []
    roles = build_020s_ai_roles(
        settings,
        action_targets=action_targets,
        record_llm_io=True,
        llm_io_records=llm_records,
    )
    prepared = None
    error: str | None = None
    try:
        backend = OrchestratorIncidentBackend(
            incident_resolver=lambda payload: incident,
            context_provider=lambda value: _with_policy(provider, value),
            planner=roles.planner,
            verifier_panel=roles.verifier_panel,
            policy_gate=build_policy_gate(
                action_targets,
                minimum_plan_confidence=0.8,
                minimum_verifier_confidence=0.85,
                quorum=2,
            ),
            executor=_disabled_executor,
            writeback=_disabled_writeback,
        )
        backend.trigger({"incident_id": incident.incident_id})
        prepared = backend.prepared_run
        if prepared is None:
            raise RuntimeError("backend did not retain the prepared run")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        roles.close()

    flow = [
        {
            "id": "sense",
            "label": "Sense",
            "detail": "Catalog/DataHub context (facts, owners, blast radius)",
            "actor": "tools",
        },
        {
            "id": "plan",
            "label": "Plan tools",
            "detail": f"LLM planner ({settings.planner_model}) proposes allowlisted tool calls",
            "actor": "llm",
            "model": settings.planner_model,
        },
        {
            "id": "critique",
            "label": "Critique",
            "detail": f"Verifier models ({', '.join(settings.verifier_model_ids)}) review the plan",
            "actor": "llm",
            "models": list(settings.verifier_model_ids),
        },
        {
            "id": "gate",
            "label": "Gate",
            "detail": "Deterministic policy: allowlist + quorum + confidence (not the model)",
            "actor": "policy",
        },
        {
            "id": "hold",
            "label": "Hold tools",
            "detail": "This trace does not execute GitHub/Slack/PD/Jira or DataHub mutations",
            "actor": "safety",
        },
    ]

    authorized = bool(prepared and prepared.authorization.authorized)
    trace: dict[str, Any] = {
        "schemaVersion": "1.0",
        "kind": "agent-io-trace",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": (
            "authorized"
            if authorized
            else ("failed-closed" if error else "blocked")
        ),
        "networkUsed": True,
        "externalMutations": False,
        "models": {
            "planner": settings.planner_model,
            "verifiers": list(settings.verifier_model_ids),
            "provider": settings.llm_base_url,
        },
        "incidentId": incident.incident_id,
        "flow": flow,
        "llmCalls": _sanitize_records(llm_records, max_context_chars=args.max_context_chars),
        "agentPlan": (
            prepared.plan.model_dump(mode="json", by_alias=True) if prepared else None
        ),
        "verification": (
            prepared.verification.model_dump(mode="json", by_alias=True) if prepared else None
        ),
        "authorization": (
            prepared.authorization.model_dump(mode="json", by_alias=True) if prepared else None
        ),
        "error": error,
        "howToRead": [
            "llmCalls[].input.system — agent instructions",
            "llmCalls[].input.userPrompt — task instructions",
            "llmCalls[].input.context — tool catalog + incident facts (or plan under review)",
            "llmCalls[].output.json — structured model response (plan or verdict)",
            "authorization — deterministic gate result after models finish",
        ],
        "limitations": [
            "No provider or DataHub mutation was executed in this trace.",
            "Distinct model IDs do not establish provider-family independence.",
            "Published context may be truncated for demo readability.",
            "API keys are never stored in this file.",
        ],
        "candidateOnly": True,
        "canClaimAGI": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(trace, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.output.write_text(text, encoding="utf-8")
    if args.also_benchmark and str(args.also_benchmark).strip():
        args.also_benchmark.parent.mkdir(parents=True, exist_ok=True)
        args.also_benchmark.write_text(text, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": trace["status"],
                "llmCalls": len(trace["llmCalls"]),
                "authorized": authorized,
                "error": error,
                "candidateOnly": True,
            },
            sort_keys=True,
        )
    )
    return 0 if authorized else 3


if __name__ == "__main__":
    raise SystemExit(main())
