"""DataHub context ON/OFF ablation that exercises the REAL LedgerLens pipeline.

Unlike ``benchmark.py`` — whose two arms are hand-written scripted responders (the
context-ON arm copies the fixture's pre-labeled answer key; the context-OFF arm is a
fixed list) — this module runs the *production* classes end to end:

* a single ``DeterministicIncidentPlanner`` (implementing the real
  :class:`~ledgerlens.incident_models.IncidentPlanner` protocol),
* the real :class:`~ledgerlens.verification.VerifierPanel` with two independent
  deterministic verifier families, and
* the real :class:`~ledgerlens.verification.PolicyGate`, built by the same
  ``runtime_factory.build_policy_gate`` the application uses.

The **only** difference between the two arms is the :class:`IncidentContext` supplied:

* **context ON** carries the DataHub-shaped facts a real catalog read resolves —
  ``root-asset``, ``primary-owner``, ``blast-radius``, ``runbook`` — each grounded by a
  ``datahub_entity`` evidence pointer, mirroring
  :class:`~ledgerlens.datahub_context.DataHubMCPContextProvider`;
* **context OFF** carries only a single self-reported ``root-asset`` fact grounded by a
  ``log`` pointer — the alert envelope, and nothing the catalog would have added.

The planner proposes the *same* bounded response in both arms. The gate then authorizes
only the actions whose evidence is actually grounded in the supplied context. Because the
OFF arm lacks the owner/blast-radius/runbook facts, the real gate refuses the actions that
cite them — with its own reason codes, not a scripted branch.

What this measures: whether the deterministic policy gate authorizes only fact-grounded
actions when DataHub context is present, and correctly refuses them when it is absent.

What this does NOT measure: it says nothing about model or system *capability*. The
planner is a fixed, non-fabricating stub, so the OFF arm fails to ground actions by
construction — this exercises the fail-closed gate on a controlled input, it does not show
that "context makes the system smarter". The real, LLM-backed planner/verifier
(``ai_roles.JsonIncidentPlanner`` / ``JsonPlanVerifier``) are deliberately untouched here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlens.incident_models import (
    ActionPlan,
    ActionRisk,
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentStatus,
    IncidentTrigger,
    PlannedAction,
)
from ledgerlens.runtime_factory import build_policy_gate
from ledgerlens.verification import (
    PolicyGate,
    VerifierAssessment,
    VerifierPanel,
    VerifierPanelConfig,
)

JsonObject = dict[str, Any]

SCHEMA_VERSION = "ledgerlens.real-pipeline-ablation.v1"
MODE_ON = "datahub-context-on"
MODE_OFF = "datahub-context-off"

# Fixed collaboration surfaces — one per real action type. Targets are stable, not
# per-incident asset URNs, so a single shared PolicyGate authorizes every scenario.
GITHUB_TARGET = "tomyimkc/ledgerlens"
SLACK_TARGET = "#inc-data-platform"
PAGERDUTY_TARGET = "pagerduty:events-v2"
JIRA_TARGET = "DATAOPS"

POLICY_TARGETS: dict[str, tuple[str, ...]] = {
    "github.issue.create": (GITHUB_TARGET,),
    "slack.message.post": (SLACK_TARGET,),
    "pagerduty.event.trigger": (PAGERDUTY_TARGET,),
    "jira.issue.create": (JIRA_TARGET,),
}

_SEVERITY_MAP = {
    "SEV-1": IncidentSeverity.CRITICAL,
    "SEV-2": IncidentSeverity.HIGH,
    "SEV-3": IncidentSeverity.MEDIUM,
    "SEV-4": IncidentSeverity.LOW,
}


class RealPipelineAblationError(RuntimeError):
    """Raised when the fixture cannot satisfy the ablation contract."""


# --------------------------------------------------------------------------------------
# Context construction
# --------------------------------------------------------------------------------------


def _clock(catalog: Mapping[str, Any]) -> datetime:
    epoch = catalog["generator"]["fixtureEpochUtc"]
    return datetime.fromisoformat(epoch).astimezone(UTC)


def _incident(record: Mapping[str, Any], collected_at: datetime) -> Incident:
    severity = _SEVERITY_MAP.get(str(record["severity"]))
    if severity is None:
        raise RealPipelineAblationError(f"unknown severity {record['severity']!r}")
    incident_id = str(record["id"])
    root_urn = str(record["rootAssetUrn"])
    return Incident(
        incident_id=incident_id,
        title=str(record["title"]),
        severity=severity,
        status=IncidentStatus.TRIGGERED,
        detected_at=datetime.fromisoformat(str(record["detectedAtUtc"])).astimezone(UTC),
        trigger=IncidentTrigger(
            trigger_id=f"{incident_id}:trigger",
            source="datahub",
            kind=str(record["kind"]),
            occurred_at=collected_at,
            idempotency_key=f"{incident_id}:trigger",
        ),
        affected_entities=(root_urn,),
    )


def _datahub_fact(fact_id: str, statement: str, reference: str) -> IncidentFact:
    return IncidentFact(
        fact_id=fact_id,
        statement=statement,
        evidence=(EvidencePointer(reference=reference, kind=EvidenceKind.DATAHUB_ENTITY),),
    )


def _context_on(
    incident: Incident,
    record: Mapping[str, Any],
    owner_id: str,
    blast_radius: Sequence[str],
    collected_at: datetime,
) -> IncidentContext:
    """Full DataHub-shaped context, mirroring DataHubMCPContextProvider's fact vocabulary."""

    root_urn = str(record["rootAssetUrn"])
    runbook = f"https://runbooks.ledgerlens.example/{incident.incident_id}"
    facts = (
        _datahub_fact("root-asset", f"The triggering DataHub entity is {root_urn}.", root_urn),
        _datahub_fact(
            "primary-owner",
            f"The recorded primary owner is {owner_id}.",
            f"{root_urn}#ownership",
        ),
        _datahub_fact(
            "blast-radius",
            f"DataHub lineage records {len(blast_radius)} downstream entities.",
            f"{root_urn}#downstream-lineage",
        ),
        _datahub_fact(
            "runbook",
            f"The recorded runbook is {runbook}.",
            f"{root_urn}#runbook",
        ),
    )
    return IncidentContext(
        context_id=f"context-on:{incident.incident_id}",
        incident=incident.model_copy(update={"affected_entities": (root_urn, *blast_radius)}),
        collected_at=collected_at,
        facts=facts,
        metadata={
            "mode": MODE_ON,
            "source": "datahub-shaped-fixture",
            "owner": owner_id,
            "blastRadiusUrns": list(blast_radius),
            "claimBoundary": (
                "DataHub metadata and lineage do not establish causality or recovery."
            ),
        },
    )


