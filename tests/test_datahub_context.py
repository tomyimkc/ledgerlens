from datetime import UTC, datetime
from typing import Any

import pytest

from ledgerlens.datahub_context import DataHubContextError, DataHubMCPContextProvider
from ledgerlens.incident_models import (
    Incident,
    IncidentSeverity,
    IncidentTrigger,
)

NOW = datetime(2026, 7, 31, tzinfo=UTC)
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)"


class Client:
    def __init__(self, *, owner: bool = True) -> None:
        self.owner = owner

    def get_entities(self, urns: list[str]) -> list[dict[str, Any]]:
        assert urns == [URN]
        return [
            {
                "urn": URN,
                "type": "DATASET",
                "properties": {
                    "customProperties": [
                        {
                            "key": "ledgerlens.runbookUrl",
                            "value": "https://runbooks.example.invalid/orders",
                        },
                        {
                            "key": "ledgerlens.schema",
                            "value": '[{"name":"event_time"}]',
                        },
                    ]
                },
                "ownership": {
                    "owners": ([{"owner": "urn:li:corpGroup:data-platform"}] if self.owner else [])
                },
            }
        ]

    def get_lineage(self, urn: str, **kwargs: Any) -> list[dict[str, Any]]:
        assert urn == URN
        assert kwargs == {"direction": "downstream", "max_hops": 3, "count": 50}
        return [{"urn": "urn:li:dashboard:(looker,orders)", "degree": 1}]


def _incident() -> Incident:
    return Incident(
        incident_id="INC-1",
        title="Orders stale",
        severity=IncidentSeverity.HIGH,
        detected_at=NOW,
        affected_entities=(URN,),
        trigger=IncidentTrigger(
            trigger_id="trigger-1",
            source="datahub",
            kind="freshness",
            occurred_at=NOW,
            idempotency_key="trigger-1",
        ),
    )


def test_mcp_context_provider_builds_grounded_context_and_blast_radius() -> None:
    context = DataHubMCPContextProvider(
        Client(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )(_incident())

    assert context.metadata["source"] == "official-datahub-mcp"
    assert context.metadata["blastRadiusUrns"] == ["urn:li:dashboard:(looker,orders)"]
    assert context.incident.affected_entities == (
        URN,
        "urn:li:dashboard:(looker,orders)",
    )
    assert context.fact_ids == {
        "root-asset",
        "primary-owner",
        "blast-radius",
        "runbook",
        "schema",
    }


def test_mcp_context_provider_fails_closed_without_owner() -> None:
    provider = DataHubMCPContextProvider(
        Client(owner=False),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    with pytest.raises(DataHubContextError, match="owner"):
        provider(_incident())
