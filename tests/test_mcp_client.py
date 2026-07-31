"""Deterministic tests for HTTP, stdio, and result normalization."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from ledgerlens.mcp_client import (
    DataHubMCPClient,
    HttpMCPTransport,
    MCPReadOnlyError,
    MCPRemoteError,
    StdioMCPTransport,
)


class FakeTransport:
    def __init__(self, results: Mapping[str, Any]) -> None:
        self.results = results
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.closed = False

    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        params = dict(params or {})
        self.calls.append((method, params))
        name = params.get("name")
        return self.results[str(name)]

    def close(self) -> None:
        self.closed = True


def test_tools_are_normalized_from_structured_and_text_content() -> None:
    transport = FakeTransport(
        {
            "search": {
                "structuredContent": {
                    "searchResults": [
                        {
                            "entity": {"urn": "urn:one", "type": "DATASET", "name": "One"},
                            "matchedFields": [{"name": "name", "value": "One"}],
                        }
                    ]
                }
            },
            "get_entities": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"result": [{"urn": "urn:one", "customProperties": {"x": "y"}}]}
                        ),
                    }
                ]
            },
            "get_lineage": {
                "structuredContent": {
                    "downstreams": {
                        "searchResults": [
                            {
                                "entity": {"urn": "urn:two", "type": "DATASET"},
                                "degree": 1,
                            }
                        ]
                    }
                }
            },
        }
    )
    client = DataHubMCPClient(transport)
    assert client.search("one")[0]["urn"] == "urn:one"
    assert client.get_entities(["urn:one"])[0]["customProperties"] == {"x": "y"}
    lineage = client.get_lineage("urn:one")
    assert lineage[0]["urn"] == "urn:two"
    assert lineage[0]["direction"] == "downstream"
    assert lineage[0]["degree"] == 1
    search_call = transport.calls[0][1]["arguments"]
    assert search_call == {"query": "one", "num_results": 20}
    lineage_call = transport.calls[2][1]["arguments"]
    assert lineage_call == {
        "urn": "urn:one",
        "upstream": False,
        "max_hops": 3,
        "max_results": 50,
    }


def test_search_infers_entity_type_from_official_oss_shape() -> None:
    transport = FakeTransport(
        {
            "search": {
                "structuredContent": {
                    "searchResults": [
                        {
                            "entity": {
                                "urn": "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,x,PROD)"
                            }
                        },
                        {"entity": {"urn": "urn:li:corpuser:datahub"}},
                    ]
                }
            }
        }
    )
    results = DataHubMCPClient(transport).search("*", entity_types=("DATASET",))
    assert [item["type"] for item in results] == ["DATASET"]


def test_empty_official_lineage_section_returns_no_records() -> None:
    transport = FakeTransport(
        {
            "get_lineage": {
                "structuredContent": {
                    "downstreams": {
                        "total": 0,
                        "facets": [],
                    }
                }
            }
        }
    )
    assert DataHubMCPClient(transport).get_lineage("urn:one") == []


def test_mutation_tools_are_never_callable() -> None:
    transport = FakeTransport({})
    client = DataHubMCPClient(transport)
    with pytest.raises(MCPReadOnlyError):
        client.call_tool("update_description", {"urn": "urn:one"})
    assert transport.calls == []


def test_tool_error_content_is_typed() -> None:
    transport = FakeTransport(
        {
            "search": {
                "isError": True,
                "content": [{"type": "text", "text": "DataHub unavailable"}],
            }
        }
    )
    with pytest.raises(MCPRemoteError, match="DataHub unavailable"):
        DataHubMCPClient(transport).search("*")


def test_http_transport_initializes_session_and_parses_sse() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "serverInfo": {"name": "datahub", "version": "1"},
                    },
                },
            )
        assert request.headers["mcp-session-id"] == "session-1"
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                "event: message\n"
                f"data: {json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': {'ok': True}})}"
                "\n\n"
            ),
        )

    transport = HttpMCPTransport(
        "http://mcp.test/mcp",
        transport=httpx.MockTransport(handler),
    )
    assert transport.request("tools/list") == {"ok": True}
    assert [call["method"] for call in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]


def test_stdio_transport_round_trip_and_forces_mutations_off() -> None:
    server = r"""
import json, os, sys
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {}}
    else:
        result = {
            "mutationFlag": os.environ.get("TOOLS_IS_MUTATION_ENABLED"),
            "method": method,
        }
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
"""
    transport = StdioMCPTransport(
        [sys.executable, "-u", "-c", server],
        timeout=3,
        env={"TOOLS_IS_MUTATION_ENABLED": "true"},
    )
    try:
        result = transport.request("tools/list")
    finally:
        transport.close()
    assert result == {"mutationFlag": "false", "method": "tools/list"}


def test_stdio_transport_requires_explicit_mutation_opt_in() -> None:
    server = r"""
import json, os, sys
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "notifications/initialized":
        continue
    result = (
        {"protocolVersion": "2025-06-18", "capabilities": {}}
        if method == "initialize"
        else {"mutationFlag": os.environ.get("TOOLS_IS_MUTATION_ENABLED")}
    )
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
"""
    transport = StdioMCPTransport(
        [sys.executable, "-u", "-c", server],
        timeout=3,
        allow_mutations=True,
    )
    try:
        result = transport.request("tools/list")
    finally:
        transport.close()
    assert result == {"mutationFlag": "true"}
