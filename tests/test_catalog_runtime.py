"""Tests for application use of the synthetic multi-domain incident catalog."""

from __future__ import annotations

from ledgerlens.catalog_runtime import (
    CatalogContextProvider,
    catalog_descendants,
    incident_from_catalog,
    load_incident_catalog,
)


def test_catalog_builds_grounded_incident_context() -> None:
    catalog = load_incident_catalog()
    incident_id = str(catalog["incidents"][0]["id"])
    incident = incident_from_catalog(catalog, incident_id)
    context = CatalogContextProvider(catalog)(incident)

    assert incident.incident_id == incident_id
    assert incident.affected_entities[0] == catalog["incidents"][0]["rootAssetUrn"]
    assert context.incident == incident
    assert context.fact_ids == {
        "incident-id",
        "incident-severity",
        "root-asset",
        "primary-owner",
        "affected-field",
        "blast-radius",
        "runbook",
    }
    assert context.metadata["blastRadiusUrns"]
    assert context.candidate_only is True
    assert context.can_claim_agi is False


def test_descendants_match_scenario_ground_truth() -> None:
    catalog = load_incident_catalog()
    scenarios = {item["incidentId"]: item for item in catalog["scenarios"]}
    for incident in catalog["incidents"]:
        expected = tuple(sorted(scenarios[incident["id"]]["expected"]["blastRadiusUrns"]))
        assert catalog_descendants(catalog, incident["rootAssetUrn"]) == expected
