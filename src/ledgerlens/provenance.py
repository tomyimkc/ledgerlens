"""Merge DataHub context without confusing ingestion audit with validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ledgerlens.datahub_client import AuditMetadata


class ProvenanceError(ValueError):
    """Base provenance normalization error."""


class ProvenanceConflictError(ProvenanceError):
    """Raised when sources disagree on safety-critical metadata."""


@dataclass(frozen=True)
class ProvenanceRecord:
    urn: str
    entity_type: str | None
    title: str | None
    status: str | None
    owners: tuple[str, ...]
    evidence_references: tuple[str, ...]
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    candidate_only: bool
    can_claim_agi: bool
    scientific_validation_status: str
    datahub_ingestion_time_ms: int | None
    datahub_ingestion_actor: str | None
    datahub_run_ids: tuple[str, ...]
    missing_metadata: tuple[str, ...]
    custom_properties: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        ingestion_iso = None
        if self.datahub_ingestion_time_ms is not None:
            ingestion_iso = datetime.fromtimestamp(
                self.datahub_ingestion_time_ms / 1000,
                tz=UTC,
            ).isoformat()
        return {
            "urn": self.urn,
            "entityType": self.entity_type,
            "title": self.title,
            "status": self.status,
            "owners": list(self.owners),
            "evidenceReferences": list(self.evidence_references),
            "supersedes": list(self.supersedes),
            "supersededBy": list(self.superseded_by),
            "candidateOnly": self.candidate_only,
            "canClaimAGI": self.can_claim_agi,
            "scientificValidation": {
                "status": self.scientific_validation_status,
                "source": "declared finding metadata",
                "independentlyValidatedByLedgerLens": False,
            },
            "datahubIngestionAudit": {
                "timeMs": self.datahub_ingestion_time_ms,
                "time": ingestion_iso,
                "actor": self.datahub_ingestion_actor,
                "runIds": list(self.datahub_run_ids),
                "meaning": (
                    "DataHub metadata ingestion/observation time; not scientific validation time"
                ),
            },
            "missingMetadata": list(self.missing_metadata),
            "customProperties": dict(self.custom_properties),
        }


def merge_provenance(
    mcp_context: Mapping[str, Any],
    *,
    graphql_entity: Mapping[str, Any] | None = None,
    audit_metadata: AuditMetadata | None = None,
) -> ProvenanceRecord:
    """Merge read-only sources and fail closed on safety-critical conflicts."""

    mcp_urn = _optional_string(mcp_context.get("urn"))
    graph_urn = _optional_string(graphql_entity.get("urn")) if graphql_entity else None
    audit_urn = audit_metadata.urn if audit_metadata else None
    urns = {item for item in (mcp_urn, graph_urn, audit_urn) if item}
    if not urns:
        raise ProvenanceError("No entity URN was supplied")
    if len(urns) != 1:
        raise ProvenanceConflictError(f"Entity URNs conflict: {sorted(urns)}")
    urn = next(iter(urns))

    mcp_properties = extract_custom_properties(mcp_context)
    graph_properties = extract_custom_properties(graphql_entity or {})
    properties = _merge_properties(mcp_properties, graph_properties)

    candidate_values = _source_values(
        "candidateOnly", mcp_context, graphql_entity, mcp_properties, graph_properties
    )
    if any(_to_bool(value) is False for value in candidate_values):
        raise ProvenanceConflictError("candidateOnly must not be false")
    candidate_only = True

    agi_values = _source_values(
        "canClaimAGI", mcp_context, graphql_entity, mcp_properties, graph_properties
    )
    if any(_to_bool(value) is True for value in agi_values):
        raise ProvenanceConflictError("canClaimAGI must not be true")
    can_claim_agi = False

    status = _consistent_scalar(
        "status",
        _source_values("status", mcp_context, graphql_entity, mcp_properties, graph_properties),
    )
    title = _first_string(
        mcp_context.get("name"),
        mcp_context.get("title"),
        _nested(mcp_context, "properties", "name"),
        graphql_entity.get("name") if graphql_entity else None,
        _nested(graphql_entity or {}, "properties", "name"),
        properties.get("title"),
    )
    entity_type = _first_string(
        mcp_context.get("type"),
        graphql_entity.get("type") if graphql_entity else None,
    )

    owners = _merge_owners(mcp_context, graphql_entity or {}, properties)
    evidence = extract_evidence_references(mcp_context, graphql_entity or {}, properties)
    supersedes = _to_string_tuple(properties.get("supersedes") or mcp_context.get("supersedes"))
    superseded_by = _to_string_tuple(
        properties.get("supersededBy")
        or properties.get("superseded_by")
        or mcp_context.get("supersededBy")
    )

    validation_status = _consistent_scalar(
        "scientificValidationStatus",
        _source_values(
            "scientificValidationStatus",
            mcp_context,
            graphql_entity,
            mcp_properties,
            graph_properties,
        ),
    )
    if validation_status is None:
        validation_status = "unverified"
    validation_status = validation_status.lower()
    if validation_status in {"validated", "proven", "confirmed"}:
        # DataHub and this adapter only carry claims. They do not independently
        # establish scientific validity.
        validation_status = f"declared-{validation_status}"

    ingestion_time = audit_metadata.latest_ingestion_time_ms if audit_metadata else None
    actor = None
    run_ids: list[str] = []
    if audit_metadata:
        sorted_stamps = sorted(
            (stamp for stamp in audit_metadata.audit_stamps if stamp.time_ms is not None),
            key=lambda stamp: stamp.time_ms or -1,
            reverse=True,
        )
        actor = next((stamp.actor for stamp in sorted_stamps if stamp.actor), None)
        for metadata in audit_metadata.system_metadata.values():
            run_id = _optional_string(metadata.get("runId"))
            if run_id and run_id not in run_ids:
                run_ids.append(run_id)

    missing: list[str] = []
    if status is None:
        missing.append("status")
    if not owners:
        missing.append("owner")
    if not evidence:
        missing.append("evidenceReferences")
    if audit_metadata is None or ingestion_time is None:
        missing.append("datahubIngestionAudit")
    if validation_status == "unverified":
        missing.append("scientificValidation")

    return ProvenanceRecord(
        urn=urn,
        entity_type=entity_type,
        title=title,
        status=status,
        owners=owners,
        evidence_references=evidence,
        supersedes=supersedes,
        superseded_by=superseded_by,
        candidate_only=candidate_only,
        can_claim_agi=can_claim_agi,
        scientific_validation_status=validation_status,
        datahub_ingestion_time_ms=ingestion_time,
        datahub_ingestion_actor=actor,
        datahub_run_ids=tuple(run_ids),
        missing_metadata=tuple(missing),
        custom_properties=properties,
    )


def extract_custom_properties(entity: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        entity.get("customProperties"),
        _nested(entity, "properties", "customProperties"),
        _nested(entity, "raw", "customProperties"),
        _nested(entity, "raw", "entity", "properties", "customProperties"),
    ]
    result: dict[str, Any] = {}
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            result.update(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                if not isinstance(item, Mapping):
                    continue
                key = item.get("key")
                if isinstance(key, str):
                    result[key] = item.get("value")
    for key, value in tuple(result.items()):
        if not key.startswith("ledgerlens."):
            continue
        alias = key.removeprefix("ledgerlens.")
        result.setdefault(alias, value)
    if "supersedesIds" in result:
        result.setdefault("supersedes", result["supersedesIds"])
    return result


def extract_evidence_references(*sources: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    keys = {
        "evidence",
        "evidenceReference",
        "evidenceReferences",
        "evidenceReceipt",
        "evidenceReceipts",
        "evidence_reference",
        "evidence_references",
    }
    for source in sources:
        properties = extract_custom_properties(source)
        combined = {**source, **properties}
        for key in keys:
            if key not in combined:
                continue
            for reference in _evidence_strings(combined[key]):
                if reference and reference not in values:
                    values.append(reference)
    return tuple(values)


def _evidence_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith(("[", "{")):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if decoded is not None:
                return _evidence_strings(decoded)
        return _to_string_tuple(stripped)
    if isinstance(value, Mapping):
        for key in ("reference", "uri", "url", "path"):
            reference = value.get(key)
            if isinstance(reference, str) and reference.strip():
                return (reference.strip(),)
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        references: list[str] = []
        for item in value:
            for reference in _evidence_strings(item):
                if reference not in references:
                    references.append(reference)
        return tuple(references)
    return ()


def _merge_properties(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(left)
    for key, value in right.items():
        if key in result and _canonical(result[key]) != _canonical(value):
            if key in {
                "status",
                "candidateOnly",
                "canClaimAGI",
                "scientificValidationStatus",
            }:
                raise ProvenanceConflictError(f"Conflicting custom property: {key}")
        else:
            result[key] = value
    return result


def _source_values(
    key: str,
    mcp: Mapping[str, Any],
    graph: Mapping[str, Any] | None,
    mcp_properties: Mapping[str, Any],
    graph_properties: Mapping[str, Any],
) -> list[Any]:
    values: list[Any] = []
    for source in (mcp, graph or {}, mcp_properties, graph_properties):
        if key not in source:
            continue
        value = source[key]
        if value in (None, "") or isinstance(value, (Mapping, list, tuple, set)):
            continue
        values.append(value)
    return values


def _consistent_scalar(name: str, values: Sequence[Any]) -> str | None:
    normalized = {
        str(value).strip().lower() for value in values if value is not None and str(value).strip()
    }
    if len(normalized) > 1:
        raise ProvenanceConflictError(f"Conflicting {name}: {sorted(normalized)}")
    return next(iter(normalized)) if normalized else None


def _merge_owners(
    mcp: Mapping[str, Any],
    graph: Mapping[str, Any],
    properties: Mapping[str, Any],
) -> tuple[str, ...]:
    owners: list[str] = []
    for direct in (
        mcp.get("owners"),
        mcp.get("owner"),
        graph.get("owners"),
        graph.get("owner"),
        properties.get("owner"),
        properties.get("owners"),
    ):
        for owner in _to_string_tuple(direct):
            if owner not in owners:
                owners.append(owner)
    for source in (mcp, graph):
        raw_owners = _nested(source, "ownership", "owners")
        if not isinstance(raw_owners, list):
            continue
        for item in raw_owners:
            if not isinstance(item, Mapping):
                continue
            raw_owner = item.get("owner")
            nested_owner = raw_owner.get("urn") if isinstance(raw_owner, Mapping) else raw_owner
            if isinstance(nested_owner, str) and nested_owner not in owners:
                owners.append(nested_owner)
    return tuple(owners)


def _to_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith(("[", "{")):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if decoded is not None:
                return _to_string_tuple(decoded)
        if stripped.startswith("urn:li:"):
            return (stripped,)
        separators = ("\n", ",")
        items = [stripped]
        for separator in separators:
            if separator in stripped:
                items = [part.strip() for part in stripped.split(separator)]
                break
        return tuple(item for item in items if item)
    if isinstance(value, Mapping):
        return tuple(str(item) for item in value.values() if item not in (None, ""))
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        result: list[str] = []
        for item in value:
            for normalized in _to_string_tuple(item):
                if normalized not in result:
                    result.append(normalized)
        return tuple(result)
    return (str(value),)


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _first_string(*values: Any) -> str | None:
    return next((value for value in values if isinstance(value, str) and value.strip()), None)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _nested(source: Mapping[str, Any], *keys: str) -> Any:
    current: Any = source
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _canonical(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return json.dumps(value, sort_keys=True, default=str)
