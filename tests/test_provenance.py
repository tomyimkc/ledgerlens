"""Tests for fail-closed provenance merging and claim boundaries."""

from __future__ import annotations

import pytest

from ledgerlens.datahub_client import AuditMetadata, AuditStamp
from ledgerlens.provenance import (
    ProvenanceConflictError,
    extract_evidence_references,
    merge_provenance,
)

URN = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,F-001,PROD)"


def _audit(urn: str = URN) -> AuditMetadata:
    return AuditMetadata(
        urn=urn,
        entity_type="dataset",
        audit_stamps=(
            AuditStamp(
                aspect="datasetProperties",
                kind="created",
                time_ms=1_700_000_000_000,
                actor="urn:li:corpuser:ingestor",
            ),
        ),
        system_metadata={
            "datasetProperties": {
                "lastObserved": 1_700_000_000_100,
                "runId": "run-1",
            }
        },
        aspect_values={},
    )


def test_merge_preserves_evidence_and_separates_ingestion_from_validation() -> None:
    mcp = {
        "urn": URN,
        "type": "DATASET",
        "name": "F-001",
        "customProperties": {
            "status": "open",
            "candidateOnly": "true",
            "canClaimAGI": "false",
            "scientificValidationStatus": "unverified",
            "evidenceReferences": '["receipts/run.json", "https://example.test/evidence"]',
            "supersededBy": "urn:li:dataset:next",
        },
    }
    graph = {
        "urn": URN,
        "type": "DATASET",
        "name": "F-001",
        "status": {"removed": False},
        "ownership": {
            "owners": [{"owner": {"urn": "urn:li:corpuser:owner"}, "type": "TECHNICAL_OWNER"}]
        },
        "properties": {
            "customProperties": [
                {"key": "status", "value": "open"},
                {"key": "candidateOnly", "value": "true"},
                {"key": "canClaimAGI", "value": "false"},
                {"key": "scientificValidationStatus", "value": "unverified"},
                {
                    "key": "evidenceReferences",
                    "value": '["receipts/run.json", "https://example.test/evidence"]',
                },
                {"key": "supersededBy", "value": "urn:li:dataset:next"},
            ]
        },
    }
    record = merge_provenance(mcp, graphql_entity=graph, audit_metadata=_audit())
    rendered = record.to_dict()
    assert record.owners == ("urn:li:corpuser:owner",)
    assert record.evidence_references == (
        "receipts/run.json",
        "https://example.test/evidence",
    )
    assert record.superseded_by == ("urn:li:dataset:next",)
    assert rendered["candidateOnly"] is True
    assert rendered["canClaimAGI"] is False
    assert rendered["scientificValidation"]["independentlyValidatedByLedgerLens"] is False
    assert "not scientific validation time" in rendered["datahubIngestionAudit"]["meaning"]
    assert rendered["datahubIngestionAudit"]["timeMs"] == 1_700_000_000_100


def test_missing_metadata_is_explicit_and_fail_closed() -> None:
    record = merge_provenance({"urn": URN}, audit_metadata=None)
    assert record.scientific_validation_status == "unverified"
    assert set(record.missing_metadata) == {
        "status",
        "owner",
        "evidenceReferences",
        "datahubIngestionAudit",
        "scientificValidation",
    }
    assert record.candidate_only is True
    assert record.can_claim_agi is False


@pytest.mark.parametrize(
    ("mcp", "graph", "message"),
    [
        ({"urn": URN}, {"urn": "urn:other"}, "URNs conflict"),
        ({"urn": URN, "candidateOnly": False}, None, "candidateOnly"),
        ({"urn": URN, "canClaimAGI": True}, None, "canClaimAGI"),
        (
            {"urn": URN, "status": "open"},
            {"urn": URN, "status": "resolved"},
            "Conflicting status",
        ),
    ],
)
def test_safety_critical_contradictions_raise(
    mcp: dict[str, object],
    graph: dict[str, object] | None,
    message: str,
) -> None:
    with pytest.raises(ProvenanceConflictError, match=message):
        merge_provenance(mcp, graphql_entity=graph, audit_metadata=_audit())


def test_declared_validation_is_not_promoted_to_independent_validation() -> None:
    record = merge_provenance(
        {
            "urn": URN,
            "customProperties": {
                "status": "open",
                "scientificValidationStatus": "validated",
            },
        },
        audit_metadata=_audit(),
    )
    assert record.scientific_validation_status == "declared-validated"


def test_evidence_normalizer_accepts_lists_json_and_lines() -> None:
    assert extract_evidence_references(
        {"evidenceReceipt": "one.json\ntwo.json"},
        {"evidenceReferences": '["two.json", "three.json"]'},
    ) == ("one.json", "two.json", "three.json")


def test_prefixed_ingestion_properties_are_normalized() -> None:
    record = merge_provenance(
        {
            "urn": URN,
            "customProperties": [
                {"key": "ledgerlens.findingId", "value": "F-001"},
                {"key": "ledgerlens.status", "value": "open"},
                {"key": "ledgerlens.candidateOnly", "value": "true"},
                {"key": "ledgerlens.canClaimAGI", "value": "false"},
                {
                    "key": "ledgerlens.owners",
                    "value": '["urn:li:corpGroup:ledgerlens.owner"]',
                },
                {
                    "key": "ledgerlens.evidenceReferences",
                    "value": (
                        '[{"reference":"fixture/receipt.json",'
                        '"kind":"repository_path","label":"receipt"}]'
                    ),
                },
                {
                    "key": "ledgerlens.supersedesIds",
                    "value": '["older-finding"]',
                },
            ],
        },
        audit_metadata=_audit(),
    )
    assert record.status == "open"
    assert record.owners == ("urn:li:corpGroup:ledgerlens.owner",)
    assert record.evidence_references == ("fixture/receipt.json",)
    assert record.supersedes == ("older-finding",)
    assert record.custom_properties["findingId"] == "F-001"
