"""Network-mocked tests for the read-only DataHub client."""

from __future__ import annotations

import json

import httpx
import pytest

from ledgerlens.datahub_client import (
    DataHubClient,
    DataHubGraphQLError,
    DataHubHTTPError,
    DataHubReadOnlyError,
    DataHubTimeoutError,
)

URN = "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,F-001,PROD)"


def _client(handler: httpx.MockTransport) -> DataHubClient:
    return DataHubClient("http://datahub.test", token="oss-token", transport=handler)


def test_search_entity_lineage_and_openapi_audit_are_normalized() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer oss-token"
        if request.url.path == "/openapi/v3/entity/dataset/" + httpx.URL(URN).raw_path.decode():
            raise AssertionError("URN must be percent encoded")
        if request.url.path.startswith("/openapi/v3/entity/dataset/"):
            assert request.url.params["aspects"] == (
                "datasetProperties,ownership,globalTags,upstreamLineage"
            )
            assert request.url.params["systemMetadata"] == "true"
            return httpx.Response(
                200,
                json={
                    "urn": URN,
                    "datasetProperties": {
                        "value": {"name": "F-001"},
                        "created": {
                            "time": 1_700_000_000_000,
                            "actor": "urn:li:corpuser:bot",
                        },
                        "systemMetadata": {
                            "lastObserved": 1_700_000_000_100,
                            "runId": "ledgerlens-run",
                        },
                    },
                },
            )
        body = json.loads(request.content)
        query = body["query"]
        if "LedgerLensSearch" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "searchAcrossEntities": {
                            "start": 0,
                            "count": 1,
                            "total": 1,
                            "searchResults": [
                                {
                                    "matchedFields": [{"name": "name", "value": "F-001"}],
                                    "entity": {
                                        "urn": URN,
                                        "type": "DATASET",
                                        "name": "F-001",
                                        "properties": {"description": "finding"},
                                    },
                                }
                            ],
                        }
                    }
                },
            )
        if "LedgerLensEntity" in query:
            return httpx.Response(
                200,
                json={"data": {"entity": {"urn": URN, "type": "DATASET", "name": "F-001"}}},
            )
        if "LedgerLensLineage" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "searchAcrossLineage": {
                            "start": 0,
                            "count": 1,
                            "total": 1,
                            "searchResults": [
                                {
                                    "degree": 1,
                                    "entity": {"urn": "urn:li:dataset:next", "type": "DATASET"},
                                }
                            ],
                        }
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = _client(httpx.MockTransport(handler))
    search = client.search("F-001")
    assert search.total == 1
    assert search.hits[0].urn == URN
    assert search.hits[0].description == "finding"

    entity = client.get_entity(URN)
    assert entity["name"] == "F-001"

    lineage = client.get_lineage(URN)
    assert lineage.hits[0].urn == "urn:li:dataset:next"
    assert lineage.hits[0].degree == 1
    assert lineage.hits[0].direction == "DOWNSTREAM"

    audit = client.get_audit_metadata(URN)
    assert audit.latest_ingestion_time_ms == 1_700_000_000_100
    assert audit.audit_stamps[0].actor == "urn:li:corpuser:bot"
    assert audit.system_metadata["datasetProperties"]["runId"] == "ledgerlens-run"
    assert len(seen) == 4


def test_token_is_optional_for_oss() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "data": {
                    "searchAcrossEntities": {
                        "start": 0,
                        "count": 0,
                        "total": 0,
                        "searchResults": [],
                    }
                }
            },
        )

    client = DataHubClient("http://oss.test", transport=httpx.MockTransport(handler))
    assert client.search("*").hits == ()


def test_graphql_mutations_are_refused_before_network() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be reached")

    client = DataHubClient("http://datahub.test", transport=httpx.MockTransport(handler))
    with pytest.raises(DataHubReadOnlyError):
        client.graphql("mutation DeleteEverything { delete }")


def test_graphql_and_http_errors_are_typed() -> None:
    def graphql_error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "bad query"}]})

    with pytest.raises(DataHubGraphQLError, match="bad query"):
        DataHubClient(
            "http://datahub.test",
            transport=httpx.MockTransport(graphql_error),
        ).search("*")

    def http_error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="not ready")

    with pytest.raises(DataHubHTTPError) as exc_info:
        DataHubClient(
            "http://datahub.test",
            transport=httpx.MockTransport(http_error),
        ).search("*")
    assert exc_info.value.status_code == 503


def test_timeout_is_typed() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = DataHubClient(
        "http://datahub.test",
        timeout=0.1,
        transport=httpx.MockTransport(timeout),
    )
    with pytest.raises(DataHubTimeoutError):
        client.search("*")
