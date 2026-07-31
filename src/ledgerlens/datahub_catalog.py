"""Deterministic DataHub metadata proposals for the incident-command catalog."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from ledgerlens.datahub_ingest import metadata_change_proposal

JsonObject = dict[str, Any]
_URN_TYPE = re.compile(r"^urn:li:([^:(]+)")
_ASPECT_TYPES = {
    "corpGroupInfo": "CorpGroupInfo",
    "dashboardInfo": "DashboardInfo",
    "dataProductProperties": "DataProductProperties",
    "datasetProperties": "DatasetProperties",
    "domainProperties": "DomainProperties",
    "globalTags": "GlobalTags",
    "mlModelProperties": "MLModelProperties",
    "ownership": "Ownership",
    "status": "Status",
    "tagProperties": "TagProperties",
    "upstreamLineage": "UpstreamLineage",
}


class IncidentCatalogIngestionError(ValueError):
    """Raised when catalog data cannot produce bounded DataHub proposals."""


def build_incident_catalog_bundle(catalog: Mapping[str, Any]) -> JsonObject:
    """Return deterministic generic MCPs for all catalog assets and support entities."""

    assets = _records(catalog, "assets")
    owners = _records(catalog, "owners")
    lineage = _records(catalog, "lineage")
    tags = sorted(
        {
            str(tag)
            for asset in assets
            for tag in asset.get("tags", [])
            if isinstance(tag, str) and tag
        }
    )
    domains = sorted(
        {
            str(asset["domain"])
            for asset in assets
            if isinstance(asset.get("domain"), str) and asset["domain"]
        }
    )

    upstream_by_downstream: dict[str, list[str]] = {}
    for edge in lineage:
        upstream = _required_string(edge, "upstreamUrn")
        downstream = _required_string(edge, "downstreamUrn")
        upstream_by_downstream.setdefault(downstream, []).append(upstream)

    entities: list[JsonObject] = []
    for owner in owners:
        owner_id = _required_string(owner, "id")
        entities.append(
            _entity(
                "corpGroup",
                f"urn:li:corpGroup:{owner_id}",
                {
                    "corpGroupInfo": {
                        "displayName": _required_string(owner, "displayName"),
                        "email": str(owner.get("email") or ""),
                        "description": str(owner.get("escalationPolicy") or ""),
                        "slack": str(owner.get("slackChannel") or ""),
                        "admins": [],
                        "members": [],
                        "groups": [],
                    }
                },
            )
        )
    for tag in tags:
        entities.append(
            _entity(
                "tag",
                f"urn:li:tag:ledgerlens.{_slug(tag)}",
                {
                    "tagProperties": {
                        "name": tag,
                        "description": "Synthetic LedgerLens incident-catalog tag.",
                        "colorHex": "#7CFFB2",
                    }
                },
            )
        )
    for domain in domains:
        entities.append(
            _entity(
                "domain",
                f"urn:li:domain:ledgerlens.{_slug(domain)}",
                {
                    "domainProperties": {
                        "name": domain,
                        "description": ("Synthetic LedgerLens incident-command catalog domain."),
                        "customProperties": {
                            "ledgerlens.candidateOnly": "true",
                            "ledgerlens.canClaimAGI": "false",
                        },
                    }
                },
            )
        )
    for asset in assets:
        urn = _required_string(asset, "urn")
        entity_type = _entity_type(urn)
        aspects = _asset_aspects(
            asset,
            upstream_urns=tuple(sorted(upstream_by_downstream.get(urn, []))),
        )
        entities.append(_entity(entity_type, urn, aspects))

    mcps = [proposal for entity in entities for proposal in entity["mcps"]]
    mcps.sort(key=lambda item: (item["entityType"], item["entityUrn"], item["aspectName"]))
    return {
        "schemaVersion": "ledgerlens.incident-catalog.datahub.v1",
        "entityCount": len(entities),
        "assetCount": len(assets),
        "ownerCount": len(owners),
        "tagCount": len(tags),
        "domainCount": len(domains),
        "lineageEdgeCount": len(lineage),
        "entities": entities,
        "mcps": mcps,
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def _asset_aspects(
    asset: Mapping[str, Any],
    *,
    upstream_urns: tuple[str, ...],
) -> dict[str, JsonObject]:
    urn = _required_string(asset, "urn")
    entity_type = _entity_type(urn)
    documentation = asset.get("documentation")
    docs = dict(documentation) if isinstance(documentation, Mapping) else {}
    custom_properties = {
        "ledgerlens.assetId": _required_string(asset, "id"),
        "ledgerlens.domain": str(asset.get("domain") or ""),
        "ledgerlens.tier": str(asset.get("tier") or ""),
        "ledgerlens.environment": str(asset.get("environment") or ""),
        "ledgerlens.platform": str(asset.get("platform") or ""),
        "ledgerlens.runbookUrl": str(docs.get("runbookUrl") or ""),
        "ledgerlens.freshnessSloMinutes": str(docs.get("freshnessSloMinutes") or ""),
        "ledgerlens.availabilitySloPercent": str(docs.get("availabilitySloPercent") or ""),
        "ledgerlens.qualityChecks": _canonical(docs.get("qualityChecks", [])),
        "ledgerlens.schema": _canonical(asset.get("schema", [])),
        "ledgerlens.upstreamUrns": _canonical(upstream_urns),
        "ledgerlens.synthetic": "true",
        "ledgerlens.candidateOnly": "true",
        "ledgerlens.canClaimAGI": "false",
    }
    description = str(docs.get("summary") or "Synthetic incident-command catalog asset.")
    name = str(asset.get("displayName") or asset.get("name") or urn)
    primary: JsonObject
    if entity_type == "dataset":
        primary_name = "datasetProperties"
        primary = {
            "name": name,
            "description": description,
            "externalUrl": str(docs.get("catalogUrl") or ""),
            "customProperties": custom_properties,
        }
    elif entity_type == "dashboard":
        primary_name = "dashboardInfo"
        primary = {
            "title": name,
            "description": description,
            "externalUrl": str(docs.get("catalogUrl") or ""),
            "datasets": [value for value in upstream_urns if ":dataset:" in value],
            "dashboards": [],
            "charts": [],
            "customProperties": custom_properties,
            "lastModified": {
                "created": {"time": 0, "actor": "urn:li:corpuser:ledgerlens"},
                "lastModified": {"time": 0, "actor": "urn:li:corpuser:ledgerlens"},
            },
        }
    elif entity_type == "mlModel":
        primary_name = "mlModelProperties"
        primary = {
            "name": name,
            "description": description,
            "externalUrl": str(docs.get("catalogUrl") or ""),
            "customProperties": custom_properties,
            "tags": [],
            "trainingJobs": [],
            "downstreamJobs": [],
        }
    elif entity_type == "dataProduct":
        primary_name = "dataProductProperties"
        primary = {
            "name": name,
            "description": description,
            "externalUrl": str(docs.get("catalogUrl") or ""),
            "customProperties": custom_properties,
            "assets": [{"destinationUrn": value, "outputPort": False} for value in upstream_urns],
        }
    else:  # pragma: no cover - guarded by _entity_type
        raise AssertionError(entity_type)

    owner_urns = [
        f"urn:li:corpGroup:{value}"
        for value in asset.get("owners", [])
        if isinstance(value, str) and value
    ]
    tag_urns = [
        f"urn:li:tag:ledgerlens.{_slug(value)}"
        for value in asset.get("tags", [])
        if isinstance(value, str) and value
    ]
    aspects: dict[str, JsonObject] = {
        "status": {"removed": False},
        primary_name: primary,
        "ownership": {
            "owners": [
                {
                    "owner": value,
                    "type": "TECHNICAL_OWNER",
                    "source": {"type": "SERVICE"},
                }
                for value in owner_urns
            ]
        },
        "globalTags": {"tags": [{"tag": value} for value in tag_urns]},
    }
    if entity_type == "dataset" and upstream_urns:
        aspects["upstreamLineage"] = {
            "upstreams": [{"dataset": value, "type": "TRANSFORMED"} for value in upstream_urns],
            "fineGrainedLineages": [],
        }
    return aspects


def _entity(
    entity_type: str,
    urn: str,
    aspects: Mapping[str, JsonObject],
) -> JsonObject:
    proposals = []
    normalized_aspects: dict[str, JsonObject] = {}
    for aspect_name in sorted(aspects):
        value = dict(aspects[aspect_name])
        normalized_aspects[aspect_name] = value
        proposal = metadata_change_proposal(
            entity_type=entity_type,
            entity_urn=urn,
            aspect_name=aspect_name,
            aspect=value,
        )
        aspect_type = _ASPECT_TYPES.get(aspect_name)
        if aspect_type is not None:
            proposal["aspect"]["value"]["__type"] = aspect_type
        proposals.append(proposal)
    return {
        "entityType": entity_type,
        "urn": urn,
        "aspects": normalized_aspects,
        "mcps": proposals,
    }


def _entity_type(urn: str) -> str:
    match = _URN_TYPE.match(urn)
    if match is None or match.group(1) not in {
        "dataset",
        "dashboard",
        "mlModel",
        "dataProduct",
    }:
        raise IncidentCatalogIngestionError(f"unsupported catalog entity URN: {urn}")
    return match.group(1)


def _records(catalog: Mapping[str, Any], key: str) -> list[JsonObject]:
    raw = catalog.get(key)
    if not isinstance(raw, list) or any(not isinstance(item, Mapping) for item in raw):
        raise IncidentCatalogIngestionError(f"catalog {key} must be a list of objects")
    return [dict(item) for item in raw]


def _required_string(item: Mapping[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IncidentCatalogIngestionError(f"required string is missing: {key}")
    return value.strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"
    return f"{slug[:48]}-{hashlib.sha256(value.encode()).hexdigest()[:8]}"


__all__ = [
    "IncidentCatalogIngestionError",
    "build_incident_catalog_bundle",
]
