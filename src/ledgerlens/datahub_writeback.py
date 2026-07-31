"""Controlled DataHub write-back orchestration and audit receipts."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol

from ledgerlens.mcp_client import DataHubMCPClient
from ledgerlens.mcp_mutations import (
    OFFICIAL_MUTATION_TOOLS,
    MCPMutationAuthorizationError,
    MCPMutationClient,
    MutationAuthorization,
    MutationCall,
    MutationTool,
    redact_sensitive,
    redact_text,
)

JsonObject = dict[str, Any]


class WritebackError(RuntimeError):
    """Base controlled write-back error."""


class PolicyDeniedError(WritebackError):
    """Raised when the deterministic policy gate refuses authorization."""


class IdempotencyConflictError(WritebackError):
    """Raised when an idempotency key is reused for a different request."""


class WritebackExecutionError(WritebackError):
    """Execution failure carrying the sanitized audit receipt."""

    def __init__(self, receipt: WritebackReceipt) -> None:
        self.receipt = receipt
        super().__init__(receipt.error or "DataHub write-back failed")


class IncidentStatus(StrEnum):
    """Conservative incident-state vocabulary for receipt context."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IncidentStatusContext:
    """Typed incident and optional status-transition context."""

    incident_id: str
    status: IncidentStatus
    previous_status: IncidentStatus | None = None
    summary: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        incident_id = self.incident_id.strip()
        if not incident_id:
            raise ValueError("incident_id cannot be blank")
        status = (
            self.status if isinstance(self.status, IncidentStatus) else IncidentStatus(self.status)
        )
        previous_status = self.previous_status
        if previous_status is not None and not isinstance(previous_status, IncidentStatus):
            previous_status = IncidentStatus(previous_status)
        object.__setattr__(self, "incident_id", incident_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "previous_status", previous_status)

    def to_dict(self) -> JsonObject:
        return {
            "incidentId": self.incident_id,
            "status": self.status.value,
            "previousStatus": (
                self.previous_status.value if self.previous_status is not None else None
            ),
            "summary": self.summary,
            "source": self.source,
        }


@dataclass(frozen=True)
class WritebackRequest:
    """One canonical DataHub mutation request."""

    call: MutationCall

    @property
    def digest(self) -> str:
        return self.call.digest

    @classmethod
    def save_document(
        cls,
        *,
        document_type: str,
        title: str,
        content: str,
        idempotency_key: str,
        urn: str | None = None,
        topics: Sequence[str] | None = None,
        related_documents: Sequence[str] | None = None,
        related_assets: Sequence[str] | None = None,
    ) -> WritebackRequest:
        arguments: JsonObject = {
            "document_type": document_type,
            "title": title,
            "content": content,
        }
        if urn is not None:
            arguments["urn"] = urn
        if topics is not None:
            arguments["topics"] = list(topics)
        if related_documents is not None:
            arguments["related_documents"] = list(related_documents)
        if related_assets is not None:
            arguments["related_assets"] = list(related_assets)
        return cls(MutationCall(MutationTool.SAVE_DOCUMENT, arguments, idempotency_key))

    @classmethod
    def add_tags(
        cls,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        column_paths: Sequence[str | None] | None = None,
    ) -> WritebackRequest:
        return cls._tags(
            MutationTool.ADD_TAGS,
            tag_urns=tag_urns,
            entity_urns=entity_urns,
            idempotency_key=idempotency_key,
            column_paths=column_paths,
        )

    @classmethod
    def remove_tags(
        cls,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        column_paths: Sequence[str | None] | None = None,
    ) -> WritebackRequest:
        return cls._tags(
            MutationTool.REMOVE_TAGS,
            tag_urns=tag_urns,
            entity_urns=entity_urns,
            idempotency_key=idempotency_key,
            column_paths=column_paths,
        )

    @classmethod
    def _tags(
        cls,
        tool: MutationTool,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        column_paths: Sequence[str | None] | None,
    ) -> WritebackRequest:
        arguments: JsonObject = {
            "tag_urns": list(tag_urns),
            "entity_urns": list(entity_urns),
        }
        if column_paths is not None:
            arguments["column_paths"] = list(column_paths)
        return cls(MutationCall(tool, arguments, idempotency_key))

    @classmethod
    def update_description(
        cls,
        *,
        entity_urn: str,
        operation: str,
        idempotency_key: str,
        description: str | None = None,
        column_path: str | None = None,
    ) -> WritebackRequest:
        arguments: JsonObject = {"entity_urn": entity_urn, "operation": operation}
        if description is not None:
            arguments["description"] = description
        if column_path is not None:
            arguments["column_path"] = column_path
        return cls(MutationCall(MutationTool.UPDATE_DESCRIPTION, arguments, idempotency_key))

    @classmethod
    def set_structured_properties(
        cls,
        *,
        property_values: Mapping[str, Sequence[str | float | int]],
        entity_urns: Sequence[str],
        idempotency_key: str,
    ) -> WritebackRequest:
        return cls(
            MutationCall(
                MutationTool.ADD_STRUCTURED_PROPERTIES,
                {
                    "property_values": {
                        urn: list(values) for urn, values in property_values.items()
                    },
                    "entity_urns": list(entity_urns),
                },
                idempotency_key,
            )
        )

    add_structured_properties = set_structured_properties

    @classmethod
    def remove_structured_properties(
        cls,
        *,
        property_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
    ) -> WritebackRequest:
        return cls(
            MutationCall(
                MutationTool.REMOVE_STRUCTURED_PROPERTIES,
                {
                    "property_urns": list(property_urns),
                    "entity_urns": list(entity_urns),
                },
                idempotency_key,
            )
        )


