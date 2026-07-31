"""Tests for the self-contained synthetic incident catalog."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.incident_commander.catalog import (  # noqa: E402
    DEFAULT_CATALOG_SEED,
    CatalogValidationError,
    descendants,
    generate_catalog,
    load_catalog,
    validate_catalog,
    write_catalog_atomic,
)

CATALOG_PATH = ROOT / "fixtures/incident_commander/catalog.json"


def test_checked_in_catalog_is_deterministic_and_realistic() -> None:
    checked_in = load_catalog(CATALOG_PATH)
    rebuilt = generate_catalog(DEFAULT_CATALOG_SEED)

    assert checked_in == rebuilt
    summary = validate_catalog(checked_in)
    assert summary["assetCount"] == 120
    assert summary["scenarioCount"] == 24
    assert summary["incidentCount"] == 24
    assert summary["domainAssetCounts"] == {
        "analytics": 30,
        "customer": 30,
        "finance": 30,
        "ml": 30,
    }
    assert summary["entityTypeCounts"]["dashboard"] == 12
    assert summary["entityTypeCounts"]["ml_model"] == 12
    assert summary["crossDomainLineageEdgeCount"] >= 4
    assert checked_in["candidateOnly"] is True
    assert checked_in["canClaimAGI"] is False


def test_assets_have_schema_owners_documentation_and_lineage() -> None:
    catalog = load_catalog(CATALOG_PATH)
    owner_ids = {owner["id"] for owner in catalog["owners"]}
    asset_urns = {asset["urn"] for asset in catalog["assets"]}

    for asset in catalog["assets"]:
        assert asset["schema"]
        assert set(asset["owners"]).issubset(owner_ids)
        assert asset["documentation"]["summary"]
        assert asset["documentation"]["runbookUrl"].startswith("https://runbooks.example.invalid/")
        assert set(asset["upstreamUrns"]).issubset(asset_urns)

    cross_domain_scenarios = []
    asset_by_urn = {asset["urn"]: asset for asset in catalog["assets"]}
    incident_by_id = {incident["id"]: incident for incident in catalog["incidents"]}
    for scenario in catalog["scenarios"]:
        incident = incident_by_id[scenario["incidentId"]]
        root_domain = asset_by_urn[incident["rootAssetUrn"]]["domain"]
        impacted_domains = {
            asset_by_urn[urn]["domain"] for urn in scenario["expected"]["blastRadiusUrns"]
        }
        if impacted_domains - {root_domain}:
            cross_domain_scenarios.append(scenario["id"])
    assert cross_domain_scenarios


def test_scenario_blast_radius_is_full_transitive_closure() -> None:
    catalog = load_catalog(CATALOG_PATH)
    incident_by_id = {incident["id"]: incident for incident in catalog["incidents"]}

    for scenario in catalog["scenarios"]:
        incident = incident_by_id[scenario["incidentId"]]
        expected = descendants(catalog, incident["rootAssetUrn"])
        assert scenario["expected"]["blastRadiusUrns"] == expected
        assert expected


def test_validator_rejects_dangling_lineage_and_overclaiming() -> None:
    catalog = generate_catalog()
    dangling = deepcopy(catalog)
    dangling["assets"][0]["upstreamUrns"] = ["urn:li:dataset:missing"]
    with pytest.raises(CatalogValidationError, match="unknown upstream"):
        validate_catalog(dangling)

    overclaiming = deepcopy(catalog)
    overclaiming["canClaimAGI"] = True
    with pytest.raises(CatalogValidationError, match="canClaimAGI"):
        validate_catalog(overclaiming)


def test_atomic_writer_preserves_existing_file_when_catalog_is_invalid(
    tmp_path: Path,
) -> None:
    output = tmp_path / "catalog.json"
    output.write_text('{"sentinel": true}\n', encoding="utf-8")
    invalid = generate_catalog()
    invalid["candidateOnly"] = False

    with pytest.raises(CatalogValidationError, match="candidateOnly"):
        write_catalog_atomic(output, invalid)

    assert json.loads(output.read_text(encoding="utf-8")) == {"sentinel": True}


def test_seed_is_recorded_and_changes_deterministic_assignment() -> None:
    first = generate_catalog(DEFAULT_CATALOG_SEED)
    second = generate_catalog(DEFAULT_CATALOG_SEED + 1)

    assert first["generator"]["seed"] == DEFAULT_CATALOG_SEED
    assert second["generator"]["seed"] == DEFAULT_CATALOG_SEED + 1
    assert first["summary"] == second["summary"]
    assert [asset["owners"] for asset in first["assets"]] != [
        asset["owners"] for asset in second["assets"]
    ]