def _context_off(
    incident: Incident,
    record: Mapping[str, Any],
    collected_at: datetime,
) -> IncidentContext:
    """Alert-envelope-only context: one self-reported fact, grounded by a log pointer.

    The absence of owner/blast-radius/runbook facts is the honest epistemic difference —
    without a catalog read the responder has the alert and nothing the catalog would add.
    """

    root_urn = str(record["rootAssetUrn"])
    facts = (
        IncidentFact(
            fact_id="root-asset",
            statement=f"The alert names root entity {root_urn} (self-reported, not confirmed).",
            evidence=(
                EvidencePointer(
                    reference=f"alert:{incident.incident_id}",
                    kind=EvidenceKind.LOG,
                ),
            ),
        ),
    )
    return IncidentContext(
        context_id=f"context-off:{incident.incident_id}",
        incident=incident,
        collected_at=collected_at,
        facts=facts,
        metadata={
            "mode": MODE_OFF,
            "source": "alert-envelope-only",
            "claimBoundary": "No catalog context was read; owner and blast radius are unknown.",
        },
    )


# --------------------------------------------------------------------------------------
# Real pipeline components (deterministic, offline, no API key)
# --------------------------------------------------------------------------------------


class DeterministicIncidentPlanner:
    """A fixed six-step response playbook using the four real action types.

    Implements the real ``IncidentPlanner`` protocol. It proposes the SAME plan in both
    arms; each action cites the fact IDs it semantically needs (a responder knows that
    notifying an owner requires knowing the owner). It never inspects which facts are
    present — the gate, not the planner, decides whether that evidence is grounded.
    """

    planner_id = "deterministic:playbook-v1"
    family = "deterministic-playbook"

    def plan(self, context: IncidentContext) -> ActionPlan:
        incident = context.incident
        incident_id = incident.incident_id
        steps = (
            (
                "page-oncall",
                "pagerduty.event.trigger",
                PAGERDUTY_TARGET,
                {
                    "summary": f"{incident_id}: {incident.title}",
                    "source": "ledgerlens",
                    "severity": "critical",
                },
                ("root-asset",),
                "Page the on-call responder for the triggering entity.",
            ),
            (
                "open-record",
                "github.issue.create",
                GITHUB_TARGET,
                {
                    "owner": "tomyimkc",
                    "repository": "ledgerlens",
                    "title": f"{incident_id}: {incident.title}",
                    "body": "Evidence-bounded incident record. Cause and recovery unverified.",
                },
                ("root-asset",),
                "Open a bounded incident record for the triggering entity.",
            ),
            (
                "notify-owner",
                "jira.issue.create",
                JIRA_TARGET,
                {
                    "project_key": "DATAOPS",
                    "summary": f"{incident_id}: notify accountable owner",
                    "description": "Route to the recorded accountable owner.",
                },
                ("primary-owner",),
                "Notify the accountable owner recorded in DataHub.",
            ),
            (
                "coordinate-blast-radius",
                "slack.message.post",
                SLACK_TARGET,
                {
                    "channel": SLACK_TARGET,
                    "text": f"{incident_id}: coordinating containment across downstream lineage.",
                },
                ("blast-radius",),
                "Coordinate containment across the downstream blast radius.",
            ),
            (
                "communicate-status",
                "slack.message.post",
                SLACK_TARGET,
                {
                    "channel": SLACK_TARGET,
                    "text": f"{incident_id}: incident acknowledged; cause and recovery unverified.",
                },
                ("root-asset",),
                "Communicate a bounded status update.",
            ),
            (
                "schedule-recovery-validation",
                "jira.issue.create",
                JIRA_TARGET,
                {
                    "project_key": "DATAOPS",
                    "summary": f"{incident_id}: validate recovery against runbook",
                    "description": "Verify a fresh DataHub assertion before resolving.",
                },
                ("runbook",),
                "Schedule recovery validation against the recorded runbook.",
            ),
        )
        actions = tuple(
            PlannedAction(
                action_id=action_id,
                action_type=action_type,
                target=target,
                parameters=parameters,
                rationale=rationale,
                evidence_fact_ids=evidence_fact_ids,
                idempotency_key=f"{incident_id}:{action_id}",
                risk=ActionRisk.LOW,
            )
            for action_id, action_type, target, parameters, evidence_fact_ids, rationale in steps
        )
        return ActionPlan(
            plan_id=f"{incident_id}:plan",
            incident_id=incident_id,
            planner_id=self.planner_id,
            planner_family=self.family,
            created_at=context.collected_at,
            confidence=0.9,
            summary="Bounded six-step incident response using collaboration adapters only.",
            actions=actions,
        )


