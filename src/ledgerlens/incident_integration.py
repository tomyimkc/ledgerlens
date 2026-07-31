"""Production integration between the incident core, provider adapters, and dashboard.

The dashboard deliberately owns only presentation and an operator/autonomous grant.
This module owns the real preparation and execution path:

``Incident -> Context -> Planner -> VerifierPanel -> PolicyGate``

Preparation is side-effect free.  Only :meth:`OrchestratorIncidentBackend.execute`
constructs :class:`~ledgerlens.orchestrator.IncidentOrchestrator`, which executes
the frozen, verified plan and records the write-back receipt.  Freezing the prepared
objects prevents a second model call from changing a plan after the dashboard has
authorized its fingerprint.
"""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ledgerlens.actions import (
    ActionAdapter,
    ActionAuthorizer,
    GitHubIssueAction,
    JiraIssueAction,
    PagerDutyEventAction,
    SlackMessageAction,
)
from ledgerlens.datahub_writeback import (
    DataHubWritebackService,
    IncidentStatusContext,
    WritebackRequest,
    WritebackStatus,
)
from ledgerlens.datahub_writeback import (
    IncidentStatus as WritebackIncidentStatus,
)
from ledgerlens.incident_dashboard import plan_fingerprint
from ledgerlens.incident_models import (
    ActionPlan,
    ActionReceipt,
    ActionRisk,
    Incident,
    IncidentContext,
    IncidentPlanner,
    PlannedAction,
)
from ledgerlens.orchestrator import (
    ActionExecutor,
    ExecutionOutcome,
    IncidentOrchestrator,
    OrchestrationResult,
    OrchestrationState,
    WritebackCallback,
    WritebackOutcome,
)
from ledgerlens.verification import (
    AuthorizationDecision,
    PolicyGate,
    VerificationPanelResult,
    VerifierPanel,
)

JsonObject = dict[str, Any]

_ACTION_PROVIDERS = {
    "github.issue.create": ("GitHub", "GH", "Create incident issue"),
    "slack.message.post": ("Slack", "SL", "Post incident brief"),
    "pagerduty.event.trigger": ("PagerDuty", "PD", "Trigger incident event"),
    "jira.issue.create": ("Jira", "JR", "Create recovery task"),
}


class IncidentIntegrationError(RuntimeError):
    """Raised when prepared or live integration state fails closed."""


class UnsupportedPlannedAction(IncidentIntegrationError):
    """Raised when no typed provider adapter exists for a planned action."""


@dataclass(frozen=True)
class PreparedIncidentRun:
    """Immutable, side-effect-free result of the planning and policy stages."""

    incident: Incident
    context: IncidentContext
    plan: ActionPlan
    verification: VerificationPanelResult
    authorization: AuthorizationDecision


class ActionRegistryExecutor:
    """Convert verified planned actions into signed, typed provider calls."""

    def __init__(
        self,
        adapters: Mapping[str, ActionAdapter[Any]],
        *,
        authorizer: ActionAuthorizer,
        subject: str = "autonomous-data-incident-commander",
    ) -> None:
        self.adapters = dict(adapters)
        self.authorizer = authorizer
        self.subject = subject

    def __call__(
        self,
        context: IncidentContext,
        action: PlannedAction,
    ) -> ExecutionOutcome:
        del context
        adapter = self.adapters.get(action.action_type)
        if adapter is None:
            raise UnsupportedPlannedAction(
                f"no provider adapter is configured for {action.action_type}"
            )
        provider_action = _provider_action(action)
        preview = adapter.preview(provider_action)
        authorization = self.authorizer.issue(
            preview,
            subject=self.subject,
            authorization_id=f"action-grant:{action.action_id}",
        )
        receipt = adapter.execute(provider_action, authorization)
        references = tuple(
            value
            for value in (
                receipt.remote_url,
                f"{receipt.adapter}://receipt/{receipt.receipt_id}",
            )
            if value
        )
        return ExecutionOutcome(
            succeeded=True,
            executor=f"{receipt.adapter}:{receipt.operation}",
            message=f"{receipt.adapter} accepted the bounded action",
            output_references=references,
            details={
                "actionType": action.action_type,
                "providerReceipt": receipt.model_dump(mode="json"),
            },
        )


