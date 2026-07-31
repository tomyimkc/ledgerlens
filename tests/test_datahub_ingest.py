"""Tests for deterministic, SDK-free DataHub ingestion payloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.datahub_ingest import (
    SUPERSESSION_LINEAGE_SEMANTICS,
    DataHubPayloadError,
    build_datahub_bundle,
    container_urn,
    dataset_urn,
    metadata_change_proposal,
)
from ledgerlens.models import Finding
from ledgerlens.parser import parse_ledger_file

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sophia_failure_ledger_sanitized.md"


def _dataset(bundle: dict, finding_id: str) -> dict:
    return next(
        dataset
        for dataset in bundle["datasets"]
        if dataset["aspects"]["datasetProperties"]["name"] == finding_id
    )


def test_urns_are_stable_collision_resistant_and_datahub_shaped() -> None:
    assert dataset_urn("Finding A") == dataset_urn("Finding A")
    assert dataset_urn("Finding A") != dataset_urn("finding-a")
    assert dataset_urn("Finding A").startswith("urn:li:dataset:(urn:li:dataPlatform:ledgerlens,")
    assert dataset_urn("Finding A").endswith(",PROD)")
    assert container_urn("fixture") == container_urn("fixture")
    assert container_urn("fixture") != container_urn("other")


def test_bundle_is_deterministic_and_json_serializable() -> None:
    result = parse_ledger_file(FIXTURE)

    first = build_datahub_bundle(
        result.valid_findings,
        source_key="public-fixture",
        source_repository_url="https://github.com/example/ledgerlens",
    )
    second = build_datahub_bundle(
        list(reversed(result.valid_findings)),
        source_key="public-fixture",
        source_repository_url="https://github.com/example/ledgerlens",
    )

    assert first == second
    assert json.loads(json.dumps(first)) == first


def test_bundle_contains_container_tags_ownership_evidence_and_claim_boundaries() -> None:
    result = parse_ledger_file(FIXTURE)
    bundle = build_datahub_bundle(
        result.valid_findings,
        source_key="public-fixture",
        source_repository_url="https://github.com/example/ledgerlens",
    )
    dataset = _dataset(bundle, "cache-receipt-missing-2026-07-20")
    aspects = dataset["aspects"]
    properties = aspects["datasetProperties"]["customProperties"]

    assert aspects["container"]["container"] == bundle["container"]["urn"]
    assert properties["ledgerlens.candidateOnly"] == "true"
    assert properties["ledgerlens.canClaimAGI"] == "false"
    assert "does not independently validate" in aspects["datasetProperties"]["description"]
    assert aspects["ownership"]["owners"][0]["type"] == "TECHNICAL_OWNER"
    assert aspects["ownership"]["owners"][0]["owner"].startswith("urn:li:corpGroup:ledgerlens.")
    assert aspects["institutionalMemory"]["elements"][0]["url"] == (
        "https://example.org/evidence/cache-refresh.json"
    )
    assert any(
        tag["tag"].startswith("urn:li:tag:ledgerlens.status-open-")
        for tag in aspects["globalTags"]["tags"]
    )

    defined_tag_urns = {tag["urn"] for tag in bundle["tags"]}
    referenced_tag_urns = {
        tag["tag"] for item in bundle["datasets"] for tag in item["aspects"]["globalTags"]["tags"]
    }
    assert referenced_tag_urns <= defined_tag_urns


def test_local_evidence_paths_become_public_repository_links_when_available() -> None:
    result = parse_ledger_file(FIXTURE)
    bundle = build_datahub_bundle(
        result.valid_findings,
        source_repository_url="https://github.com/example/ledgerlens",
    )
    dataset = _dataset(bundle, "safe-pipes-2026-07-24")

    assert dataset["aspects"]["institutionalMemory"]["elements"][0]["url"] == (
        "https://github.com/example/ledgerlens/blob/main/fixtures/evidence/safe-pipes.json"
    )


def test_supersession_uses_documented_newer_to_older_lineage_direction() -> None:
    result = parse_ledger_file(FIXTURE)
    bundle = build_datahub_bundle(result.valid_findings)
    replacement = _dataset(bundle, "cache-rule-v2-2026-07-22")
    lineage = replacement["aspects"]["upstreamLineage"]["upstreams"]

    assert lineage == [
        {
            "dataset": dataset_urn("stale-cache-rule-2026-07-18"),
            "type": "TRANSFORMED",
            "auditStamp": {
                "actor": "urn:li:corpuser:ledgerlens",
                "time": 1784707200000,
            },
        }
    ]
    assert bundle["lineage"] == [
        {
            "relationship": "supersedes",
            "upstreamUrn": dataset_urn("stale-cache-rule-2026-07-18"),
            "downstreamUrn": dataset_urn("cache-rule-v2-2026-07-22"),
            "semantics": SUPERSESSION_LINEAGE_SEMANTICS,
        }
    ]


def test_metadata_change_proposal_wraps_typed_aspect_payload() -> None:
    proposal = metadata_change_proposal(
        entity_type="dataset",
        entity_urn=dataset_urn("one"),
        aspect_name="status",
        aspect={"removed": False},
    )

    assert proposal == {
        "entityType": "dataset",
        "entityUrn": dataset_urn("one"),
        "changeType": "UPSERT",
        "aspectName": "status",
        "aspect": {
            "contentType": "application/json",
            "value": {"__type": "Status", "removed": False},
        },
    }


def test_malformed_findings_fail_closed_by_default_and_can_be_reported_as_skipped() -> None:
    result = parse_ledger_file(FIXTURE)

    with pytest.raises(DataHubPayloadError, match="malformed findings"):
        build_datahub_bundle(result)

    bundle = build_datahub_bundle(result, reject_malformed=False)
    assert len(bundle["datasets"]) == 6
    assert {
        code for finding in bundle["skippedMalformed"] for code in finding["diagnosticCodes"]
    } == {
        "duplicate_id",
        "unsafe_unescaped_pipe",
        "unbalanced_backticks",
        "column_count",
    }


def test_datahub_builder_refuses_a_direct_malformed_finding() -> None:
    finding = Finding(
        id="bad",
        status_classification="malformed",
        raw_middle="ambiguous",
    )

    with pytest.raises(DataHubPayloadError):
        build_datahub_bundle([finding])