class GroundingLintVerifier:
    """Context-sensitive lens: every action's cited evidence must exist in the context."""

    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    def verify(self, context: IncidentContext, plan: ActionPlan) -> VerifierAssessment:
        fact_ids = context.fact_ids
        ungrounded: list[str] = []
        for action in plan.actions:
            for fact_id in action.evidence_fact_ids:
                if fact_id not in fact_ids and fact_id not in ungrounded:
                    ungrounded.append(fact_id)
        if ungrounded:
            return VerifierAssessment(
                approved=False,
                confidence=0.99,
                reasons=("actions cite evidence absent from the supplied context",),
                unverifiable_fact_ids=tuple(ungrounded),
            )
        return VerifierAssessment(
            approved=True,
            confidence=0.95,
            reasons=("every cited fact is grounded in the supplied context",),
        )


class PolicyShapeVerifier:
    """Context-independent lens: the plan is well-formed against the known action types."""

    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    @staticmethod
    def _is_well_formed(action: PlannedAction) -> bool:
        allowed_targets = POLICY_TARGETS.get(action.action_type)
        return (
            allowed_targets is not None
            and action.target in allowed_targets
            and action.risk in {ActionRisk.LOW, ActionRisk.MEDIUM}
        )

    def verify(self, context: IncidentContext, plan: ActionPlan) -> VerifierAssessment:
        del context
        bad_shape = [
            action.action_id for action in plan.actions if not self._is_well_formed(action)
        ]
        if bad_shape:
            return VerifierAssessment(
                approved=False,
                confidence=0.99,
                reasons=("plan contains malformed or out-of-scope actions",),
                unverifiable_action_ids=tuple(bad_shape),
            )
        return VerifierAssessment(
            approved=True,
            confidence=0.95,
            reasons=("every action is well-formed against the known collaboration types",),
        )


