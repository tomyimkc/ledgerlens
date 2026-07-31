"""Deterministic DataHub aspect and Metadata Change Proposal payloads.

The module deliberately has no runtime dependency on the DataHub SDK. It emits
plain dictionaries that can be snapshot-tested, serialized, or passed through
an SDK/OpenAPI adapter by the integration layer.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

from ledgerlens.models import EvidenceKind, Finding, LedgerParseResult

DATAHUB_PLATFORM = "ledgerlens"
DATAHUB_ENVIRONMENT = "PROD"
DATASET_NAMESPACE = "ledgerlens.failure_ledger"
DEFAULT_ACTOR_URN = "urn:li:corpuser:ledgerlens"
SUPERSESSION_LINEAGE_SEMANTICS = (
    "A LedgerLens supersession edge uses DataHub dataset lineage only as a "
    "discoverable graph representation: the downstream finding supersedes the "
    "upstream historical finding. It is not data-pipeline lineage and does not "
    "independently validate either finding."
)

_ASPECT_TYPES = {
    "container": "Container",
    "containerProperties": "ContainerProperties",
    "datasetProperties": "DatasetProperties",
    "globalTags": "GlobalTags",
    "institutionalMemory": "InstitutionalMemory",
    "ownership": "Ownership",
    "status": "Status",
    "subTypes": "SubTypes",
    "tagProperties": "TagProperties",
    "upstreamLineage": "UpstreamLineage",
}


class DataHubPayloadError(ValueError):
    """Raised when malformed findings are offered for ingestion."""


def _stable_component(value: str, *, max_slug_length: int = 56) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "item"
    slug = slug[:max_slug_length].rstrip("-") or "item"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def data_platform_urn(platform: str = DATAHUB_PLATFORM) -> str:
    """Return the DataHub platform URN used by LedgerLens datasets."""

    return f"urn:li:dataPlatform:{platform}"


def is_ledgerlens_finding_urn(urn: str) -> bool:
    """Return whether *urn* is a default LedgerLens failure-finding dataset."""

    prefix = f"urn:li:dataset:({data_platform_urn()},{DATASET_NAMESPACE}.finding."
    return urn.startswith(prefix) and urn.endswith(f",{DATAHUB_ENVIRONMENT})")


def container_urn(source_key: str = "sophia-failure-ledger") -> str:
    """Return a deterministic DataHub container URN for a ledger source."""

    digest = hashlib.sha256(f"ledgerlens:container:{source_key}".encode()).hexdigest()[:32]
    return f"urn:li:container:{digest}"


def dataset_urn(
    finding_id: str,
    *,
    platform: str = DATAHUB_PLATFORM,
    environment: str = DATAHUB_ENVIRONMENT,
    namespace: str = DATASET_NAMESPACE,
) -> str:
    """Return a stable, collision-resistant dataset URN for one finding."""

    dataset_name = f"{namespace}.finding.{_stable_component(finding_id)}"
    return f"urn:li:dataset:(urn:li:dataPlatform:{platform},{dataset_name},{environment})"


def tag_urn(tag: str) -> str:
    """Return a stable tag URN under the LedgerLens namespace."""

    return f"urn:li:tag:ledgerlens.{_stable_component(tag, max_slug_length=40)}"


def owner_urn(owner: str) -> str:
    """Represent conservatively parsed owners as deterministic CorpGroup URNs."""

    return f"urn:li:corpGroup:ledgerlens.{_stable_component(owner, max_slug_length=40)}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return value.isoformat()


def _timestamp_millis(finding: Finding) -> int:
    timestamp = finding.updated_at or finding.created_at or finding.resolved_at
    if timestamp is not None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return int(timestamp.timestamp() * 1000)
    if finding.recorded_on is not None:
        midnight = datetime.combine(finding.recorded_on, datetime.min.time(), tzinfo=UTC)
        return int(midnight.timestamp() * 1000)
    return 0


def _aspect_value(aspect_name: str, aspect: dict[str, Any]) -> dict[str, Any]:
    aspect_type = _ASPECT_TYPES.get(aspect_name)
    if aspect_type is None:
        return dict(aspect)
    return {"__type": aspect_type, **aspect}


def metadata_change_proposal(
    *,
    entity_type: str,
    entity_urn: str,
    aspect_name: str,
    aspect: dict[str, Any],
) -> dict[str, Any]:
    """Build an OpenAPI-compatible Metadata Change Proposal dictionary."""

    return {
        "entityType": entity_type,
        "entityUrn": entity_urn,
        "changeType": "UPSERT",
        "aspectName": aspect_name,
        "aspect": {
            "contentType": "application/json",
            "value": _aspect_value(aspect_name, aspect),
        },
    }


def _evidence_url(
    reference: str,
    kind: EvidenceKind,
    *,
    source_repository_url: str | None,
) -> str | None:
    if kind is EvidenceKind.URL:
        return reference
    if kind is EvidenceKind.PATH and source_repository_url:
        root = source_repository_url.rstrip("/")
        path = quote(reference.lstrip("/"), safe="/:@%+~#=-._")
        return f"{root}/blob/main/{path}"
    return None


def _finding_tags(finding: Finding) -> list[str]:
    tags = {
        f"status-{finding.status_classification.value}",
        "candidate-only" if finding.candidate_only else "not-candidate-only",
        "can-claim-agi" if finding.can_claim_agi else "cannot-claim-agi",
    }
    if finding.kind:
        tags.add(f"kind-{finding.kind}")
    if not finding.owners:
        tags.add("missing-owner")
    if not finding.evidence_references:
        tags.add("missing-evidence")
    if finding.supersedes_ids:
        tags.add("has-supersession")
    if finding.is_malformed:
        tags.add("malformed")
    return sorted(tags)


def _finding_custom_properties(finding: Finding) -> dict[str, str]:
    return {
        "ledgerlens.findingId": finding.id,
        "ledgerlens.status": finding.status_classification.value,
        "ledgerlens.rawStatus": finding.status or "",
        "ledgerlens.statusClassification": finding.status_classification.value,
        "ledgerlens.kind": finding.kind or "",
        "ledgerlens.claimImpact": finding.claim_impact or "",
        "ledgerlens.requiredResponse": finding.required_response or "",
        "ledgerlens.candidateOnly": str(finding.candidate_only).lower(),
        "ledgerlens.canClaimAGI": str(finding.can_claim_agi).lower(),
        "ledgerlens.owners": _canonical_json(finding.owners),
        "ledgerlens.evidenceReferences": _canonical_json(
            [
                {
                    "reference": reference.reference,
                    "kind": reference.kind.value,
                    "label": reference.label,
                }
                for reference in finding.evidence_references
            ]
        ),
        "ledgerlens.supersedesIds": _canonical_json(finding.supersedes_ids),
        "ledgerlens.recordedOn": _iso(finding.recorded_on),
        "ledgerlens.createdAt": _iso(finding.created_at),
        "ledgerlens.updatedAt": _iso(finding.updated_at),
        "ledgerlens.resolvedAt": _iso(finding.resolved_at),
        "ledgerlens.source": finding.source or "",
        "ledgerlens.sourceLine": str(finding.source_line or ""),
        "ledgerlens.parseDiagnostics": _canonical_json(
            [
                diagnostic.model_dump(mode="json", exclude_none=True)
                for diagnostic in finding.parse_diagnostics
            ]
        ),
        "ledgerlens.relationshipSemantics": SUPERSESSION_LINEAGE_SEMANTICS,
    }


def finding_aspects(
    finding: Finding,
    *,
    ledger_container_urn: str,
    source_repository_url: str | None = None,
    actor_urn: str = DEFAULT_ACTOR_URN,
) -> dict[str, dict[str, Any]]:
    """Build deterministic DataHub aspects for a valid finding."""

    if finding.is_malformed:
        raise DataHubPayloadError(
            f"refusing to build DataHub aspects for malformed finding {finding.id!r}"
        )

    aspects: dict[str, dict[str, Any]] = {
        "status": {"removed": False},
        "datasetProperties": {
            "name": finding.id,
            "description": (
                "Failure-ledger finding ingested by LedgerLens. This metadata "
                "supports triage and does not independently validate the finding."
            ),
            "customProperties": _finding_custom_properties(finding),
        },
        "container": {"container": ledger_container_urn},
        "subTypes": {"typeNames": ["Failure Ledger Finding"]},
    }

    tag_urns = [tag_urn(tag) for tag in _finding_tags(finding)]
    aspects["globalTags"] = {"tags": [{"tag": urn} for urn in sorted(tag_urns)]}

    if finding.owners:
        aspects["ownership"] = {
            "owners": [
                {
                    "owner": owner_urn(owner),
                    "type": "TECHNICAL_OWNER",
                    "source": {"type": "SERVICE"},
                }
                for owner in sorted(finding.owners, key=str.casefold)
            ]
        }

    evidence_elements: list[dict[str, Any]] = []
    for evidence in finding.evidence_references:
        url = _evidence_url(
            evidence.reference,
            evidence.kind,
            source_repository_url=source_repository_url,
        )
        if url is None:
            continue
        evidence_elements.append(
            {
                "url": url,
                "description": (
                    f"{evidence.label or 'evidence'} reference preserved from finding {finding.id}"
                ),
                "createStamp": {
                    "actor": actor_urn,
                    "time": _timestamp_millis(finding),
                },
            }
        )
    if evidence_elements:
        aspects["institutionalMemory"] = {
            "elements": sorted(evidence_elements, key=lambda element: element["url"])
        }

    if finding.supersedes_ids:
        upstreams: list[dict[str, Any]] = []
        for superseded_id in sorted(finding.supersedes_ids):
            upstream: dict[str, Any] = {
                "dataset": dataset_urn(superseded_id),
                "type": "TRANSFORMED",
            }
            timestamp = _timestamp_millis(finding)
            if timestamp:
                upstream["auditStamp"] = {"actor": actor_urn, "time": timestamp}
            upstreams.append(upstream)
        aspects["upstreamLineage"] = {
            "upstreams": upstreams,
            "fineGrainedLineages": [],
        }

    return aspects


def _entity_payload(
    *, entity_type: str, urn: str, aspects: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "entityType": entity_type,
        "urn": urn,
        "aspects": aspects,
        "mcps": [
            metadata_change_proposal(
                entity_type=entity_type,
                entity_urn=urn,
                aspect_name=aspect_name,
                aspect=aspects[aspect_name],
            )
            for aspect_name in sorted(aspects)
        ],
    }


def _coerce_findings(
    findings: Sequence[Finding] | LedgerParseResult,
) -> tuple[list[Finding], list[Finding]]:
    values = findings.findings if isinstance(findings, LedgerParseResult) else list(findings)
    malformed = [finding for finding in values if finding.is_malformed]
    valid = [finding for finding in values if not finding.is_malformed]
    return valid, malformed


def build_datahub_bundle(
    findings: Sequence[Finding] | LedgerParseResult,
    *,
    source_key: str = "sophia-failure-ledger",
    source_name: str = "Sophia failure ledger",
    source_description: str = (
        "Pre-existing failure-ledger material ingested for a LedgerLens prototype."
    ),
    source_repository_url: str | None = None,
    reject_malformed: bool = True,
    actor_urn: str = DEFAULT_ACTOR_URN,
) -> dict[str, Any]:
    """Build a deterministic container, dataset, tag, lineage, and MCP bundle."""

    valid_findings, malformed_findings = _coerce_findings(findings)
    if malformed_findings and reject_malformed:
        malformed_ids = ", ".join(sorted(finding.id for finding in malformed_findings))
        raise DataHubPayloadError(
            f"refusing ingestion because malformed findings are present: {malformed_ids}"
        )

    ledger_container_urn = container_urn(source_key)
    container_aspects: dict[str, dict[str, Any]] = {
        "status": {"removed": False},
        "containerProperties": {
            "name": source_name,
            "description": source_description,
            "customProperties": {
                "ledgerlens.sourceKey": source_key,
                "ledgerlens.findingCount": str(len(valid_findings)),
                "ledgerlens.candidateOnly": "true",
                "ledgerlens.canClaimAGI": "false",
                "ledgerlens.disclosure": (
                    "Source ledger material predates the LedgerLens contest project."
                ),
            },
        },
        "subTypes": {"typeNames": ["Failure Ledger"]},
    }
    if source_repository_url:
        container_aspects["containerProperties"]["externalUrl"] = source_repository_url

    datasets = [
        _entity_payload(
            entity_type="dataset",
            urn=dataset_urn(finding.id),
            aspects=finding_aspects(
                finding,
                ledger_container_urn=ledger_container_urn,
                source_repository_url=source_repository_url,
                actor_urn=actor_urn,
            ),
        )
        for finding in sorted(valid_findings, key=lambda value: value.id)
    ]

    tag_names = sorted({tag for finding in valid_findings for tag in _finding_tags(finding)})
    tags = [
        _entity_payload(
            entity_type="tag",
            urn=tag_urn(tag),
            aspects={
                "tagProperties": {
                    "name": f"LedgerLens: {tag}",
                    "description": (
                        "Deterministic LedgerLens tag derived from failure-ledger metadata."
                    ),
                    "colorHex": "#5B6CF9",
                }
            },
        )
        for tag in tag_names
    ]

    container = _entity_payload(
        entity_type="container",
        urn=ledger_container_urn,
        aspects=container_aspects,
    )

    lineage_edges = [
        {
            "relationship": "supersedes",
            "upstreamUrn": dataset_urn(superseded_id),
            "downstreamUrn": dataset_urn(finding.id),
            "semantics": SUPERSESSION_LINEAGE_SEMANTICS,
        }
        for finding in sorted(valid_findings, key=lambda value: value.id)
        for superseded_id in sorted(finding.supersedes_ids)
    ]

    mcps = [
        *container["mcps"],
        *(mcp for tag in tags for mcp in tag["mcps"]),
        *(mcp for dataset in datasets for mcp in dataset["mcps"]),
    ]
    mcps.sort(
        key=lambda mcp: (
            mcp["entityType"],
            mcp["entityUrn"],
            mcp["aspectName"],
        )
    )

    return {
        "schemaVersion": "ledgerlens.datahub.bundle.v1",
        "urnConvention": {
            "platformUrn": data_platform_urn(),
            "environment": DATAHUB_ENVIRONMENT,
            "datasetNamespace": DATASET_NAMESPACE,
            "findingComponent": "<normalized-id>-<sha256-prefix-12>",
            "containerComponent": "sha256(source-key)-prefix-32",
        },
        "container": container,
        "datasets": datasets,
        "tags": tags,
        "lineage": lineage_edges,
        "skippedMalformed": [
            {
                "id": finding.id,
                "sourceLine": finding.source_line,
                "diagnosticCodes": [diagnostic.code for diagnostic in finding.parse_diagnostics],
            }
            for finding in sorted(malformed_findings, key=lambda value: value.id)
        ],
        "mcps": mcps,
    }


# Compatibility-oriented name for integration code that thinks in MCP batches.
build_metadata_change_proposals = build_datahub_bundle
