"""Fail-closed orchestration state machine for autonomous incident response."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ledgerlens.incident_models import (
    ActionPlan,
    ActionReceipt,
    ActionReceiptStatus,
    ClaimBoundedModel,
    Incident,
    IncidentContext,
    IncidentPlanner,
    PlannedAction,
)
from ledgerlens.verification import (
    AuthorizationDecision,
    PolicyGate,
    VerificationPanelResult,
    VerifierPanel,
)


class OrchestrationState(StrEnum):
    """Observable states in the incident-command workflow."""

    TRIGGERED = "triggered"
    CONTEXT_READY = "context_ready"
    PLANNED = "planned"
    VERIFIED = "verified"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    RECEIPTS_RECORDED = "receipts_recorded"
    WRITTEN_BACK = "written_back"
    BLOCKED = "blocked"
    FAILED = "failed"


class ExecutionOutcome(BaseModel):
    """Typed response from an injected action executor."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    succeeded: bool
    executor: str = Field(min_length=1)
    message: str = Field(min_length=1)
    output_references: tuple[str, ...] = Field(default_factory=tuple)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class WritebackOutcome(BaseModel):
    """Typed response from the injected writeback callback."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    succeeded: bool
    message: str = Field(min_length=1)
    reference: str | None = Field(default=None, min_length=1)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class OrchestrationResult(ClaimBoundedModel):
    """Complete audit object for one incident-command run."""

    run_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    trigger_id: str = Field(min_length=1)
    state: OrchestrationState
    state_history: tuple[OrchestrationState, ...]
    started_at: datetime
    completed_at: datetime
    context: IncidentContext | None = None
    plan: ActionPlan | None = None
    verification: VerificationPanelResult | None = None
    authorization: AuthorizationDecision | None = None
    receipts: tuple[ActionReceipt, ...] = Field(default_factory=tuple)
    writeback: WritebackOutcome | None = None
    error: str | None = Field(default=None, min_length=1)
    idempotent_replay: bool = False


@runtime_checkable
class ContextProvider(Protocol):
    """Injected read-only context collector."""

    def __call__(self, incident: Incident) -> IncidentContext:
        """Return evidence-grounded context for the incident."""


@runtime_checkable
class ActionExecutor(Protocol):
    """Injected bounded tool executor."""

    def __call__(
        self,
        context: IncidentContext,
        action: PlannedAction,
    ) -> ExecutionOutcome | Mapping[str, object]:
        """Execute exactly one already-authorized action."""


@runtime_checkable
class WritebackCallback(Protocol):
    """Injected callback that records the run and its receipts."""

    def __call__(
        self,
        result: OrchestrationResult,
    ) -> WritebackOutcome | Mapping[str, object] | None:
        """Write back the receipt-bearing run snapshot."""


class IncidentOrchestrator:
    """Run trigger -> context -> plan -> verify -> authorize -> execute -> writeback."""

    def __init__(
        self,
        *,
        context_provider: ContextProvider,
        planner: IncidentPlanner,
        verifier_panel: VerifierPanel,
        policy_gate: PolicyGate,
        executor: ActionExecutor,
        writeback: WritebackCallback,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
        run_cache: MutableMapping[str, OrchestrationResult] | None = None,
        receipt_cache: MutableMapping[str, ActionReceipt] | None = None,
        stop_on_action_failure: bool = True,
    ) -> None:
        self.context_provider = context_provider
        self.planner = planner
        self.verifier_panel = verifier_panel
        self.policy_gate = policy_gate
        self.executor = executor
        self.writeback = writeback
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4()}")
        self._run_cache = run_cache if run_cache is not None else {}
        self._receipt_cache = receipt_cache if receipt_cache is not None else {}
        self.stop_on_action_failure = stop_on_action_failure

    def run(self, incident: Incident) -> OrchestrationResult:
        """Execute a full incident workflow or return a cached idempotent replay."""

        run_key = incident.trigger.idempotency_key
        cached = self._run_cache.get(run_key)
        if cached is not None:
            return cached.model_copy(update={"idempotent_replay": True})

        run_id = self._id_factory("run")
        started_at = self._clock()
        history = [OrchestrationState.TRIGGERED]
        context: IncidentContext | None = None
        plan: ActionPlan | None = None
        verification: VerificationPanelResult | None = None
        authorization: AuthorizationDecision | None = None
        receipts: list[ActionReceipt] = []
        writeback_outcome: WritebackOutcome | None = None

        try:
            context = IncidentContext.model_validate(self.context_provider(incident))
            if context.incident.incident_id != incident.incident_id:
                raise ValueError("context incident_id does not match the trigger incident")
            if context.incident.trigger.idempotency_key != run_key:
                raise ValueError("context changed the incident idempotency key")
            history.append(OrchestrationState.CONTEXT_READY)

            plan = ActionPlan.model_validate(self.planner.plan(context))
            if plan.planner_id != self.planner.planner_id:
                raise ValueError("planner output planner_id does not match the injected planner")
            if plan.planner_family.casefold() != self.planner.family.casefold():
                raise ValueError("planner output family does not match the injected planner")
            history.append(OrchestrationState.PLANNED)

            verification = self.verifier_panel.verify(context, plan)
            history.append(OrchestrationState.VERIFIED)

            authorization = self.policy_gate.authorize(context, plan, verification)
            if not authorization.authorized:
                history.append(OrchestrationState.BLOCKED)
                result = self._result(
                    run_id=run_id,
                    incident=incident,
                    state=OrchestrationState.BLOCKED,
                    history=history,
                    started_at=started_at,
                    context=context,
                    plan=plan,
                    verification=verification,
                    authorization=authorization,
                )
                self._run_cache[run_key] = result
                return result
            history.append(OrchestrationState.AUTHORIZED)
            history.append(OrchestrationState.EXECUTING)

            action_failed = False
            for action in plan.actions:
                receipt = self._execute_action(
                    run_id=run_id,
                    incident=incident,
                    plan=plan,
                    context=context,
                    action=action,
                )
                receipts.append(receipt)
                if receipt.status is ActionReceiptStatus.FAILED:
                    action_failed = True
                    if self.stop_on_action_failure:
                        break
            history.append(OrchestrationState.RECEIPTS_RECORDED)

            snapshot = self._result(
                run_id=run_id,
                incident=incident,
                state=OrchestrationState.RECEIPTS_RECORDED,
                history=history,
                started_at=started_at,
                context=context,
                plan=plan,
                verification=verification,
                authorization=authorization,
                receipts=receipts,
            )
            raw_writeback = self.writeback(snapshot)
            writeback_outcome = (
                WritebackOutcome(
                    succeeded=True,
                    message="writeback callback completed",
                )
                if raw_writeback is None
                else WritebackOutcome.model_validate(raw_writeback)
            )
            if not writeback_outcome.succeeded:
                raise RuntimeError(f"writeback failed: {writeback_outcome.message}")
            history.append(OrchestrationState.WRITTEN_BACK)

            final_state = (
                OrchestrationState.FAILED if action_failed else OrchestrationState.WRITTEN_BACK
            )
            error = "one or more authorized actions failed" if action_failed else None
            if action_failed:
                history.append(OrchestrationState.FAILED)
            result = self._result(
                run_id=run_id,
                incident=incident,
                state=final_state,
                history=history,
                started_at=started_at,
                context=context,
                plan=plan,
                verification=verification,
                authorization=authorization,
                receipts=receipts,
                writeback=writeback_outcome,
                error=error,
            )
        except Exception as exc:
            if history[-1] is not OrchestrationState.FAILED:
                history.append(OrchestrationState.FAILED)
            result = self._result(
                run_id=run_id,
                incident=incident,
                state=OrchestrationState.FAILED,
                history=history,
                started_at=started_at,
                context=context,
                plan=plan,
                verification=verification,
                authorization=authorization,
                receipts=receipts,
                writeback=writeback_outcome,
                error=f"{type(exc).__name__}: {exc}",
            )

        self._run_cache[run_key] = result
        return result

    orchestrate = run

    def _execute_action(
        self,
        *,
        run_id: str,
        incident: Incident,
        plan: ActionPlan,
        context: IncidentContext,
        action: PlannedAction,
    ) -> ActionReceipt:
        cached = self._receipt_cache.get(action.idempotency_key)
        if cached is not None:
            if cached.incident_id != incident.incident_id or cached.action_id != action.action_id:
                raise RuntimeError(f"idempotency key collision for action {action.action_id}")
            return cached

        started_at = self._clock()
        try:
            raw = self.executor(context, action)
            outcome = (
                raw if isinstance(raw, ExecutionOutcome) else ExecutionOutcome.model_validate(raw)
            )
        except Exception as exc:
            outcome = ExecutionOutcome(
                succeeded=False,
                executor=type(self.executor).__name__,
                message=f"{type(exc).__name__}: {exc}",
            )
        receipt = ActionReceipt(
            receipt_id=self._id_factory("receipt"),
            run_id=run_id,
            incident_id=incident.incident_id,
            plan_id=plan.plan_id,
            action_id=action.action_id,
            idempotency_key=action.idempotency_key,
            executor=outcome.executor,
            status=(
                ActionReceiptStatus.SUCCEEDED if outcome.succeeded else ActionReceiptStatus.FAILED
            ),
            started_at=started_at,
            completed_at=self._clock(),
            message=outcome.message,
            output_references=outcome.output_references,
            details=outcome.details,
        )
        self._receipt_cache[action.idempotency_key] = receipt
        return receipt

    def _result(
        self,
        *,
        run_id: str,
        incident: Incident,
        state: OrchestrationState,
        history: list[OrchestrationState],
        started_at: datetime,
        context: IncidentContext | None = None,
        plan: ActionPlan | None = None,
        verification: VerificationPanelResult | None = None,
        authorization: AuthorizationDecision | None = None,
        receipts: list[ActionReceipt] | None = None,
        writeback: WritebackOutcome | None = None,
        error: str | None = None,
    ) -> OrchestrationResult:
        return OrchestrationResult(
            run_id=run_id,
            incident_id=incident.incident_id,
            trigger_id=incident.trigger.trigger_id,
            state=state,
            state_history=tuple(history),
            started_at=started_at,
            completed_at=self._clock(),
            context=context,
            plan=plan,
            verification=verification,
            authorization=authorization,
            receipts=tuple(receipts or ()),
            writeback=writeback,
            error=error,
        )


AutonomousIncidentCommander = IncidentOrchestrator