def _build_panel() -> VerifierPanel:
    return VerifierPanel(
        (
            GroundingLintVerifier("deterministic:grounding-lint", "grounding-lint"),
            PolicyShapeVerifier("deterministic:policy-shape", "policy-shape"),
        ),
        config=VerifierPanelConfig(
            quorum=2,
            minimum_families=2,
            confidence_threshold=0.85,
            require_planner_independence=True,
            fail_on_verifier_error=True,
        ),
    )


def _build_gate(clock: datetime) -> PolicyGate:
    # Reuse the production allowlist/threshold config verbatim, then bind a fixed clock so
    # the receipt is byte-reproducible.
    base = build_policy_gate(
        POLICY_TARGETS,
        maximum_risk=ActionRisk.MEDIUM,
        minimum_plan_confidence=0.8,
        minimum_verifier_confidence=0.85,
        quorum=2,
    )
    return PolicyGate(base.config, clock=lambda: clock)


# --------------------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------------------


def _jaccard(predicted: frozenset[str], expected: frozenset[str]) -> float:
    if not predicted and not expected:
        return 1.0
    union = predicted | expected
    if not union:
        return 1.0
    return len(predicted & expected) / len(union)


def _recall(predicted: frozenset[str], expected: frozenset[str]) -> float:
    if not expected:
        return 1.0
    return len(predicted & expected) / len(expected)


def _evaluate_arm(
    catalog: Mapping[str, Any],
    *,
    mode: str,
) -> JsonObject:
    clock = _clock(catalog)
    planner = DeterministicIncidentPlanner()
    panel = _build_panel()
    gate = _build_gate(clock)

    incidents_by_id = {str(rec["id"]): rec for rec in catalog["incidents"]}
    scenario_results: list[JsonObject] = []
    reason_counter: dict[str, int] = {}
    authorized_scenarios = 0
    verifier_approved_scenarios = 0
    grounded_actions = 0
    total_actions = 0
    owner_accuracy_sum = 0.0
    blast_recall_sum = 0.0

    for scenario in catalog["scenarios"]:
        record = incidents_by_id[str(scenario["incidentId"])]
        expected = scenario["expected"]
        owner_id = str(expected["ownerIds"][0])
        blast_radius = tuple(str(urn) for urn in expected["blastRadiusUrns"])

        incident = _incident(record, clock)
        if mode == MODE_ON:
            context = _context_on(incident, record, owner_id, blast_radius, clock)
            predicted_owner: frozenset[str] = frozenset({owner_id})
            predicted_blast: frozenset[str] = frozenset(blast_radius)
        else:
            context = _context_off(incident, record, clock)
            predicted_owner = frozenset()
            predicted_blast = frozenset()

        plan = planner.plan(context)
        verification = panel.verify(context, plan)
        decision = gate.authorize(context, plan, verification)

        total_actions += len(plan.actions)
        grounded_actions += sum(
            1 for action in plan.actions if frozenset(action.evidence_fact_ids) <= context.fact_ids
        )
        if decision.authorized:
            authorized_scenarios += 1
        if verification.approved:
            verifier_approved_scenarios += 1
        for code in decision.reason_codes:
            # Collapse per-action suffixes (e.g. "action_references_unknown_fact:notify-owner")
            key = code.split(":", 1)[0]
            reason_counter[key] = reason_counter.get(key, 0) + 1

        owner_accuracy_sum += _jaccard(predicted_owner, frozenset({owner_id}))
        blast_recall_sum += _recall(predicted_blast, frozenset(blast_radius))

        scenario_results.append(
            {
                "scenarioId": str(scenario["id"]),
                "incidentId": incident.incident_id,
                "authorized": decision.authorized,
                "verifierApproved": verification.approved,
                "reasonCodes": list(decision.reason_codes),
                "actionCount": len(plan.actions),
                "groundedActionCount": sum(
                    1
                    for action in plan.actions
                    if frozenset(action.evidence_fact_ids) <= context.fact_ids
                ),
            }
        )

    n = len(catalog["scenarios"])
    return {
        "mode": mode,
        "scenarioCount": n,
        "metrics": {
            "planAuthorizationRate": authorized_scenarios / n,
            "verifierApprovalRate": verifier_approved_scenarios / n,
            "actionGroundingRate": grounded_actions / total_actions if total_actions else 0.0,
            "ownerAccuracy": owner_accuracy_sum / n,
            "blastRadiusRecall": blast_recall_sum / n,
        },
        "blockReasonDistribution": dict(sorted(reason_counter.items())),
        "scenarios": scenario_results,
    }


