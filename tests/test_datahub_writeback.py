"""Deterministic controlled DataHub write-back policy and receipt tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from ledgerlens.datahub_writeback import (
    DataHubWritebackService,
    DeterministicPolicyGate,
    IdempotencyConflictError,
    IncidentStatus,
    IncidentStatusContext,
    PolicyDeniedError,
    WritebackExecutionError,
    WritebackRequest,
    WritebackStatus,
)
from ledgerlens.mcp_mutations import (
    MCPMutationAuthorizationError,
    MCPMutationClient,
    MutationTool,
)

URN = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,incident-7,PROD)"
TAG = "urn:li:tag:ledgerlens.status-monitoring"
PROPERTY = "urn:li:structuredProperty:ledgerlens.incidentStatus"


class FakeTransport:
    def __init__(self, result: Any = None, *, error: Exception | None = None) -> None:
        self.result = result or {"structuredContent": {"success": True}}
        self.error = error
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        self.calls.append((method, dict(params or {})))
        if self.error is not None:
            raise self.error
        return self.result

    def close(self) -> None:
        return None


class SequenceSnapshotReader:
    def __init__(self, states: Sequence[Mapping[str, Any]]) -> None:
        self.states = list(states)
        self.calls: list[tuple[str, ...]] = []

    def capture(self, urns: Sequence[str]) -> Mapping[str, Any]:
        self.calls.append(tuple(urns))
        return self.states.pop(0)


class FixedClock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> datetime:
        self.tick += 1
        return datetime(2026, 7, 31, 12, 0, self.tick, tzinfo=UTC)


def _context() -> IncidentStatusContext:
    return IncidentStatusContext(
        incident_id="INC-7",
        previous_status=IncidentStatus.INVESTIGATING,
        status=IncidentStatus.MONITORING,
        summary="Mitigation deployed; monitor receipts.",
        source="deterministic-policy",
    )


def _stack(
    *,
    enabled: bool = True,
    transport: FakeTransport | None = None,
    snapshots: SequenceSnapshotReader | None = None,
    supported_tools: set[MutationTool] | None = None,
) -> tuple[DataHubWritebackService, DeterministicPolicyGate, FakeTransport]:
    actual_transport = transport or FakeTransport()
    gate = DeterministicPolicyGate(enabled=enabled)
    mutations = MCPMutationClient(
        actual_transport,
        enabled=enabled,
        supported_tools=supported_tools,
        authorization_verifier=gate,
    )
    service = DataHubWritebackService(
        mutations,
        gate,
        snapshot_reader=snapshots,
        clock=FixedClock(),
    )
    return service, gate, actual_transport


def test_live_writeback_is_disabled_by_default_but_preview_is_available() -> None:
    service, gate, transport = _stack(enabled=False)
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-tags",
    )
    with pytest.raises(PolicyDeniedError, match="disabled"):
        gate.authorize(request, actor="oncall", reason="status transition")

    authorization = gate.authorize(
        request,
        actor="oncall",
        reason="review intended status transition",
        preview=True,
        incident_context=_context(),
    )
    receipt = service.execute(request, authorization=authorization, preview=True)
    assert receipt.status is WritebackStatus.PREVIEW
    assert receipt.after.source == "deterministic-preview"
    assert receipt.result == {"planned": True, "transportCalled": False}
    assert transport.calls == []


def test_preview_only_authorization_cannot_execute() -> None:
    service, gate, transport = _stack(enabled=True)
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-preview-only",
    )
    authorization = gate.authorize(
        request,
        actor="oncall",
        reason="preview",
        preview=True,
    )
    with pytest.raises(MCPMutationAuthorizationError, match="preview-only"):
        service.execute(request, authorization=authorization)
    assert transport.calls == []


def test_authorization_is_exact_call_bound_and_gate_local() -> None:
    service, gate, transport = _stack()
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-bound",
    )
    changed = WritebackRequest.remove_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-bound",
    )
    authorization = gate.authorize(request, actor="oncall", reason="approved")
    with pytest.raises(MCPMutationAuthorizationError, match="tool does not match"):
        service.execute(changed, authorization=authorization)

    other_gate = DeterministicPolicyGate(enabled=True)
    foreign = other_gate.authorize(request, actor="oncall", reason="approved")
    with pytest.raises(MCPMutationAuthorizationError, match="not issued by this"):
        service.execute(request, authorization=foreign)
    assert transport.calls == []


def test_execution_captures_before_after_receipts_and_incident_context() -> None:
    snapshots = SequenceSnapshotReader(
        [
            {"urn": URN, "tags": []},
            {"urn": URN, "tags": [TAG]},
        ]
    )
    service, gate, transport = _stack(snapshots=snapshots)
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-apply",
    )
    authorization = gate.authorize(
        request,
        actor="urn:li:corpuser:oncall",
        reason="incident moved to monitoring",
        incident_context=_context(),
    )
    receipt = service.execute(request, authorization=authorization)
    payload = receipt.to_dict()
    assert receipt.status is WritebackStatus.APPLIED
    assert receipt.before.available is True
    assert receipt.after.available is True
    assert receipt.before.digest != receipt.after.digest
    assert payload["authorization"]["incidentContext"]["incidentId"] == "INC-7"
    assert payload["authorization"]["incidentContext"]["status"] == "monitoring"
    assert transport.calls[0][1]["name"] == "add_tags"
    assert receipt.rollback.available is True
    assert receipt.rollback.actions[0].tool is MutationTool.REMOVE_TAGS


def test_exact_tag_rollback_does_not_remove_a_preexisting_tag() -> None:
    snapshots = SequenceSnapshotReader(
        [
            {"urn": URN, "tags": [TAG]},
            {"urn": URN, "tags": [TAG]},
        ]
    )
    service, gate, _ = _stack(snapshots=snapshots)
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-existing-tag",
    )
    authorization = gate.authorize(request, actor="oncall", reason="ensure status tag")
    receipt = service.execute(request, authorization=authorization)
    assert receipt.rollback.exact is True
    assert receipt.rollback.actions == ()


def test_idempotency_replays_receipt_without_second_mutation() -> None:
    service, gate, transport = _stack()
    request = WritebackRequest.remove_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-idempotent",
    )
    authorization = gate.authorize(request, actor="oncall", reason="correct stale tag")
    first = service.execute(request, authorization=authorization)
    second = service.execute(request, authorization=authorization)
    assert first.replayed is False
    assert second.replayed is True
    assert second.receipt_id == first.receipt_id
    assert len(transport.calls) == 1


def test_idempotency_key_conflict_fails_before_transport() -> None:
    service, gate, transport = _stack()
    first = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-conflict",
    )
    first_auth = gate.authorize(first, actor="oncall", reason="first")
    service.execute(first, authorization=first_auth)
    changed = WritebackRequest.add_tags(
        tag_urns=["urn:li:tag:different"],
        entity_urns=[URN],
        idempotency_key="incident-7-conflict",
    )
    changed_auth = gate.authorize(changed, actor="oncall", reason="changed")
    with pytest.raises(IdempotencyConflictError):
        service.execute(changed, authorization=changed_auth)
    assert len(transport.calls) == 1


def test_preview_key_does_not_consume_live_execution_key() -> None:
    service, gate, transport = _stack()
    request = WritebackRequest.update_description(
        entity_urn=URN,
        operation="replace",
        description="Incident INC-7 is monitoring.",
        idempotency_key="incident-7-description",
    )
    preview_auth = gate.authorize(
        request,
        actor="oncall",
        reason="review",
        preview=True,
    )
    service.execute(request, authorization=preview_auth, preview=True)
    live_auth = gate.authorize(request, actor="oncall", reason="approved")
    receipt = service.execute(request, authorization=live_auth)
    assert receipt.status is WritebackStatus.APPLIED
    assert len(transport.calls) == 1


def test_description_rollback_restores_captured_value() -> None:
    snapshots = SequenceSnapshotReader(
        [
            {"urn": URN, "description": "Previous description"},
            {"urn": URN, "description": "Incident INC-7 is monitoring."},
        ]
    )
    service, gate, _ = _stack(snapshots=snapshots)
    request = WritebackRequest.update_description(
        entity_urn=URN,
        operation="replace",
        description="Incident INC-7 is monitoring.",
        idempotency_key="incident-7-desc-rollback",
    )
    authorization = gate.authorize(request, actor="oncall", reason="approved")
    receipt = service.execute(request, authorization=authorization)
    action = receipt.rollback.actions[0]
    assert receipt.rollback.exact is True
    assert action.tool is MutationTool.UPDATE_DESCRIPTION
    assert action.arguments == {
        "entity_urn": URN,
        "operation": "replace",
        "description": "Previous description",
    }


def test_structured_property_rollback_restores_previous_values() -> None:
    snapshots = SequenceSnapshotReader(
        [
            {"urn": URN, "structured_properties": {PROPERTY: ["investigating"]}},
            {"urn": URN, "structured_properties": {PROPERTY: ["monitoring"]}},
        ]
    )
    service, gate, transport = _stack(snapshots=snapshots)
    request = WritebackRequest.set_structured_properties(
        property_values={PROPERTY: ["monitoring"]},
        entity_urns=[URN],
        idempotency_key="incident-7-property",
    )
    authorization = gate.authorize(
        request,
        actor="oncall",
        reason="record status",
        incident_context=_context(),
    )
    receipt = service.execute(request, authorization=authorization)
    assert transport.calls[0][1]["name"] == "add_structured_properties"
    assert receipt.rollback.exact is True
    assert receipt.rollback.actions[0].arguments["property_values"] == {PROPERTY: ["investigating"]}


def test_unsupported_structured_properties_fail_with_sanitized_receipt() -> None:
    service, gate, transport = _stack(supported_tools={MutationTool.ADD_TAGS})
    request = WritebackRequest.set_structured_properties(
        property_values={PROPERTY: ["monitoring"]},
        entity_urns=[URN],
        idempotency_key="incident-7-unsupported",
    )
    authorization = gate.authorize(request, actor="oncall", reason="record status")
    with pytest.raises(WritebackExecutionError) as exc_info:
        service.execute(request, authorization=authorization)
    assert exc_info.value.receipt.status is WritebackStatus.FAILED
    assert "not supported" in (exc_info.value.receipt.error or "")
    assert transport.calls == []


def test_new_document_receipt_records_non_compensable_creation() -> None:
    transport = FakeTransport(
        {
            "structuredContent": {
                "success": True,
                "urn": "urn:li:document:shared-1",
            }
        }
    )
    service, gate, _ = _stack(transport=transport)
    request = WritebackRequest.save_document(
        document_type="Context",
        title="INC-7 status context",
        content="Mitigation deployed; monitor deterministic receipts.",
        related_assets=[URN],
        idempotency_key="incident-7-document",
    )
    authorization = gate.authorize(
        request,
        actor="oncall",
        reason="persist incident context",
        incident_context=_context(),
    )
    receipt = service.execute(request, authorization=authorization)
    assert receipt.rollback.available is False
    assert "no document deletion tool" in receipt.rollback.limitations[0]
    assert receipt.after.urns == ("urn:li:document:shared-1",)


def test_failure_receipt_redacts_tokens_and_blocks_automatic_retry() -> None:
    transport = FakeTransport(error=RuntimeError("upstream Bearer raw-token token=second-token"))
    service, gate, _ = _stack(transport=transport)
    request = WritebackRequest.add_tags(
        tag_urns=[TAG],
        entity_urns=[URN],
        idempotency_key="incident-7-failure",
    )
    authorization = gate.authorize(request, actor="oncall", reason="approved")
    with pytest.raises(WritebackExecutionError) as first:
        service.execute(request, authorization=authorization)
    serialized = repr(first.value.receipt.to_dict())
    assert "raw-token" not in serialized
    assert "second-token" not in serialized
    assert "[REDACTED]" in serialized

    with pytest.raises(WritebackExecutionError) as replay:
        service.execute(request, authorization=authorization)
    assert replay.value.receipt.replayed is True
    assert len(transport.calls) == 1
