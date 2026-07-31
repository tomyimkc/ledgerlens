"""Deterministic tests for the isolated official MCP mutation adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from ledgerlens.mcp_mutations import (
    MCPMutationAuthorizationError,
    MCPMutationClient,
    MCPMutationDisabledError,
    MCPMutationNotAllowedError,
    MCPMutationResponseError,
    MCPMutationUnsupportedError,
    MutationAuthorization,
    MutationCall,
    MutationTool,
)


class FakeTransport:
    def __init__(self, result: Any = None) -> None:
        self.result = result or {"structuredContent": {"success": True}}
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.closed = False

    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        normalized = dict(params or {})
        self.calls.append((method, normalized))
        return self.result

    def close(self) -> None:
        self.closed = True


class AcceptingVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[MutationAuthorization, MutationCall, bool]] = []

    def verify(
        self,
        authorization: MutationAuthorization,
        call: MutationCall,
        *,
        preview: bool = False,
    ) -> None:
        self.calls.append((authorization, call, preview))


def _authorization(call: MutationCall) -> MutationAuthorization:
    return MutationAuthorization(
        authorization_id="auth-1",
        policy_version="test/v1",
        actor="operator",
        reason="incident remediation",
        tool=call.tool,
        idempotency_key=call.idempotency_key,
        call_digest=call.digest,
        preview_only=False,
        _issuer=object(),
    )


def _client(
    transport: FakeTransport,
    *,
    enabled: bool = True,
    supported_tools: set[MutationTool] | None = None,
) -> tuple[MCPMutationClient, AcceptingVerifier]:
    verifier = AcceptingVerifier()
    return (
        MCPMutationClient(
            transport,
            enabled=enabled,
            supported_tools=supported_tools,
            authorization_verifier=verifier,
        ),
        verifier,
    )


def test_mutation_client_is_disabled_by_default() -> None:
    transport = FakeTransport()
    call = MutationCall(
        MutationTool.ADD_TAGS,
        {"tag_urns": ["urn:li:tag:incident"], "entity_urns": ["urn:li:dataset:one"]},
        "idem-1",
    )
    client = MCPMutationClient(transport, authorization_verifier=AcceptingVerifier())
    with pytest.raises(MCPMutationDisabledError):
        client.call_tool(call, authorization=_authorization(call))
    assert transport.calls == []


def test_typed_authorization_is_required_before_transport() -> None:
    transport = FakeTransport()
    client = MCPMutationClient(transport, enabled=True)
    call = MutationCall(
        MutationTool.REMOVE_TAGS,
        {"tag_urns": ["urn:li:tag:old"], "entity_urns": ["urn:li:dataset:one"]},
        "idem-2",
    )
    with pytest.raises(MCPMutationAuthorizationError):
        client.call_tool(call, authorization=None)
    assert transport.calls == []


def test_allowlist_and_supported_capabilities_fail_closed() -> None:
    transport = FakeTransport()
    call = MutationCall(
        MutationTool.UPDATE_DESCRIPTION,
        {
            "entity_urn": "urn:li:dataset:one",
            "operation": "replace",
            "description": "incident context",
        },
        "idem-3",
    )
    client = MCPMutationClient(
        transport,
        enabled=True,
        allowlisted_tools={MutationTool.ADD_TAGS},
        authorization_verifier=AcceptingVerifier(),
    )
    with pytest.raises(MCPMutationNotAllowedError):
        client.call_tool(call, authorization=_authorization(call))

    client, _ = _client(transport, supported_tools={MutationTool.ADD_TAGS})
    with pytest.raises(MCPMutationUnsupportedError):
        client.call_tool(call, authorization=_authorization(call))
    assert transport.calls == []


def test_official_tool_name_and_arguments_are_sent_exactly() -> None:
    transport = FakeTransport({"structuredContent": {"success": True, "message": "updated"}})
    client, verifier = _client(transport)
    call = MutationCall(
        MutationTool.UPDATE_DESCRIPTION,
        {
            "entity_urn": "urn:li:dataset:one",
            "operation": "append",
            "description": "\nIncident INC-7 is monitoring.",
        },
        "idem-4",
    )
    result = client.call_tool(call, authorization=_authorization(call))
    assert result == {"success": True, "message": "updated"}
    assert transport.calls == [
        (
            "tools/call",
            {
                "name": "update_description",
                "arguments": dict(call.arguments),
            },
        )
    ]
    assert verifier.calls[0][1] == call


def test_convenience_methods_use_official_structured_property_surface() -> None:
    transport = FakeTransport()
    client, _ = _client(transport)
    call = MutationCall(
        MutationTool.ADD_STRUCTURED_PROPERTIES,
        {
            "property_values": {
                "urn:li:structuredProperty:ledgerlens.incidentStatus": ["monitoring"]
            },
            "entity_urns": ["urn:li:dataset:one"],
        },
        "idem-5",
    )
    client.set_structured_properties(
        property_values=call.arguments["property_values"],
        entity_urns=["urn:li:dataset:one"],
        idempotency_key=call.idempotency_key,
        authorization=_authorization(call),
    )
    assert transport.calls[0][1]["name"] == "add_structured_properties"


def test_sensitive_credential_fields_are_rejected_and_results_are_redacted() -> None:
    with pytest.raises(ValueError, match="sensitive credential field"):
        MutationCall(
            MutationTool.SAVE_DOCUMENT,
            {
                "document_type": "Note",
                "title": "Unsafe",
                "content": "body",
                "token": "raw-secret",
            },
            "idem-6",
        )
    with pytest.raises(ValueError, match="raw credential-like value"):
        MutationCall(
            MutationTool.SAVE_DOCUMENT,
            {
                "document_type": "Note",
                "title": "Unsafe",
                "content": "Accidentally copied Bearer raw-secret",
            },
            "idem-6-value",
        )

    transport = FakeTransport(
        {
            "structuredContent": {
                "success": True,
                "debug": {
                    "authorization": "Bearer raw-token",
                    "message": "upstream said Bearer another-token",
                },
            }
        }
    )
    client, _ = _client(transport)
    call = MutationCall(
        MutationTool.ADD_TAGS,
        {"tag_urns": ["urn:li:tag:incident"], "entity_urns": ["urn:li:dataset:one"]},
        "idem-7",
    )
    result = client.call_tool(call, authorization=_authorization(call))
    assert result["debug"]["authorization"] == "[REDACTED]"
    assert result["debug"]["message"] == "upstream said Bearer [REDACTED]"
    assert "raw-token" not in repr(result)
    assert "another-token" not in repr(result)


def test_unsuccessful_tool_payload_is_typed() -> None:
    transport = FakeTransport(
        {
            "structuredContent": {
                "success": False,
                "message": "denied with token=raw-token",
            }
        }
    )
    client, _ = _client(transport)
    call = MutationCall(
        MutationTool.ADD_TAGS,
        {"tag_urns": ["urn:li:tag:incident"], "entity_urns": ["urn:li:dataset:one"]},
        "idem-8",
    )
    with pytest.raises(MCPMutationResponseError, match=r"token=\[REDACTED\]"):
        client.call_tool(call, authorization=_authorization(call))


def test_unknown_or_invalid_official_arguments_never_reach_transport() -> None:
    transport = FakeTransport()
    client, _ = _client(transport)
    with pytest.raises(MCPMutationNotAllowedError):
        client.call_tool(
            "delete_entity",
            {"entity_urn": "urn:li:dataset:one"},
            authorization=None,
            idempotency_key="idem-9",
        )
    with pytest.raises(ValueError, match="description is required"):
        MutationCall(
            MutationTool.UPDATE_DESCRIPTION,
            {"entity_urn": "urn:li:dataset:one", "operation": "replace"},
            "idem-10",
        )
    assert transport.calls == []


def test_close_is_forwarded_to_injected_transport() -> None:
    transport = FakeTransport()
    client, _ = _client(transport)
    client.close()
    assert transport.closed is True
