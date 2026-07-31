"""Application runtime for the deterministic multi-domain incident catalog."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

from ledgerlens.incident_models import (
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
    IncidentSeverity,
    IncidentStatus,
    IncidentTrigger,
)

JsonObject = dict[str, Any]
DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "fixtures/incident_commander/catalog.json"


class IncidentCatalogError(ValueError):
    """Raised when catalog data cannot satisfy the incident context contract."""


def load_incident_catalog(path: Path = DEFAULT_CATALOG) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IncidentCatalogError("incident catalog must be a JSON object")
    if payload.get("candidateOnly") is not True or payload.get("canClaimAGI") is not False:
        raise IncidentCatalogError("incident catalog claim boundary is invalid")
    for key in ("assets", "owners", "incidents", "lineage", "scenarios"):
        if not isinstance(payload.get(key), list):
            raise IncidentCatalogError(f"incident catalog {key} must be a list")
    return payload


def incident_from_catalog(catalog: JsonObject, incident_id: str) -> Incident:
    incident = _by_id(catalog["incidents"], incident_id, "incident")
    root_urn = _required_string(incident, "rootAssetUrn")
    affected = (root_urn, *catalog_descendants(catalog, root_urn))
    occurred_at = datetime.fromisoformat(_required_string(incident, "detectedAtUtc"))
    severity = {
        "SEV-1": IncidentSeverity.CRITICAL,
        "SEV-2": IncidentSeverity.HIGH,
        "SEV-3": IncidentSeverity.MEDIUM,
    }.get(str(incident.get("severity")), IncidentSeverity.LOW)
    trigger = IncidentTrigger(
        trigger_id=f"trigger-{incident_id}",
        source="datahub-incident-catalog",
        kind=_required_string(incident, "kind"),
        occurred_at=occurred_at,
        idempotency_key=f"catalog:{incident_id}",
        payload={
            "incidentId": incident_id,
            "rootAssetUrn": root_urn,
            "signal": _required_string(incident, "signal"),
        },
        evidence_references=tuple(str(item) for item in incident.get("evidenceRefs", [])),
    )
    return Incident(
        incident_id=incident_id,
        title=_required_string(incident, "title"),
        severity=severity,
        status=IncidentStatus.TRIGGERED,
        detected_at=occurred_at,
        trigger=trigger,
        affected_entities=affected,
    )


class CatalogContextProvider:
    """Build evidence-grounded incident context from the checked catalog."""

    def __init__(self, catalog: JsonObject) -> None:
        self.catalog = catalog
        self._assets = {str(item["urn"]): item for item in catalog["assets"]}
        self._owners = {str(item["id"]): item for item in catalog["owners"]}
        self._incidents = {str(item["id"]): item for item in catalog["incidents"]}

    def __call__(self, incident: Incident) -> IncidentContext:
        source = self._incidents.get(incident.incident_id)
        if source is None:
            raise IncidentCatalogError(f"incident not found: {incident.incident_id}")
        root_urn = _required_string(source, "rootAssetUrn")
        root = self._assets.get(root_urn)
        if root is None:
            raise IncidentCatalogError(f"root asset not found: {root_urn}")
        owner_ids = tuple(str(item) for item in root.get("owners", []))
        if not owner_ids:
            raise IncidentCatalogError(f"root asset has no owner: {root_urn}")
        owner = self._owners.get(owner_ids[0])
        if owner is None:
            raise IncidentCatalogError(f"owner not found: {owner_ids[0]}")
        blast_radius = catalog_descendants(self.catalog, root_urn)
        runbook = _required_string(root["documentation"], "runbookUrl")
        affected_field = _required_string(source, "affectedField")
        facts = (
            _fact(
                "incident-id",
                f"The incident identifier is {incident.incident_id}.",
                f"incident:{incident.incident_id}",
                EvidenceKind.SOURCE_RECORD,
            ),
            _fact(
                "incident-severity",
                f"The recorded severity is {source['severity']}.",
                f"incident:{incident.incident_id}#severity",
                EvidenceKind.SOURCE_RECORD,
            ),
            _fact(
                "root-asset",
                f"The triggering DataHub asset is {root_urn}.",
                f"asset:{root_urn}",
                EvidenceKind.DATAHUB_ENTITY,
            ),
            _fact(
                "primary-owner",
                f"The recorded primary owner is {owner_ids[0]}.",
                f"asset:{root_urn}#ownership",
                EvidenceKind.DATAHUB_ENTITY,
            ),
            _fact(
                "affected-field",
                f"The recorded affected field is {affected_field}.",
                f"schema:{root_urn}#{affected_field}",
                EvidenceKind.DATAHUB_ENTITY,
            ),
            _fact(
                "blast-radius",
                f"DataHub lineage records {len(blast_radius)} downstream assets.",
                f"lineage:{root_urn}",
                EvidenceKind.DATAHUB_ENTITY,
            ),
            _fact(
                "runbook",
                f"The recorded runbook URL is {runbook}.",
                f"doc:{root_urn}#runbook",
                EvidenceKind.DATAHUB_ENTITY,
            ),
        )
        return IncidentContext(
            context_id=f"context-{incident.incident_id}",
            incident=incident,
            collected_at=incident.detected_at,
            facts=facts,
            metadata={
                "source": "deterministic-datahub-shaped-catalog",
                "rootAsset": root,
                "owner": owner,
                "blastRadiusUrns": list(blast_radius),
                "safeActions": list(source.get("safeActions", [])),
                "forbiddenActionTypes": list(source.get("forbiddenActionTypes", [])),
                "claimBoundary": (
                    "Lineage is metadata-derived context and does not establish causality."
                ),
            },
        )


def catalog_descendants(catalog: JsonObject, root_urn: str) -> tuple[str, ...]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in catalog["lineage"]:
        upstream = str(edge["upstreamUrn"])
        downstream = str(edge["downstreamUrn"])
        adjacency[upstream].append(downstream)
    visited: set[str] = set()
    queue: deque[str] = deque(sorted(adjacency[root_urn]))
    while queue:
        urn = queue.popleft()
        if urn in visited:
            continue
        visited.add(urn)
        queue.extend(sorted(adjacency[urn]))
    return tuple(sorted(visited))


def _by_id(items: list[JsonObject], item_id: str, label: str) -> JsonObject:
    matches = [item for item in items if item.get("id") == item_id]
    if len(matches) != 1:
        raise IncidentCatalogError(f"{label} {item_id!r} was not uniquely found")
    return matches[0]


def _required_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IncidentCatalogError(f"required string is missing: {key}")
    return value.strip()


def _fact(
    fact_id: str,
    statement: str,
    reference: str,
    kind: EvidenceKind,
) -> IncidentFact:
    return IncidentFact(
        fact_id=fact_id,
        statement=statement,
        evidence=(EvidencePointer(reference=reference, kind=kind),),
    )
