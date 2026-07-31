"""Live IncidentContext collection through the official read-only DataHub MCP tools."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from ledgerlens.incident_models import (
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
)
from ledgerlens.mcp_client import DataHubMCPClient


class DataHubContextError(RuntimeError):
    """Raised when live DataHub metadata cannot satisfy the context contract."""


class DataHubMCPContextProvider:
    """Resolve an incident root entity and bounded downstream lineage via MCP."""

    def __init__(
        self,
        client: DataHubMCPClient,
        *,
        max_hops: int = 3,
        max_results: int = 50,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self.max_hops = max_hops
        self.max_results = max_results
        self._clock = clock or (lambda: datetime.now(UTC))

    def __call__(self, incident: Incident) -> IncidentContext:
        if not incident.affected_entities:
            raise DataHubContextError("incident has no affected DataHub entity URN")
        root_urn = incident.affected_entities[0]
        entities = self.client.get_entities([root_urn])
        if len(entities) != 1 or entities[0].get("urn") != root_urn:
            raise DataHubContextError("DataHub MCP did not return the exact root entity")
        entity = entities[0]
        lineage = self.client.get_lineage(
            root_urn,
            direction="downstream",
            max_hops=self.max_hops,
            count=self.max_results,
        )
        downstream_urns = tuple(
            dict.fromkeys(
                str(item["urn"])
                for item in lineage
                if isinstance(item.get("urn"), str) and item["urn"] != root_urn
            )
        )
        properties = _custom_properties(entity)
        owner = _primary_owner(entity)
        runbook = properties.get("ledgerlens.runbookUrl")
        schema = properties.get("ledgerlens.schema")
        if owner is None:
            raise DataHubContextError("root entity has no recorded owner")
        if not runbook:
            raise DataHubContextError("root entity has no recorded runbook")
        facts = (
            _fact(
                "root-asset",
                f"The triggering DataHub entity is {root_urn}.",
                root_urn,
            ),
            _fact(
                "primary-owner",
                f"The recorded primary owner is {owner}.",
                f"{root_urn}#ownership",
            ),
            _fact(
                "blast-radius",
                f"DataHub lineage records {len(downstream_urns)} downstream entities.",
                f"{root_urn}#downstream-lineage",
            ),
            _fact(
                "runbook",
                f"The recorded runbook is {runbook}.",
                f"{root_urn}#runbook",
            ),
            _fact(
                "schema",
                "The entity has recorded schema metadata."
                if schema
                else "The entity has no recorded schema metadata.",
                f"{root_urn}#schema",
            ),
        )
        return IncidentContext(
            context_id=f"datahub-mcp:{incident.incident_id}",
            incident=incident.model_copy(
                update={"affected_entities": (root_urn, *downstream_urns)}
            ),
            collected_at=self._clock(),
            facts=facts,
            metadata={
                "source": "official-datahub-mcp",
                "rootAsset": entity,
                "owner": {"id": owner, "displayName": owner},
                "blastRadiusUrns": list(downstream_urns),
                "runbookUrl": runbook,
                "schema": _json_or_text(schema),
                "claimBoundary": (
                    "DataHub metadata and lineage do not establish causality or recovery."
                ),
            },
        )


def _custom_properties(entity: Mapping[str, Any]) -> dict[str, str]:
    direct = entity.get("customProperties")
    if isinstance(direct, Mapping):
        return {str(key): str(value) for key, value in direct.items()}
    if isinstance(direct, list):
        return _property_list(direct)
    properties = entity.get("properties")
    if isinstance(properties, Mapping):
        nested = properties.get("customProperties")
        if isinstance(nested, Mapping):
            return {str(key): str(value) for key, value in nested.items()}
        if isinstance(nested, list):
            return _property_list(nested)
    return {}


def _property_list(values: list[Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if not isinstance(item, Mapping):
            continue
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and key and value is not None:
            result[key] = str(value)
    return result


def _primary_owner(entity: Mapping[str, Any]) -> str | None:
    ownership = entity.get("ownership")
    if not isinstance(ownership, Mapping):
        return None
    owners = ownership.get("owners")
    if not isinstance(owners, list):
        return None
    for item in owners:
        if not isinstance(item, Mapping):
            continue
        owner = item.get("owner")
        if isinstance(owner, str) and owner:
            return owner
        if isinstance(owner, Mapping) and isinstance(owner.get("urn"), str):
            return str(owner["urn"])
    return None


def _json_or_text(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _fact(fact_id: str, statement: str, reference: str) -> IncidentFact:
    return IncidentFact(
        fact_id=fact_id,
        statement=statement,
        evidence=(
            EvidencePointer(
                reference=reference,
                kind=EvidenceKind.DATAHUB_ENTITY,
            ),
        ),
    )


__all__ = ["DataHubContextError", "DataHubMCPContextProvider"]
