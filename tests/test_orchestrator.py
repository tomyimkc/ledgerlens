"""End-to-end, network-free tests for the incident orchestration state machine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ledgerlens.incident_models import (
    ActionPlan,
    ActionReceiptStatus,
    ActionRisk,
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentTrigger,
    PlannedAction,
)
from ledgerlens.orchestrator import (
    ExecutionOutcome,
    IncidentOrchestrator,
    OrchestrationResult,
    OrchestrationState,
    WritebackOutcome,
)
from ledgerlens.verification import (
    ActionAllowance,
    PolicyConfig,
    PolicyGate,
    VerifierAssessment,
    VerifierPanel,
)

NOW = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)


def _incident() -> Incident:
    return Incident(
        incident_id="incident-1",
        title="Orders freshness degraded",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        trigger=IncidentTrigger(
            trigger_id="trigger-1",
            source="datahub",
            kind="freshness_assertion",
            occurred_at=NOW,
            idempotency_key="incident-trigger-key",
        ),
    )


def _context(incident: Incident) -> IncidentContext:
    return IncidentContext(
        context_id="context-1",
        incident=incident,
        collected_at=NOW,
        facts=(
            IncidentFact(
                fact_id="fact-1",
                statement="The freshness assertion is failed.",
                evidence=(
                    EvidencePointer(
                        reference="urn:li:assertion:orders-freshness",
                        kind=EvidenceKind.DATAHUB_ENTITY,
                        observed_at=NOW,
                    ),
                ),
            ),
        ),
    )


class FakePlanner:
    planner_id = "planner-1"
    family = "planner-family"

    def __init__(self, *, action_type: str = "notify_owner") -> None:
        self.action_type = action_type
        self.calls = 0

    def plan(self, context: IncidentContext) -> ActionPlan:
        self.calls += 1
        return ActionPlan(
            plan_id="plan-1",
            incident_id=context.incident.incident_id,
            planner_id=self.planner_id,
            planner_family=self.family,
            created_at=NOW,
            confidence=0.96,
            summary="Notify the owner using the grounded assertion state.",
            actions=(
                PlannedAction(
                    action_id="action-1",
                    action_type=self.action_type,
                    target="urn:li:corpgroup:data-platform",
                    parameters={"channel": "incident-room"},
                    rationale="The allowlisted owner should receive the incident.",
                    evidence_fact_ids=("fact-1",),
                    idempotency_key="incident-1:action-1",
                    risk=ActionRisk.LOW,
                ),
            ),
        )


class FakeVerifier:
    def __init__(self, verifier_id: str, family: str) -> None:
        self.verifier_id = verifier_id
        self.family = family

    def verify(
        self,
        context: IncidentContext,
        plan: ActionPlan,
    ) -> VerifierAssessment:
        assert plan.incident_id == context.incident.incident_id
        return VerifierAssessment(
            approved=True,
            confidence=0.95,
            reasons=("all facts and actions are structurally verifiable",),
        )


def _gate() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            allowances=(
                ActionAllowance(
                    action_type="notify_owner",
                    targets=frozenset({"urn:li:corpgroup:data-platform"}),
                    allowed_parameter_keys=frozenset({"channel"}),
                    required_parameter_keys=frozenset({"channel"}),
                    maximum_risk=ActionRisk.LOW,
                ),
            ),
        ),
        clock=lambda: NOW,
    )


def _id_factory() -> Callable[[str], str]:
    counters: dict[str, int] = {}

    def factory(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]}"

    return factory


def _commander(
    *,
    planner: FakePlanner,
    executor: Callable[[IncidentContext, PlannedAction], ExecutionOutcome | dict[str, Any]],
    writeback: Callable[
        [OrchestrationResult],
        WritebackOutcome | dict[str, Any] | None,
    ],
) -> IncidentOrchestrator:
    return IncidentOrchestrator(
        context_provider=_context,
        planner=planner,
        verifier_panel=VerifierPanel(
            (
                FakeVerifier("verifier-1", "family-a"),
                FakeVerifier("verifier-2", "family-b"),
            )
        ),
        policy_gate=_gate(),
        executor=executor,
        writeback=writeback,
        clock=lambda: NOW,
        id_factory=_id_factory(),
    )


def test_orchestrator_runs_every_stage_and_writes_back_receipts() -> None:
    events: list[str] = []
    planner = FakePlanner()

    def execute(context: IncidentContext, action: PlannedAction) -> ExecutionOutcome:
        events.append(f"execute:{action.action_id}")
        assert context.fact_ids == frozenset({"fact-1"})
        return ExecutionOutcome(
            succeeded=True,
            executor="notification-tool",
            message="notification accepted",
            output_references=("ticket://INC-1",),
        )

    def writeback(result: OrchestrationResult) -> WritebackOutcome:
        events.append("writeback")
        assert result.state is OrchestrationState.RECEIPTS_RECORDED
        assert result.receipts[0].status is ActionReceiptStatus.SUCCEEDED
        return WritebackOutcome(
            succeeded=True,
            message="incident timeline updated",
            reference="urn:li:dataset:incident-1",
        )

    result = _commander(
        planner=planner,
        executor=execute,
        writeback=writeback,
    ).run(_incident())

    assert result.state is OrchestrationState.WRITTEN_BACK
    assert result.state_history == (
        OrchestrationState.TRIGGERED,
        OrchestrationState.CONTEXT_READY,
        OrchestrationState.PLANNED,
        OrchestrationState.VERIFIED,
        OrchestrationState.AUTHORIZED,
        OrchestrationState.EXECUTING,
        OrchestrationState.RECEIPTS_RECORDED,
        OrchestrationState.WRITTEN_BACK,
    )
    assert events == ["execute:action-1", "writeback"]
    assert result.authorization is not None and result.authorization.authorized is True
    assert result.receipts[0].output_references == ("ticket://INC-1",)
    assert result.candidate_only is True
    assert result.can_claim_agi is False


def test_orchestrator_blocks_before_execution_when_policy_denies() -> None:
    calls = {"executor": 0, "writeback": 0}

    def execute(context: IncidentContext, action: PlannedAction) -> ExecutionOutcome:
        del context, action
        calls["executor"] += 1
        raise AssertionError("executor must not run")

    def writeback(result: OrchestrationResult) -> None:
        del result
        calls["writeback"] += 1
        raise AssertionError("writeback must not run for a blocked plan")

    result = _commander(
        planner=FakePlanner(action_type="drop_table"),
        executor=execute,
        writeback=writeback,
    ).run(_incident())

    assert result.state is OrchestrationState.BLOCKED
    assert result.receipts == ()
    assert result.authorization is not None
    assert "action_not_allowlisted:action-1" in result.authorization.reason_codes
    assert calls == {"executor": 0, "writeback": 0}


def test_trigger_idempotency_replays_without_model_tool_or_writeback_calls() -> None:
    calls = {"executor": 0, "writeback": 0}
    planner = FakePlanner()

    def execute(context: IncidentContext, action: PlannedAction) -> dict[str, Any]:
        del context, action
        calls["executor"] += 1
        return {
            "succeeded": True,
            "executor": "notification-tool",
            "message": "notification accepted",
        }

    def writeback(result: OrchestrationResult) -> dict[str, Any]:
        del result
        calls["writeback"] += 1
        return {"succeeded": True, "message": "recorded"}

    commander = _commander(planner=planner, executor=execute, writeback=writeback)
    first = commander.run(_incident())
    replay = commander.run(_incident())

    assert first.idempotent_replay is False
    assert replay.idempotent_replay is True
    assert replay.run_id == first.run_id
    assert replay.receipts == first.receipts
    assert planner.calls == 1
    assert calls == {"executor": 1, "writeback": 1}


def test_executor_exception_becomes_failed_receipt_and_is_written_back() -> None:
    snapshots: list[OrchestrationResult] = []

    def execute(context: IncidentContext, action: PlannedAction) -> ExecutionOutcome:
        del context, action
        raise RuntimeError("tool unavailable")

    def writeback(result: OrchestrationResult) -> WritebackOutcome:
        snapshots.append(result)
        return WritebackOutcome(succeeded=True, message="failure receipt recorded")

    result = _commander(
        planner=FakePlanner(),
        executor=execute,
        writeback=writeback,
    ).run(_incident())

    assert result.state is OrchestrationState.FAILED
    assert result.receipts[0].status is ActionReceiptStatus.FAILED
    assert "RuntimeError: tool unavailable" in result.receipts[0].message
    assert snapshots[0].state is OrchestrationState.RECEIPTS_RECORDED
    assert snapshots[0].receipts == result.receipts
    assert result.writeback is not None and result.writeback.succeeded is True
