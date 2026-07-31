from ledgerlens.catalog_runtime import load_incident_catalog
from ledgerlens.datahub_catalog import build_incident_catalog_bundle


def test_catalog_bundle_covers_all_assets_and_support_entities_deterministically() -> None:
    catalog = load_incident_catalog()
    first = build_incident_catalog_bundle(catalog)
    second = build_incident_catalog_bundle(catalog)

    assert first == second
    assert first["assetCount"] == 120
    assert first["ownerCount"] == 13
    assert first["domainCount"] == 4
    assert first["lineageEdgeCount"] == 174
    assert first["entityCount"] > first["assetCount"]
    assert len(first["mcps"]) > 500
    assert first["candidateOnly"] is True
    assert first["canClaimAGI"] is False
    entity_types = {item["entityType"] for item in first["entities"]}
    assert {"dataset", "dashboard", "mlModel", "dataProduct"} <= entity_types


def test_catalog_assets_preserve_operational_context_in_datahub_properties() -> None:
    bundle = build_incident_catalog_bundle(load_incident_catalog())
    dataset = next(item for item in bundle["entities"] if item["entityType"] == "dataset")
    properties = dataset["aspects"]["datasetProperties"]["customProperties"]

    assert properties["ledgerlens.runbookUrl"].startswith("https://runbooks.example.invalid/")
    assert properties["ledgerlens.schema"].startswith("[")
    assert properties["ledgerlens.qualityChecks"].startswith("[")
    assert properties["ledgerlens.candidateOnly"] == "true"
    assert properties["ledgerlens.canClaimAGI"] == "false"