class DataHubIncidentWriteback:
    """Record a receipt-bearing incident document through controlled MCP mutation."""

    def __init__(
        self,
        service: DataHubWritebackService,
        *,
        actor: str = "ledgerlens-autonomous-incident-commander",
        document_type: str = "Context",
        document_urn_factory: Callable[[OrchestrationResult], str | None] | None = None,
    ) -> None:
        self.service = service
        self.actor = actor
        self.document_type = document_type
        self.document_urn_factory = document_urn_factory or (lambda result: None)

    def __call__(self, result: OrchestrationResult) -> WritebackOutcome:
        if result.context is None or result.plan is None or result.authorization is None:
            return WritebackOutcome(
                succeeded=False,
                message="orchestration result is missing context, plan, or authorization",
            )
        related_assets = list(result.context.incident.affected_entities[:1])
        content = json.dumps(
            {
                "schemaVersion": "1.0",
                "run": result.model_dump(mode="json", by_alias=True),
                "claimBoundary": {
                    "candidateOnly": True,
                    "canClaimAGI": False,
                    "note": (
                        "Receipts prove bounded tool acceptance, not incident causality "
                        "or recovery."
                    ),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        request = WritebackRequest.save_document(
            document_type=self.document_type,
            title=f"LedgerLens incident command receipt: {result.incident_id}",
            content=content,
            idempotency_key=f"incident-writeback:{result.run_id}",
            urn=self.document_urn_factory(result),
            topics=("incident-response", "ledgerlens"),
            related_assets=related_assets or None,
        )
        authorization = self.service.policy.authorize(
            request,
            actor=self.actor,
            reason="Record the authorized incident plan and provider action receipts.",
            incident_context=IncidentStatusContext(
                incident_id=result.incident_id,
                status=WritebackIncidentStatus.INVESTIGATING,
                summary=result.plan.summary,
                source="ledgerlens",
            ),
        )
        receipt = self.service.execute(request, authorization=authorization)
        return WritebackOutcome(
            succeeded=receipt.status is WritebackStatus.APPLIED,
            message="DataHub incident command receipt recorded",
            reference=_writeback_reference(receipt.to_dict()),
            details={"writebackReceipt": receipt.to_dict()},
        )


class OrchestratorIncidentBackend:
    """Stateful live backend that freezes model output before executing actions."""

    mode = "live"

    def __init__(
        self,
        *,
        incident_resolver: Callable[[Mapping[str, Any]], Incident],
        context_provider: Callable[[Incident], IncidentContext],
        planner: IncidentPlanner,
        verifier_panel: VerifierPanel,
        policy_gate: PolicyGate,
        executor: ActionExecutor,
        writeback: WritebackCallback,
        clock: Callable[[], datetime] | None = None,
        mode: str = "live",
    ) -> None:
        self.incident_resolver = incident_resolver
        self.context_provider = context_provider
        self.planner = planner
        self.verifier_panel = verifier_panel
        self.policy_gate = policy_gate
        self.executor = executor
        self.writeback = writeback
        self._clock = clock or (lambda: datetime.now(UTC))
        self.mode = mode
        self._prepared: PreparedIncidentRun | None = None
        self._result: OrchestrationResult | None = None
        self._state = _empty_state(mode)
        self._run_cache: dict[str, OrchestrationResult] = {}
        self._receipt_cache: dict[str, ActionReceipt] = {}
        self._lock = threading.RLock()

    def snapshot(self) -> Mapping[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    @property
    def prepared_run(self) -> PreparedIncidentRun | None:
        """Return the immutable prepared run for audit/receipt generation."""

        with self._lock:
            return self._prepared

    @property
    def orchestration_result(self) -> OrchestrationResult | None:
        """Return the latest immutable orchestration result, if execution occurred."""

        with self._lock:
            return self._result

    def trigger(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            try:
                incident = Incident.model_validate(self.incident_resolver(payload))
                if (
                    self._prepared is not None
                    and self._prepared.incident.trigger.idempotency_key
                    == incident.trigger.idempotency_key
                ):
                    return copy.deepcopy(self._state)
                cached = self._run_cache.get(incident.trigger.idempotency_key)
                if (
                    cached is not None
                    and cached.context is not None
                    and cached.plan is not None
                    and cached.verification is not None
                    and cached.authorization is not None
                ):
                    self._prepared = PreparedIncidentRun(
                        incident=incident,
                        context=cached.context,
                        plan=cached.plan,
                        verification=cached.verification,
                        authorization=cached.authorization,
                    )
                    self._result = cached.model_copy(update={"idempotent_replay": True})
                    self._state = _dashboard_state(
                        self._prepared,
                        self._result,
                        mode=self.mode,
                    )
                    return copy.deepcopy(self._state)
                context = IncidentContext.model_validate(self.context_provider(incident))
                if context.incident.incident_id != incident.incident_id:
                    raise IncidentIntegrationError(
                        "context incident_id does not match the resolved incident"
                    )
                plan = ActionPlan.model_validate(self.planner.plan(context))
                if plan.planner_id != self.planner.planner_id:
                    raise IncidentIntegrationError(
                        "planner output planner_id does not match the configured planner"
                    )
                if plan.planner_family.casefold() != self.planner.family.casefold():
                    raise IncidentIntegrationError(
                        "planner output family does not match the configured planner"
                    )
                verification = self.verifier_panel.verify(context, plan)
                authorization = self.policy_gate.authorize(context, plan, verification)
                self._prepared = PreparedIncidentRun(
                    incident=incident,
                    context=context,
                    plan=plan,
                    verification=verification,
                    authorization=authorization,
                )
                self._result = None
                self._state = _dashboard_state(self._prepared, None, mode=self.mode)
            except Exception as exc:
                self._prepared = None
                self._result = None
                self._state = _failed_state(self.mode, exc)
                raise IncidentIntegrationError(
                    f"incident preparation failed closed: {type(exc).__name__}: {exc}"
                ) from exc
            return copy.deepcopy(self._state)

    def execute(self, authorization: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            prepared = self._prepared
            if prepared is None:
                raise IncidentIntegrationError("no prepared incident is available")
            if not prepared.authorization.authorized:
                reasons = ", ".join(prepared.authorization.reason_codes)
                raise IncidentIntegrationError(
                    f"deterministic policy denied the prepared plan: {reasons}"
                )
            expected_hash = plan_fingerprint(self._state)
            if authorization.get("incident_id") != prepared.incident.incident_id:
                raise IncidentIntegrationError("dashboard grant incident does not match")
            if authorization.get("plan_hash") != expected_hash:
                raise IncidentIntegrationError("dashboard grant plan fingerprint does not match")

            orchestrator = IncidentOrchestrator(
                context_provider=_FrozenContextProvider(prepared.context),
                planner=_FrozenPlanner(prepared.plan),
                verifier_panel=_FrozenVerifierPanel(prepared.verification),  # type: ignore[arg-type]
                policy_gate=_FrozenPolicyGate(prepared.authorization),  # type: ignore[arg-type]
                executor=self.executor,
                writeback=self.writeback,
                clock=self._clock,
                run_cache=self._run_cache,
                receipt_cache=self._receipt_cache,
            )
            self._result = orchestrator.run(prepared.incident)
            self._state = _dashboard_state(prepared, self._result, mode=self.mode)
            if self._result.state in {
                OrchestrationState.BLOCKED,
                OrchestrationState.FAILED,
            }:
                raise IncidentIntegrationError(
                    self._result.error or f"orchestration ended in {self._result.state.value}"
                )
            return copy.deepcopy(self._state)


@dataclass(frozen=True)
class _FrozenContextProvider:
    context: IncidentContext

    def __call__(self, incident: Incident) -> IncidentContext:
        if incident.incident_id != self.context.incident.incident_id:
            raise IncidentIntegrationError("frozen context incident mismatch")
        return self.context


class _FrozenPlanner:
    def __init__(self, plan: ActionPlan) -> None:
        self._plan = plan
        self.planner_id = plan.planner_id
        self.family = plan.planner_family

    def plan(self, context: IncidentContext) -> ActionPlan:
        if context.incident.incident_id != self._plan.incident_id:
            raise IncidentIntegrationError("frozen plan incident mismatch")
        return self._plan


@dataclass(frozen=True)
class _FrozenVerifierPanel:
    result: VerificationPanelResult

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerificationPanelResult:
        if (
            self.result.incident_id != context.incident.incident_id
            or self.result.plan_id != plan.plan_id
        ):
            raise IncidentIntegrationError("frozen verification identity mismatch")
        return self.result


@dataclass(frozen=True)
class _FrozenPolicyGate:
    decision: AuthorizationDecision

    def authorize(
        self,
        context: IncidentContext,
        plan: ActionPlan,
        verification: VerificationPanelResult,
    ) -> AuthorizationDecision:
        del verification
        if (
            self.decision.incident_id != context.incident.incident_id
            or self.decision.plan_id != plan.plan_id
        ):
            raise IncidentIntegrationError("frozen authorization identity mismatch")
        return self.decision


def _provider_action(action: PlannedAction) -> Any:
    parameters = dict(action.parameters)
    parameters["idempotency_key"] = action.idempotency_key
    if action.action_type == "github.issue.create":
        owner = parameters.get("owner")
        repository = parameters.get("repository")
        if f"{owner}/{repository}" != action.target:
            raise UnsupportedPlannedAction("GitHub target does not match owner/repository")
        return GitHubIssueAction.model_validate(parameters)
    if action.action_type == "slack.message.post":
        channel = parameters.get("channel")
        if channel is not None and channel != action.target:
            raise UnsupportedPlannedAction("Slack target does not match channel")
        if channel is None and action.target != "slack:webhook":
            raise UnsupportedPlannedAction("Slack webhook actions require target slack:webhook")
        return SlackMessageAction.model_validate(parameters)
    if action.action_type == "pagerduty.event.trigger":
        if action.target != "pagerduty:events-v2":
            raise UnsupportedPlannedAction("PagerDuty target must be pagerduty:events-v2")
        return PagerDutyEventAction.model_validate(parameters)
    if action.action_type == "jira.issue.create":
        if parameters.get("project_key") != action.target:
            raise UnsupportedPlannedAction("Jira target does not match project_key")
        return JiraIssueAction.model_validate(parameters)
    raise UnsupportedPlannedAction(f"unsupported planned action: {action.action_type}")


def _empty_state(mode: str) -> JsonObject:
    return {
        "schemaVersion": "1.0",
        "mode": mode,
        "availability": "ready",
        "observed_at": None,
        "capabilities": {
            "trigger": True,
            "authorize": False,
            "execute": False,
            "replay": False,
        },
        "incident": None,
        "context": None,
        "planner": None,
        "verifier": None,
        "actions": [],
        "writeback": None,
        "memory": None,
        "events": [],
        "diagnostic": "Runtime configured; waiting for an incident trigger.",
    }


def _failed_state(mode: str, exc: Exception) -> JsonObject:
    state = _empty_state(mode)
    state.update(
        {
            "availability": "failed",
            "diagnostic": f"{type(exc).__name__}: {exc}",
            "events": [
                {
                    "time": _time_label(datetime.now(UTC)),
                    "label": "Preparation failed closed",
                    "detail": type(exc).__name__,
                    "source": "LedgerLens runtime",
                }
            ],
        }
    )
    return state


def _dashboard_state(
    prepared: PreparedIncidentRun,
    result: OrchestrationResult | None,
    *,
    mode: str,
) -> JsonObject:
    context = prepared.context
    metadata = dict(context.metadata)
    root = metadata.get("rootAsset")
    root_record = dict(root) if isinstance(root, Mapping) else {}
    root_urn = (
        str(root_record.get("urn"))
        if root_record.get("urn")
        else (
            context.incident.affected_entities[0]
            if context.incident.affected_entities
            else "unknown"
        )
    )
    owner_record = metadata.get("owner")
    owner = dict(owner_record) if isinstance(owner_record, Mapping) else {}
    blast_raw = metadata.get("blastRadiusUrns")
    blast_urns = (
        tuple(str(item) for item in blast_raw)
        if isinstance(blast_raw, list)
        else tuple(context.incident.affected_entities[1:])
    )
    observed_at = result.completed_at if result is not None else prepared.authorization.evaluated_at
    action_receipts = {
        receipt.action_id: receipt for receipt in (result.receipts if result is not None else ())
    }
    actions: list[JsonObject] = []
    for planned in prepared.plan.actions:
        provider, short, operation = _ACTION_PROVIDERS.get(
            planned.action_type,
            (planned.action_type, "??", planned.action_type),
        )
        receipt = action_receipts.get(planned.action_id)
        actions.append(
            {
                "provider": provider,
                "short": short,
                "operation": operation,
                "target": planned.target,
                "status": (receipt.status.value if receipt is not None else "held"),
                "detail": (
                    receipt.message
                    if receipt is not None
                    else "Waiting for deterministic dashboard authorization."
                ),
                "receipt": (
                    receipt.output_references[0]
                    if receipt is not None and receipt.output_references
                    else None
                ),
            }
        )

    verification_checks: list[JsonObject] = [
        {
            "name": f"Verifier {verdict.verifier_id}",
            "status": (
                "pass"
                if verdict.approved
                and verdict.error is None
                and not verdict.unverifiable_fact_ids
                and not verdict.unverifiable_action_ids
                else "fail"
            ),
            "detail": " ".join(verdict.reasons),
        }
        for verdict in prepared.verification.verdicts
    ]
    verification_checks.append(
        {
            "name": "Deterministic policy preauthorization",
            "status": "pass" if prepared.authorization.authorized else "fail",
            "detail": ", ".join(prepared.authorization.reason_codes),
        }
    )

    planner_steps: list[JsonObject] = [
        {
            "order": index,
            "action": action.action_type,
            "title": _ACTION_PROVIDERS.get(
                action.action_type,
                (action.action_type, "", action.action_type),
            )[2],
            "target": action.target,
            "reversible": (
                action.risk in {ActionRisk.LOW, ActionRisk.MEDIUM}
                and not action.requires_human_approval
            ),
            "reason": action.rationale,
        }
        for index, action in enumerate(prepared.plan.actions, start=1)
    ]
    planner_steps.append(
        {
            "order": len(planner_steps) + 1,
            "action": "datahub.incident.writeback",
            "title": "Record the incident command receipt in DataHub",
            "target": root_urn,
            "reversible": True,
            "reason": "Preserve the plan, verifier verdicts, actions, and unknowns.",
        }
    )

    writeback = {
        "status": "held",
        "entity": root_urn,
        "operation": "DataHub incident command receipt",
        "receipt": None,
        "detail": "Write-back runs only after authorized provider actions.",
    }
    if result is not None and result.writeback is not None:
        writeback = {
            "status": "recorded" if result.writeback.succeeded else "failed",
            "entity": root_urn,
            "operation": "DataHub incident command receipt",
            "receipt": result.writeback.reference,
            "detail": result.writeback.message,
        }

    completed = [
        f"{item['provider']}: {item['operation']}"
        for item in actions
        if item["status"] == "succeeded"
    ]
    evidence = [
        {
            "label": fact.statement,
            "kind": pointer.kind.value,
            "receipt": pointer.reference,
        }
        for fact in context.facts
        for pointer in fact.evidence
    ]
    state: JsonObject = {
        "schemaVersion": "1.0",
        "mode": mode,
        "availability": "ready",
        "observed_at": _iso(observed_at),
        "capabilities": {
            "trigger": True,
            "authorize": prepared.authorization.authorized,
            "execute": prepared.authorization.authorized,
            "replay": False,
        },
        "incident": {
            "id": prepared.incident.incident_id,
            "severity": prepared.incident.severity.value.upper(),
            "status": (result.state.value if result is not None else "awaiting_authorization"),
            "title": prepared.incident.title,
            "service": str(root_record.get("name") or root_urn),
            "environment": str(root_record.get("environment") or "DataHub catalog"),
            "detected_at": _iso(prepared.incident.detected_at),
            "elapsed": "not measured",
            "trigger": {
                "source": prepared.incident.trigger.source,
                "signal": prepared.incident.trigger.kind,
                "summary": str(
                    prepared.incident.trigger.payload.get(
                        "signal",
                        prepared.incident.title,
                    )
                ),
                "observed": _iso(prepared.incident.trigger.occurred_at),
                "threshold": "recorded incident policy",
                "classification": "source assertion",
            },
            "commander": str(
                owner.get("displayName") or owner.get("name") or owner.get("id") or "recorded owner"
            ),
        },
        "context": {
            "status": "grounded",
            "source": str(metadata.get("source") or "DataHub"),
            "entity": {
                "urn": root_urn,
                "name": str(root_record.get("name") or root_urn),
                "platform": str(root_record.get("platform") or "DataHub"),
                "domain": str(root_record.get("domain") or "recorded"),
                "owner": str(
                    owner.get("displayName")
                    or owner.get("name")
                    or owner.get("id")
                    or "recorded owner"
                ),
                "tier": str(root_record.get("tier") or "recorded"),
                "last_observed": _iso(context.collected_at),
            },
            "blast_radius": {
                "authorization_boundary": "bounded",
                "summary": f"{len(blast_urns)} downstream assets recorded.",
                "asset_count": len(blast_urns),
                "critical_count": sum("tier1" in item.casefold() for item in blast_urns),
                "people_on_call": 1 if owner else 0,
                "confidence": "metadata-derived, not causal proof",
                "assets": [
                    {
                        "name": urn,
                        "type": "DataHub entity",
                        "criticality": "recorded",
                        "relationship": "downstream",
                    }
                    for urn in blast_urns[:12]
                ],
                "unknowns": [
                    "Lineage proximity does not establish user-visible impact.",
                    "Root cause and recovery remain unverified.",
                ],
            },
            "evidence": evidence,
        },
        "planner": {
            "status": "ready",
            "generated_by": prepared.plan.planner_id,
            "objective": prepared.plan.summary,
            "scope": "Allowlisted collaboration actions plus DataHub receipt write-back",
            "risk": "Production mutations and unsupported remediation remain prohibited.",
            "steps": planner_steps,
            "assumptions": [
                "Targets remain within deterministic allowlists.",
                "Provider credentials are held outside model prompts.",
            ],
            "unknowns": [
                "The plan does not establish incident causality.",
                "A provider receipt does not establish incident recovery.",
            ],
        },
        "verifier": {
            "status": "complete",
            "label": "Independent AI verifier panel",
            "model": ", ".join(prepared.verification.participating_families),
            "approved": (prepared.verification.approved and prepared.authorization.authorized),
            "verdict": (
                "APPROVED"
                if prepared.verification.approved and prepared.authorization.authorized
                else "BLOCKED"
            ),
            "summary": ", ".join(prepared.verification.reason_codes),
            "policy_checks": verification_checks,
            "authority_note": (
                "Model variants provide advisory votes. Deterministic policy is the "
                "authorization authority; provider-family independence is not claimed."
            ),
        },
        "actions": actions,
        "writeback": writeback,
        "memory": {
            "status": "ready" if result is not None else "draft",
            "memory_id": (f"ledgerlens://memory/{result.run_id}" if result is not None else None),
            "next_agent": "Recovery verifier",
            "summary": (
                "Authorized action and write-back receipts are ready for the next agent."
                if result is not None
                else "Execution has not occurred."
            ),
            "known_facts": [fact.statement for fact in context.facts],
            "unknowns": [
                "Root cause is not established.",
                "End-user impact is not established.",
                "Recovery has not been independently observed.",
            ],
            "completed": completed,
            "next_actions": [
                "Verify a fresh DataHub assertion before claiming recovery.",
                "Reconcile any failed or ambiguous provider action.",
            ],
            "provenance": [pointer.reference for fact in context.facts for pointer in fact.evidence]
            + [str(item["receipt"]) for item in actions if item["receipt"] is not None],
        },
        "events": [
            {
                "time": _time_label(prepared.incident.detected_at),
                "label": "Trigger observed",
                "detail": prepared.incident.trigger.kind,
                "source": prepared.incident.trigger.source,
            },
            {
                "time": _time_label(context.collected_at),
                "label": "Context grounded",
                "detail": f"{len(context.facts)} evidence-grounded facts collected.",
                "source": str(metadata.get("source") or "DataHub"),
            },
            {
                "time": _time_label(prepared.plan.created_at),
                "label": "Plan and verifier panel completed",
                "detail": ", ".join(prepared.verification.reason_codes),
                "source": "AI advisory plus deterministic policy",
            },
        ],
        "diagnostic": None,
    }
    if result is not None:
        state["events"].append(
            {
                "time": _time_label(result.completed_at),
                "label": "Orchestration completed",
                "detail": result.state.value,
                "source": "IncidentOrchestrator",
            }
        )
    state["planner"]["plan_hash"] = plan_fingerprint(state)
    return state


def _writeback_reference(receipt: Mapping[str, Any]) -> str:
    result = receipt.get("result")
    if isinstance(result, Mapping):
        for key in ("urn", "documentUrn", "document_urn"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
    receipt_id = receipt.get("receiptId")
    return f"datahub://writeback/{receipt_id}"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _time_label(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%H:%M:%S")


__all__ = [
    "ActionRegistryExecutor",
    "DataHubIncidentWriteback",
    "IncidentIntegrationError",
    "OrchestratorIncidentBackend",
    "PreparedIncidentRun",
    "UnsupportedPlannedAction",
]
