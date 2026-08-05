"""Network-free deterministic workflow tests for the LedgerLens agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ledgerlens.agent import (
    AgentGroundingError,
    LedgerLensAgent,
    OpenAICompatible020s,
)
from ledgerlens.config import Settings
from ledgerlens.datahub_client import AuditMetadata, AuditStamp

URN_A = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,ledgerlens.failure_ledger.finding.a,PROD)"
URN_B = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,ledgerlens.failure_ledger.finding.b,PROD)"
URN_C = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,ledgerlens.failure_ledger.finding.c,PROD)"


def _entity(
    urn: str,
    *,
    status: str = "open",
    owner: str | None = "urn:li:corpuser:owner",
    evidence: str | None = "receipts/evidence.json",
    supersedes: str | None = None,
    superseded_by: str | None = None,
    candidate_only: bool = True,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "status": status,
        "candidateOnly": str(candidate_only).lower(),
        "canClaimAGI": "false",
        "scientificValidationStatus": "unverified",
    }
    if owner:
        properties["owner"] = owner
    if evidence:
        properties["evidenceReferences"] = evidence
    if supersedes:
        properties["supersedes"] = json.dumps([supersedes])
    if superseded_by:
        properties["supersededBy"] = json.dumps([superseded_by])
    return {
        "urn": urn,
        "type": "DATASET",
        "name": urn.rsplit(":", 1)[-1],
        "customProperties": properties,
    }


class FakeMCP:
    def __init__(self, entities: list[dict[str, Any]]) -> None:
        self.entities = {item["urn"]: item for item in entities}
        self.lineage = [{"urn": URN_C, "type": "DATASET", "degree": 1}]

    def search(self, query: str, *, count: int = 20, **_: Any) -> list[dict[str, Any]]:
        del query, count
        return [{"urn": urn} for urn in reversed(self.entities)]

    def get_entities(self, urns: list[str]) -> list[dict[str, Any]]:
        return [self.entities[urn] for urn in urns if urn in self.entities]

    def get_lineage(self, urn: str, **_: Any) -> list[dict[str, Any]]:
        del urn
        return self.lineage


class FakeDataHub:
    def __init__(self, entities: list[dict[str, Any]]) -> None:
        self.entities = {item["urn"]: item for item in entities}

    def get_entity(self, urn: str) -> dict[str, Any]:
        entity = self.entities[urn]
        return {
            "urn": entity["urn"],
            "type": entity["type"],
            "name": entity["name"],
            "properties": {
                "customProperties": [
                    {"key": key, "value": value}
                    for key, value in entity["customProperties"].items()
                ]
            },
        }

    def get_audit_metadata(self, urn: str) -> AuditMetadata:
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
            system_metadata={"datasetProperties": {"runId": "run-1"}},
            aspect_values={},
        )


def _agent(entities: list[dict[str, Any]], phrase_model: Any = None) -> LedgerLensAgent:
    return LedgerLensAgent(
        FakeMCP(entities),  # type: ignore[arg-type]
        FakeDataHub(entities),  # type: ignore[arg-type]
        phrase_model=phrase_model,
        clock=lambda: datetime(2026, 8, 1, tzinfo=UTC),
    )


def test_explain_is_grounded_and_has_fixed_claim_ceiling() -> None:
    report = _agent([_entity(URN_A)]).explain_finding(URN_A)
    assert report["candidateOnly"] is True
    assert report["canClaimAGI"] is False
    assert "not independent validation" in report["claimCeiling"]
    assert report["finding"]["urn"] == URN_A
    assert report["finding"]["scientificValidation"]["independentlyValidatedByLedgerLens"] is False
    assert report["decision"] == "blocked"  # scientific validation remains unverified


def test_optional_model_only_adds_narrative() -> None:
    class FakePhraseModel:
        def phrase(self, facts: dict[str, Any]) -> str:
            assert facts["urn"] == URN_A
            return "Grounded phrasing."

    report = _agent([_entity(URN_A)], FakePhraseModel()).explain_finding(URN_A)
    assert report["finding"]["status"] == "open"
    assert report["modelNarrative"] == "Grounded phrasing."
    assert report["modelNarrativeRole"].startswith("phrasing only")


def test_supersession_uses_explicit_metadata_not_lineage_alone() -> None:
    first = _entity(URN_A, superseded_by=URN_B)
    second = _entity(URN_B, status="resolved")
    unrelated_lineage = _entity(URN_C)
    agent = _agent([first, second, unrelated_lineage])
    report = agent.supersession_chain(URN_A)
    assert [item["urn"] for item in report["chain"]] == [URN_A, URN_B]
    assert report["lineageContext"][0]["urn"] == URN_C
    assert "contextual only" in report["lineageWarning"]


def test_supersession_can_walk_explicit_historical_ancestors() -> None:
    historical = _entity(URN_A, status="superseded")
    current = _entity(URN_B, supersedes=URN_A)
    report = _agent([historical, current]).supersession_chain(URN_B)
    assert [item["urn"] for item in report["chain"]] == [URN_A, URN_B]


def test_missing_metadata_and_priority_queue_are_deterministic() -> None:
    highest = _entity(URN_A, owner=None, evidence=None)
    lower = _entity(URN_B)
    resolved = _entity(URN_C, status="resolved")
    superseded = _entity(
        "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,ledgerlens.failure_ledger.finding.d,PROD)",
        status="superseded",
    )
    agent = _agent([lower, resolved, superseded, highest])

    missing = agent.missing_metadata_query()
    assert missing["items"][0]["urn"] == URN_A
    assert {"owner", "evidenceReferences"} <= set(missing["items"][0]["missingMetadata"])

    queue = agent.prioritized_remediation_queue()
    assert [item["urn"] for item in queue["items"]] == [URN_A, URN_B]
    assert queue["items"][0]["priorityScore"] > queue["items"][1]["priorityScore"]
    assert queue["items"][0]["evidenceReferences"] == []


def test_search_workflows_ignore_unrelated_catalog_entities() -> None:
    unrelated = _entity(
        "urn:li:dataset:(urn:li:dataPlatform:snowflake,production.payroll,PROD)",
        owner=None,
        evidence=None,
    )
    queue = _agent([_entity(URN_A), unrelated]).prioritized_remediation_queue()

    assert [item["urn"] for item in queue["items"]] == [URN_A]


def test_contradictory_metadata_blocks_factual_selection() -> None:
    unsafe = _entity(URN_A, candidate_only=False)
    report = _agent([unsafe]).prioritized_remediation_queue()
    assert report["decision"] == "blocked"
    assert report["items"] == []
    assert report["conflicts"][0]["urn"] == URN_A
    assert "candidateOnly" in report["conflicts"][0]["error"]


def test_missing_requested_entity_fails_closed() -> None:
    with pytest.raises(AgentGroundingError, match="did not return"):
        _agent([]).explain_finding(URN_A)


def test_report_writes_json_and_markdown(tmp_path: Path) -> None:
    agent = _agent([_entity(URN_A)])
    report = agent.prioritized_remediation_queue()
    json_path = agent.write_report(report, tmp_path / "report.json")
    md_path = agent.write_report(report, tmp_path / "report.md")
    parsed = json.loads(json_path.read_text())
    assert parsed["candidateOnly"] is True
    markdown = md_path.read_text()
    assert "`candidateOnly: true`" in markdown
    assert URN_A in markdown
    assert "receipts/evidence.json" in markdown


def test_020s_client_is_network_mocked_and_does_not_expose_key() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Safe grounded summary."}}]},
        )

    settings = Settings(
        _env_file=None,
        llm_enabled=True,
        llm_api_key="secret-020s-key",
    )
    model = OpenAICompatible020s(settings, transport=httpx.MockTransport(handler))
    assert model.phrase({"urn": URN_A, "candidateOnly": True}) == "Safe grounded summary."
    assert seen["authorization"] == "Bearer secret-020s-key"
    assert seen["body"]["model"] == "gpt-5.6-sol"
    assert "secret-020s-key" not in json.dumps(seen["body"])