class DeterministicPolicyGate:
    """Fail-closed policy that mints exact-call, process-local authorizations."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        allowlisted_tools: Iterable[MutationTool | str] = OFFICIAL_MUTATION_TOOLS,
        allowed_urn_prefixes: Sequence[str] = (
            "urn:li:dataset:",
            "urn:li:document:",
        ),
        allow_document_creation: bool = True,
        policy_version: str = "ledgerlens-datahub-writeback/v1",
    ) -> None:
        self.enabled = enabled
        self.allowlisted_tools = frozenset(
            value if isinstance(value, MutationTool) else MutationTool(value)
            for value in allowlisted_tools
        )
        self.allowed_urn_prefixes = tuple(allowed_urn_prefixes)
        self.allow_document_creation = allow_document_creation
        self.policy_version = policy_version
        self._issuer = object()

    def authorize(
        self,
        request: WritebackRequest,
        *,
        actor: str,
        reason: str,
        preview: bool = False,
        incident_context: IncidentStatusContext | None = None,
    ) -> MutationAuthorization:
        """Evaluate deterministic policy and mint a typed authorization."""

        actor = redact_text(actor.strip())
        reason = redact_text(reason.strip())
        if not actor:
            raise PolicyDeniedError("write-back actor cannot be blank")
        if not reason:
            raise PolicyDeniedError("write-back reason cannot be blank")
        if not preview and not self.enabled:
            raise PolicyDeniedError("DataHub write-back is disabled")
        if request.call.tool not in self.allowlisted_tools:
            raise PolicyDeniedError(f"mutation tool is not allowlisted: {request.call.tool.value}")
        self._validate_scope(request.call)
        incident_payload = incident_context.to_dict() if incident_context else None
        authorization_id = _digest(
            {
                "policyVersion": self.policy_version,
                "actor": actor,
                "reason": reason,
                "tool": request.call.tool.value,
                "idempotencyKey": request.call.idempotency_key,
                "callDigest": request.call.digest,
                "previewOnly": preview,
                "incidentContext": incident_payload,
            }
        )
        return MutationAuthorization(
            authorization_id=authorization_id,
            policy_version=self.policy_version,
            actor=actor,
            reason=reason,
            tool=request.call.tool,
            idempotency_key=request.call.idempotency_key,
            call_digest=request.call.digest,
            preview_only=preview,
            incident_context=incident_payload,
            _issuer=self._issuer,
        )

    def verify(
        self,
        authorization: MutationAuthorization,
        call: MutationCall,
        *,
        preview: bool = False,
    ) -> None:
        """Verify gate provenance, scope, exact call binding, and mode."""

        if not isinstance(authorization, MutationAuthorization):
            raise MCPMutationAuthorizationError("typed mutation authorization is required")
        if authorization._issuer is not self._issuer:
            raise MCPMutationAuthorizationError(
                "authorization was not issued by this deterministic policy gate"
            )
        if authorization.policy_version != self.policy_version:
            raise MCPMutationAuthorizationError("authorization policy version does not match")
        if authorization.tool is not call.tool:
            raise MCPMutationAuthorizationError("authorization tool does not match request")
        if authorization.idempotency_key != call.idempotency_key:
            raise MCPMutationAuthorizationError(
                "authorization idempotency key does not match request"
            )
        if authorization.call_digest != call.digest:
            raise MCPMutationAuthorizationError("authorization is not bound to this request")
        if preview:
            if not authorization.preview_only and not self.enabled:
                raise MCPMutationAuthorizationError(
                    "live authorization cannot be used while write-back is disabled"
                )
        else:
            if authorization.preview_only:
                raise MCPMutationAuthorizationError(
                    "preview-only authorization cannot execute a mutation"
                )
            if not self.enabled:
                raise MCPMutationAuthorizationError("DataHub write-back is disabled")
        if call.tool not in self.allowlisted_tools:
            raise MCPMutationAuthorizationError("authorization tool is no longer allowlisted")
        self._validate_scope(call)

    def _validate_scope(self, call: MutationCall) -> None:
        if (
            call.tool is MutationTool.SAVE_DOCUMENT
            and not call.target_urns
            and not self.allow_document_creation
        ):
            raise PolicyDeniedError("new DataHub document creation is not allowed")
        scoped_urns = list(call.target_urns)
        if call.tool is MutationTool.SAVE_DOCUMENT:
            for key in ("related_documents", "related_assets"):
                values = call.arguments.get(key)
                if isinstance(values, list):
                    scoped_urns.extend(value for value in values if isinstance(value, str))
        invalid = [
            urn
            for urn in scoped_urns
            if not any(urn.startswith(prefix) for prefix in self.allowed_urn_prefixes)
        ]
        if invalid:
            raise PolicyDeniedError(
                "mutation target is outside the allowed URN scope: " + ", ".join(invalid)
            )


class SnapshotReader(Protocol):
    """Injected read path used to capture before/after state."""

    def capture(self, urns: Sequence[str]) -> Mapping[str, Any]:
        """Return sanitized-source state for the requested URNs."""


class MCPStateSnapshotReader:
    """Snapshot adapter that reuses the existing read-only MCP client unchanged."""

    def __init__(self, client: DataHubMCPClient) -> None:
        self._client = client

    def capture(self, urns: Sequence[str]) -> Mapping[str, Any]:
        return {"entities": self._client.get_entities(urns)}


@dataclass(frozen=True)
class SnapshotReceipt:
    phase: str
    captured_at: str
    urns: tuple[str, ...]
    available: bool
    source: str
    state: Any = None
    digest: str | None = None
    limitation: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            "phase": self.phase,
            "capturedAt": self.captured_at,
            "urns": list(self.urns),
            "available": self.available,
            "source": self.source,
            "state": redact_sensitive(self.state),
            "digest": self.digest,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class CompensatingAction:
    tool: MutationTool
    arguments: Mapping[str, Any]
    idempotency_key: str
    requires_fresh_authorization: bool = True

    def to_dict(self) -> JsonObject:
        return {
            "tool": self.tool.value,
            "arguments": redact_sensitive(dict(self.arguments)),
            "idempotencyKey": self.idempotency_key,
            "requiresFreshAuthorization": self.requires_fresh_authorization,
        }


@dataclass(frozen=True)
class RollbackMetadata:
    available: bool
    exact: bool
    actions: tuple[CompensatingAction, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> JsonObject:
        return {
            "available": self.available,
            "exact": self.exact,
            "actions": [action.to_dict() for action in self.actions],
            "limitations": list(self.limitations),
        }


class WritebackStatus(StrEnum):
    PREVIEW = "preview"
    APPLIED = "applied"
    FAILED = "failed"


@dataclass(frozen=True)
class WritebackReceipt:
    receipt_id: str
    status: WritebackStatus
    tool: MutationTool
    idempotency_key: str
    request_digest: str
    preview: bool
    replayed: bool
    started_at: str
    completed_at: str
    authorization: Mapping[str, Any]
    request_arguments: Mapping[str, Any]
    before: SnapshotReceipt
    after: SnapshotReceipt
    rollback: RollbackMetadata
    result: Any = None
    error: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            "receiptId": self.receipt_id,
            "status": self.status.value,
            "tool": self.tool.value,
            "idempotencyKey": self.idempotency_key,
            "requestDigest": self.request_digest,
            "preview": self.preview,
            "replayed": self.replayed,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "authorization": redact_sensitive(dict(self.authorization)),
            "requestArguments": redact_sensitive(dict(self.request_arguments)),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "rollback": self.rollback.to_dict(),
            "result": redact_sensitive(self.result),
            "error": redact_text(self.error) if self.error else None,
        }


@dataclass(frozen=True)
class IdempotencyRecord:
    request_digest: str
    receipt: WritebackReceipt


class IdempotencyStore(Protocol):
    def get(self, key: str) -> IdempotencyRecord | None:
        """Return a previously completed request."""

    def put(self, key: str, record: IdempotencyRecord) -> None:
        """Persist a completed request."""


class InMemoryIdempotencyStore:
    """Thread-safe deterministic store suitable for tests and single processes."""

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> IdempotencyRecord | None:
        with self._lock:
            return self._records.get(key)

    def put(self, key: str, record: IdempotencyRecord) -> None:
        with self._lock:
            self._records[key] = record


class DataHubWritebackService:
    """Previewable, idempotent write-back with before/after receipts."""

    def __init__(
        self,
        mutation_client: MCPMutationClient,
        policy_gate: DeterministicPolicyGate,
        *,
        snapshot_reader: SnapshotReader | None = None,
        idempotency_store: IdempotencyStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.mutations = mutation_client
        self.policy = policy_gate
        self.snapshot_reader = snapshot_reader
        self.idempotency_store = idempotency_store or InMemoryIdempotencyStore()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()

    def execute(
        self,
        request: WritebackRequest,
        *,
        authorization: MutationAuthorization,
        preview: bool = False,
    ) -> WritebackReceipt:
        """Preview or execute one authorized request and return its audit receipt."""

        with self._lock:
            self.policy.verify(authorization, request.call, preview=preview)
            store_key = f"{'preview' if preview else 'execute'}:{request.call.idempotency_key}"
            previous = self.idempotency_store.get(store_key)
            if previous is not None:
                if previous.request_digest != request.digest:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for a different request"
                    )
                replayed = replace(previous.receipt, replayed=True)
                if replayed.status is WritebackStatus.FAILED:
                    raise WritebackExecutionError(replayed)
                return replayed

            started_at = self._now()
            before = self._capture("before", request.call.target_urns)
            rollback = _rollback_metadata(request.call, before)

            if preview:
                after = self._projected_after(request.call)
                receipt = self._receipt(
                    request,
                    authorization=authorization,
                    status=WritebackStatus.PREVIEW,
                    preview=True,
                    started_at=started_at,
                    before=before,
                    after=after,
                    rollback=rollback,
                    result={"planned": True, "transportCalled": False},
                )
                self.idempotency_store.put(
                    store_key,
                    IdempotencyRecord(request_digest=request.digest, receipt=receipt),
                )
                return receipt

            try:
                result = self.mutations.call_tool(
                    request.call,
                    authorization=authorization,
                )
                after_urns = _after_urns(request.call, result)
                after = self._capture("after", after_urns)
                receipt = self._receipt(
                    request,
                    authorization=authorization,
                    status=WritebackStatus.APPLIED,
                    preview=False,
                    started_at=started_at,
                    before=before,
                    after=after,
                    rollback=rollback,
                    result=result,
                )
            except Exception as exc:
                after = self._capture("after-failure", request.call.target_urns)
                receipt = self._receipt(
                    request,
                    authorization=authorization,
                    status=WritebackStatus.FAILED,
                    preview=False,
                    started_at=started_at,
                    before=before,
                    after=after,
                    rollback=rollback,
                    error=redact_text(str(exc)),
                )
                self.idempotency_store.put(
                    store_key,
                    IdempotencyRecord(request_digest=request.digest, receipt=receipt),
                )
                raise WritebackExecutionError(receipt) from exc

            self.idempotency_store.put(
                store_key,
                IdempotencyRecord(request_digest=request.digest, receipt=receipt),
            )
            return receipt

    def _capture(self, phase: str, urns: Sequence[str]) -> SnapshotReceipt:
        captured_at = self._now()
        normalized_urns = tuple(dict.fromkeys(urns))
        if not normalized_urns:
            return SnapshotReceipt(
                phase=phase,
                captured_at=captured_at,
                urns=(),
                available=False,
                source="none",
                limitation="no target URN was available for this phase",
            )
        if self.snapshot_reader is None:
            return SnapshotReceipt(
                phase=phase,
                captured_at=captured_at,
                urns=normalized_urns,
                available=False,
                source="not-configured",
                limitation="snapshot reader was not configured",
            )
        try:
            state = redact_sensitive(self.snapshot_reader.capture(normalized_urns))
            return SnapshotReceipt(
                phase=phase,
                captured_at=captured_at,
                urns=normalized_urns,
                available=True,
                source=type(self.snapshot_reader).__name__,
                state=state,
                digest=_digest(state),
            )
        except Exception as exc:
            return SnapshotReceipt(
                phase=phase,
                captured_at=captured_at,
                urns=normalized_urns,
                available=False,
                source=type(self.snapshot_reader).__name__,
                limitation=redact_text(str(exc)),
            )

    def _projected_after(self, call: MutationCall) -> SnapshotReceipt:
        state = {
            "projected": True,
            "tool": call.tool.value,
            "arguments": redact_sensitive(dict(call.arguments)),
        }
        return SnapshotReceipt(
            phase="after-preview",
            captured_at=self._now(),
            urns=call.target_urns,
            available=True,
            source="deterministic-preview",
            state=state,
            digest=_digest(state),
            limitation="projected state only; no MCP mutation was executed",
        )

    def _receipt(
        self,
        request: WritebackRequest,
        *,
        authorization: MutationAuthorization,
        status: WritebackStatus,
        preview: bool,
        started_at: str,
        before: SnapshotReceipt,
        after: SnapshotReceipt,
        rollback: RollbackMetadata,
        result: Any = None,
        error: str | None = None,
    ) -> WritebackReceipt:
        completed_at = self._now()
        receipt_id = _digest(
            {
                "requestDigest": request.digest,
                "authorizationId": authorization.authorization_id,
                "status": status.value,
                "preview": preview,
                "beforeDigest": before.digest,
                "afterDigest": after.digest,
                "error": error,
            }
        )
        return WritebackReceipt(
            receipt_id=receipt_id,
            status=status,
            tool=request.call.tool,
            idempotency_key=request.call.idempotency_key,
            request_digest=request.digest,
            preview=preview,
            replayed=False,
            started_at=started_at,
            completed_at=completed_at,
            authorization=authorization.public_summary(),
            request_arguments=redact_sensitive(dict(request.call.arguments)),
            before=before,
            after=after,
            rollback=rollback,
            result=redact_sensitive(result),
            error=redact_text(error) if error else None,
        )

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise TypeError("clock must return datetime")
        return value.astimezone(UTC).isoformat()


def _rollback_metadata(call: MutationCall, before: SnapshotReceipt) -> RollbackMetadata:
    builder = {
        MutationTool.ADD_TAGS: _tag_rollback,
        MutationTool.REMOVE_TAGS: _tag_rollback,
        MutationTool.UPDATE_DESCRIPTION: _description_rollback,
        MutationTool.ADD_STRUCTURED_PROPERTIES: _structured_rollback,
        MutationTool.REMOVE_STRUCTURED_PROPERTIES: _structured_rollback,
        MutationTool.SAVE_DOCUMENT: _document_rollback,
    }[call.tool]
    return builder(call, before)


def _tag_rollback(call: MutationCall, before: SnapshotReceipt) -> RollbackMetadata:
    inverse = (
        MutationTool.REMOVE_TAGS if call.tool is MutationTool.ADD_TAGS else MutationTool.ADD_TAGS
    )
    raw_tags = call.arguments.get("tag_urns")
    requested_tags = (
        {value for value in raw_tags if isinstance(value, str)}
        if isinstance(raw_tags, list)
        else set()
    )
    column_paths = call.arguments.get("column_paths")
    has_column_targets = isinstance(column_paths, list) and any(column_paths)

    if before.available and not has_column_targets:
        actions: list[CompensatingAction] = []
        complete = True
        for urn in call.target_urns:
            existing_tags = _extract_tags(_entity_state(before.state, urn))
            if existing_tags is None:
                complete = False
                break
            affected_tags = (
                requested_tags - existing_tags
                if call.tool is MutationTool.ADD_TAGS
                else requested_tags & existing_tags
            )
            if affected_tags:
                actions.append(
                    CompensatingAction(
                        tool=inverse,
                        arguments={
                            "tag_urns": sorted(affected_tags),
                            "entity_urns": [urn],
                        },
                        idempotency_key=(f"{call.idempotency_key}:rollback:{len(actions) + 1}"),
                    )
                )
        if complete:
            return RollbackMetadata(
                available=True,
                exact=True,
                actions=tuple(actions),
            )

    action = CompensatingAction(
        tool=inverse,
        arguments=dict(call.arguments),
        idempotency_key=f"{call.idempotency_key}:rollback:1",
    )
    return RollbackMetadata(
        available=True,
        exact=False,
        actions=(action,),
        limitations=(
            "inverse tag action may not exactly restore pre-existing membership "
            "because the before snapshot was unavailable, incomplete, or column-scoped",
        ),
    )


def _description_rollback(
    call: MutationCall,
    before: SnapshotReceipt,
) -> RollbackMetadata:
    urn = call.target_urns[0]
    entity = _entity_state(before.state, urn) if before.available else None
    known, description = _extract_description(entity, call.arguments.get("column_path"))
    if not known:
        return RollbackMetadata(
            available=False,
            exact=False,
            limitations=("previous description was not captured",),
        )
    arguments: JsonObject = {
        "entity_urn": urn,
        "operation": "replace" if description else "remove",
    }
    if description:
        arguments["description"] = description
    column_path = call.arguments.get("column_path")
    if isinstance(column_path, str):
        arguments["column_path"] = column_path
    return RollbackMetadata(
        available=True,
        exact=True,
        actions=(
            CompensatingAction(
                tool=MutationTool.UPDATE_DESCRIPTION,
                arguments=arguments,
                idempotency_key=f"{call.idempotency_key}:rollback:1",
            ),
        ),
    )


def _structured_rollback(
    call: MutationCall,
    before: SnapshotReceipt,
) -> RollbackMetadata:
    if not before.available:
        if call.tool is MutationTool.ADD_STRUCTURED_PROPERTIES:
            property_values = call.arguments.get("property_values")
            property_urns = list(property_values) if isinstance(property_values, Mapping) else []
            return RollbackMetadata(
                available=bool(property_urns),
                exact=False,
                actions=(
                    CompensatingAction(
                        tool=MutationTool.REMOVE_STRUCTURED_PROPERTIES,
                        arguments={
                            "property_urns": property_urns,
                            "entity_urns": list(call.target_urns),
                        },
                        idempotency_key=f"{call.idempotency_key}:rollback:1",
                    ),
                )
                if property_urns
                else (),
                limitations=(
                    "removing assigned properties may also remove values that existed "
                    "before the request",
                ),
            )
        return RollbackMetadata(
            available=False,
            exact=False,
            limitations=("removed structured-property values were not captured",),
        )

    property_names: Sequence[str]
    if call.tool is MutationTool.ADD_STRUCTURED_PROPERTIES:
        raw_values = call.arguments.get("property_values")
        property_names = list(raw_values) if isinstance(raw_values, Mapping) else []
    else:
        raw_names = call.arguments.get("property_urns")
        property_names = raw_names if isinstance(raw_names, list) else []

    actions: list[CompensatingAction] = []
    complete = True
    for urn in call.target_urns:
        properties = _extract_structured_properties(_entity_state(before.state, urn))
        if properties is None:
            complete = False
            continue
        restore: dict[str, list[str | float | int]] = {}
        remove: list[str] = []
        for property_urn in property_names:
            values = properties.get(property_urn)
            if values is None:
                if call.tool is MutationTool.ADD_STRUCTURED_PROPERTIES:
                    remove.append(property_urn)
            else:
                restore[property_urn] = values

        if remove:
            actions.append(
                CompensatingAction(
                    tool=MutationTool.REMOVE_STRUCTURED_PROPERTIES,
                    arguments={
                        "property_urns": sorted(set(remove)),
                        "entity_urns": [urn],
                    },
                    idempotency_key=(f"{call.idempotency_key}:rollback:{len(actions) + 1}"),
                )
            )
        if restore:
            actions.append(
                CompensatingAction(
                    tool=MutationTool.ADD_STRUCTURED_PROPERTIES,
                    arguments={
                        "property_values": restore,
                        "entity_urns": [urn],
                    },
                    idempotency_key=(f"{call.idempotency_key}:rollback:{len(actions) + 1}"),
                )
            )
    exact = complete
    return RollbackMetadata(
        available=bool(actions) or exact,
        exact=exact,
        actions=tuple(actions),
        limitations=() if exact else ("before snapshot did not expose all property values",),
    )


def _document_rollback(call: MutationCall, before: SnapshotReceipt) -> RollbackMetadata:
    if not call.target_urns:
        return RollbackMetadata(
            available=False,
            exact=False,
            limitations=(
                "the official allowlisted MCP surface has no document deletion tool "
                "for compensating a new save_document call",
            ),
        )
    urn = call.target_urns[0]
    document = _entity_state(before.state, urn) if before.available else None
    payload = _extract_document_payload(document, urn)
    if payload is None:
        return RollbackMetadata(
            available=False,
            exact=False,
            limitations=("previous document content was not captured",),
        )
    return RollbackMetadata(
        available=True,
        exact=True,
        actions=(
            CompensatingAction(
                tool=MutationTool.SAVE_DOCUMENT,
                arguments=payload,
                idempotency_key=f"{call.idempotency_key}:rollback:1",
            ),
        ),
    )


def _after_urns(call: MutationCall, result: Any) -> tuple[str, ...]:
    if call.target_urns:
        return call.target_urns
    if isinstance(result, Mapping):
        urn = result.get("urn")
        if isinstance(urn, str) and urn:
            return (urn,)
    return ()


def _entity_state(state: Any, urn: str) -> Mapping[str, Any] | None:
    if not isinstance(state, Mapping):
        return None
    direct = state.get(urn)
    if isinstance(direct, Mapping):
        return direct
    if state.get("urn") == urn:
        return state
    entities = state.get("entities")
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, Mapping) and entity.get("urn") == urn:
                return entity
    if len(state) and "entities" not in state:
        return state
    return None


def _extract_tags(entity: Mapping[str, Any] | None) -> set[str] | None:
    if entity is None:
        return None
    raw = entity.get("tags")
    if isinstance(raw, list):
        tag_values: set[str] = set()
        for item in raw:
            if isinstance(item, str):
                tag_values.add(item)
            elif isinstance(item, Mapping):
                urn = item.get("urn")
                if isinstance(urn, str):
                    tag_values.add(urn)
        return tag_values
    global_tags = entity.get("globalTags")
    if isinstance(global_tags, Mapping) and isinstance(global_tags.get("tags"), list):
        global_tag_values: set[str] = set()
        for item in global_tags["tags"]:
            if not isinstance(item, Mapping):
                continue
            tag = item.get("tag")
            if isinstance(tag, Mapping) and isinstance(tag.get("urn"), str):
                global_tag_values.add(tag["urn"])
        return global_tag_values
    return None


def _extract_description(
    entity: Mapping[str, Any] | None,
    column_path: Any,
) -> tuple[bool, str | None]:
    if entity is None:
        return False, None
    if isinstance(column_path, str):
        schema = entity.get("schemaMetadata")
        fields = schema.get("fields") if isinstance(schema, Mapping) else None
        if isinstance(fields, list):
            for item in fields:
                if isinstance(item, Mapping) and item.get("fieldPath") == column_path:
                    value = item.get("description")
                    return True, value if isinstance(value, str) else None
        return False, None
    for container in (entity, entity.get("editableProperties"), entity.get("properties")):
        if isinstance(container, Mapping) and "description" in container:
            value = container.get("description")
            return True, value if isinstance(value, str) else None
    return False, None


def _extract_structured_properties(
    entity: Mapping[str, Any] | None,
) -> dict[str, list[str | float | int]] | None:
    if entity is None:
        return None
    raw = entity.get("structured_properties", entity.get("structuredProperties"))
    if isinstance(raw, Mapping):
        normalized: dict[str, list[str | float | int]] = {}
        for key, values in raw.items():
            if not isinstance(key, str):
                continue
            candidates = values if isinstance(values, list) else [values]
            normalized[key] = [
                value
                for value in candidates
                if isinstance(value, (str, float, int)) and not isinstance(value, bool)
            ]
        return normalized
    if isinstance(raw, list):
        normalized = {}
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            property_urn = item.get("urn") or item.get("propertyUrn")
            values = item.get("values")
            if isinstance(property_urn, str) and isinstance(values, list):
                normalized[property_urn] = [
                    value
                    for value in values
                    if isinstance(value, (str, float, int)) and not isinstance(value, bool)
                ]
        return normalized
    return None


def _extract_document_payload(
    entity: Mapping[str, Any] | None,
    urn: str,
) -> JsonObject | None:
    if entity is None:
        return None
    title = entity.get("title") or entity.get("name")
    content = entity.get("content") or entity.get("text") or entity.get("description")
    document_type = entity.get("document_type") or entity.get("subtype") or entity.get("type")
    if not all(isinstance(value, str) and value for value in (title, content, document_type)):
        return None
    payload: JsonObject = {
        "urn": urn,
        "document_type": document_type,
        "title": title,
        "content": content,
    }
    for key in ("topics", "related_documents", "related_assets"):
        value = entity.get(key)
        if isinstance(value, list):
            payload[key] = value
    return payload


def _digest(value: Any) -> str:
    canonical = json.dumps(
        redact_sensitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


ControlledDataHubWriteback = DataHubWritebackService
DataHubWriteback = DataHubWritebackService
