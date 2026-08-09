#!/usr/bin/env python3
"""Build a controlled DataHub context ablation from the recorded Agent I/O plan.

The source plan and verifier panel come from ``agent-io-trace.json``, which records
real model API calls. This script does *not* call those models again. It keeps that
exact plan fixed, removes one DataHub fact at a time, and runs the current
deterministic PolicyGate over each typed counterfactual.

That separation is deliberate:

* recorded model evidence: the source plan and verifier outputs;
* deterministic fixture transformation: the context cuts;
* current executable evidence: PolicyGate authorization or refusal;
* unavailable evidence: how the planner would re-plan under each cut.

No provider adapter or DataHub write-back executes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ledgerlens.catalog_runtime import (
    CatalogContextProvider,
    incident_from_catalog,
    load_incident_catalog,
)
from ledgerlens.incident_models import ActionPlan, IncidentContext
from ledgerlens.runtime_factory import build_policy_gate
from ledgerlens.tool_catalog import DATAHUB_INCIDENT_EVIDENCE_CONTRACTS
from ledgerlens.verification import VerificationPanelResult

DEFAULT_INCIDENT = "inc-analytics-downstream_availability-01"
DEFAULT_SOURCE = Path("src/ledgerlens/static/agent-io-trace.json")
DEFAULT_OUTPUT = Path("src/ledgerlens/static/context-cut-trace.json")
DEFAULT_BENCH = Path("benchmarks/incident_commander/context-cut-agent-trace.json")

SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "full-map",
        "label": "Full DataHub map",
        "question": "Does the recorded plan pass when all cited catalog facts exist?",
        "remove": (),
    },
    {
        "id": "owner-cut",
        "label": "Ownership removed",
        "question": "Does the same plan remain executable when DataHub has no recorded owner?",
        "remove": ("primary-owner",),
    },
    {
        "id": "lineage-cut",
        "label": "Lineage removed",
        "question": "Does the same plan remain executable when blast radius is unknown?",
        "remove": ("blast-radius",),
    },
    {
        "id": "alert-only",
        "label": "Alert facts only",
        "question": "Can the same plan run with only incident ID and severity facts?",
        "keep": ("incident-id", "incident-severity"),
    },
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", default=DEFAULT_INCIDENT)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--also-benchmark", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _variant(context: IncidentContext, scenario: dict[str, Any]) -> IncidentContext:
    remove = frozenset(str(item) for item in scenario.get("remove", ()))
    keep_raw: Sequence[str] | None = scenario.get("keep")
    keep = frozenset(str(item) for item in keep_raw) if keep_raw else None
    facts = tuple(
        fact
        for fact in context.facts
        if fact.fact_id not in remove and (keep is None or fact.fact_id in keep)
    )
    metadata: dict[str, Any] = dict(context.metadata)
    present_ids = {fact.fact_id for fact in facts}
    if "primary-owner" not in present_ids:
        metadata.pop("owner", None)
    if "blast-radius" not in present_ids:
        metadata.pop("blastRadiusUrns", None)
    if "runbook" not in present_ids:
        root = metadata.get("rootAsset")
        if isinstance(root, dict):
            clean_root = dict(root)
            clean_root.pop("documentation", None)
            metadata["rootAsset"] = clean_root
    metadata.pop("automationPolicy", None)
    metadata["contextCut"] = {
        "scenario": scenario["id"],
        "removedFactIds": sorted(context.fact_ids - {fact.fact_id for fact in facts}),
        "plannerReRun": False,
        "note": "Synthetic counterfactual; no live DataHub request occurred.",
    }
    return context.model_copy(
        update={
            "context_id": f"{context.context_id}-{scenario['id']}",
            "facts": facts,
            "metadata": metadata,
        }
    )


def _action_targets(plan: ActionPlan) -> dict[str, list[str]]:
    targets: dict[str, set[str]] = {}
    for action in plan.actions:
        targets.setdefault(action.action_type, set()).add(action.target)
    return {key: sorted(value) for key, value in sorted(targets.items())}


def _load_source(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("agent I/O trace must be a JSON object")
    if raw.get("candidateOnly") is not True or raw.get("canClaimAGI") is not False:
        raise ValueError("agent I/O trace claim boundary is invalid")
    if not raw.get("agentPlan") or not raw.get("verification"):
        raise ValueError("agent I/O trace does not contain a plan and verification")
    return raw


def _source_generated_at(source: dict[str, Any]) -> datetime:
    raw = source.get("generatedAt")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("agent I/O trace must contain a generatedAt timestamp")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("agent I/O generatedAt timestamp must include a timezone")
    return parsed


def main() -> int:
    args = _arguments()
    if args.output.exists() and not args.force:
        print(f"refusing to overwrite existing trace: {args.output}", file=sys.stderr)
        return 2

    source = _load_source(args.source)
    source_generated_at = _source_generated_at(source)
    plan = ActionPlan.model_validate(source["agentPlan"])
    verification = VerificationPanelResult.model_validate(source["verification"])
    catalog = load_incident_catalog()
    incident = incident_from_catalog(catalog, args.incident_id)
    if plan.incident_id != incident.incident_id:
        raise ValueError("source plan incident does not match requested context")
    base_context = CatalogContextProvider(catalog)(incident)
    targets = _action_targets(plan)
    unknown_types = sorted(set(targets) - set(DATAHUB_INCIDENT_EVIDENCE_CONTRACTS))
    if unknown_types:
        raise ValueError(
            "source plan contains action types without DataHub evidence contracts: "
            + ", ".join(unknown_types)
        )
    contracts = {key: DATAHUB_INCIDENT_EVIDENCE_CONTRACTS[key] for key in targets}
    gate = build_policy_gate(
        targets,
        required_evidence_fact_ids=contracts,
        minimum_plan_confidence=0.8,
        minimum_verifier_confidence=0.85,
        quorum=2,
    )

    scenarios: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        context = _variant(base_context, scenario)
        authorization = gate.authorize(context, plan, verification).model_copy(
            update={"evaluated_at": source_generated_at}
        )
        scenarios.append(
            {
                "id": scenario["id"],
                "label": scenario["label"],
                "question": scenario["question"],
                "removedFactIds": sorted(base_context.fact_ids - context.fact_ids),
                "context": context.model_dump(mode="json", by_alias=True),
                "plan": plan.model_dump(mode="json", by_alias=True),
                "verification": verification.model_dump(mode="json", by_alias=True),
                "recordedAuthorization": authorization.model_dump(mode="json", by_alias=True),
                "selectedActionTypes": [action.action_type for action in plan.actions],
                "plannerReRunForScenario": False,
                "error": None,
            }
        )

    trace = {
        "schemaVersion": "ledgerlens.context-cut.v1",
        "kind": "datahub-context-cut-agent-trace",
        "generatedAt": source["generatedAt"],
        "status": "recorded",
        "evidenceClass": "recorded-model-plan-controlled-context-ablation",
        "sourceAgentIoTrace": str(args.source),
        "sourceAgentIoGeneratedAt": source.get("generatedAt"),
        "sourceModelNetworkUsed": source.get("networkUsed") is True,
        "buildNetworkUsed": False,
        "externalMutations": False,
        "models": {
            **dict(source.get("models") or {}),
            "providerFamilyIndependenceClaimed": False,
        },
        "actionTargets": targets,
        "requiredEvidenceFactIds": {key: list(value) for key, value in contracts.items()},
        "scenarios": scenarios,
        "limitations": [
            "The source plan and verifier outputs are a recorded model trace, not live calls.",
            "The exact same source plan is held fixed; the planner is not re-run per cut.",
            "The DataHub-shaped contexts and context removals are synthetic fixtures.",
            "The public endpoint re-runs only deterministic policy and executes no tools.",
            "Distinct model IDs do not establish provider-family independence.",
            "This controlled ablation is not validated uplift, reliability, or incident recovery.",
        ],
        "candidateOnly": True,
        "canClaimAGI": False,
    }
    text = json.dumps(trace, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    if args.also_benchmark and str(args.also_benchmark).strip():
        args.also_benchmark.parent.mkdir(parents=True, exist_ok=True)
        args.also_benchmark.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": trace["status"],
                "scenarios": len(scenarios),
                "sourceModelNetworkUsed": trace["sourceModelNetworkUsed"],
                "buildNetworkUsed": False,
                "externalMutations": False,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