def build_ablation_receipt(catalog: Mapping[str, Any]) -> JsonObject:
    """Run both arms through the real pipeline and return a deterministic receipt."""

    on = _evaluate_arm(catalog, mode=MODE_ON)
    off = _evaluate_arm(catalog, mode=MODE_OFF)

    on_auth = on["metrics"]["planAuthorizationRate"]
    off_auth = off["metrics"]["planAuthorizationRate"]
    # PASS means the real gate authorized the grounded arm and refused the ungrounded arm.
    status = "PASS" if on_auth == 1.0 and off_auth == 0.0 else "FAIL"

    receipt: JsonObject = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "real-pipeline-context-ablation",
        "status": status,
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "catalog": {
            "seed": catalog["generator"]["seed"],
            "assetCount": len(catalog["assets"]),
            "scenarioCount": len(catalog["scenarios"]),
        },
        "pipeline": {
            "planner": f"{DeterministicIncidentPlanner.family} (deterministic, no LLM)",
            "verifierFamilies": ["grounding-lint", "policy-shape"],
            "policyGate": "ledgerlens.runtime_factory.build_policy_gate (production class)",
            "quorum": 2,
        },
        "arms": {MODE_ON: on, MODE_OFF: off},
        "whatThisMeasures": (
            "Whether the real deterministic PolicyGate authorizes only fact-grounded actions "
            "when DataHub context is present, and refuses them when it is absent. Both arms run "
            "the identical planner and the identical production VerifierPanel + PolicyGate; the "
            "only difference is the IncidentContext supplied."
        ),
        "limitations": [
            "The planner is a fixed, non-fabricating deterministic stub — the OFF arm fails to "
            "ground actions by construction. This exercises the fail-closed gate on a controlled "
            "input; it does NOT measure model or system capability or 'uplift'.",
            "The real LLM-backed JsonIncidentPlanner/JsonPlanVerifier are not exercised here.",
            "ownerAccuracy and blastRadiusRecall measure what the context contained, not planner "
            "skill: the ON context is populated from the fixture's own ground truth.",
            "Synthetic fixture only; no live DataHub, provider, or production incident.",
        ],
    }
    receipt["contentDigest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    return receipt


def write_receipt_atomic(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


__all__ = [
    "MODE_OFF",
    "MODE_ON",
    "SCHEMA_VERSION",
    "DeterministicIncidentPlanner",
    "GroundingLintVerifier",
    "PolicyShapeVerifier",
    "RealPipelineAblationError",
    "build_ablation_receipt",
    "write_receipt_atomic",
]
