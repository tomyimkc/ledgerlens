"""Tests for the secret-safe JSON planner/verifier runtime."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ledgerlens.model_runtime import (
    ModelRuntimeError,
    OpenAICompatibleJsonClient,
    parse_json_object,
)


def test_json_client_sends_context_without_secret() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"decision":"approve"}'}}]},
        )

    client = OpenAICompatibleJsonClient(
        base_url="https://api.020s.com/v1",
        api_key="top-secret",
        model="gpt-5.6-terra",
        transport=httpx.MockTransport(handler),
    )
    result = client.complete_json(
        system="Return JSON.",
        prompt="Verify the proposed action.",
        context={"assetUrn": "urn:li:dataset:test"},
    )

    assert result == {"decision": "approve"}
    assert seen["authorization"] == "Bearer top-secret"
    assert "top-secret" not in json.dumps(seen["body"])
    assert "top-secret" not in repr(client)


def test_json_code_fence_is_allowed_but_prose_is_not() -> None:
    assert parse_json_object('```json\n{"ok":true}\n```') == {"ok": True}
    with pytest.raises(ModelRuntimeError, match="not valid JSON"):
        parse_json_object('Approved. {"ok": true}')


@pytest.mark.parametrize("raw", ("[]", '"text"', "null", ""))
def test_non_object_responses_fail_closed(raw: str) -> None:
    with pytest.raises(ModelRuntimeError):
        parse_json_object(raw)


def test_transport_error_does_not_expose_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, text="unavailable")

    client = OpenAICompatibleJsonClient(
        base_url="https://api.020s.com/v1",
        api_key="do-not-leak",
        model="gpt-5.6-sol",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ModelRuntimeError) as captured:
        client.complete_json(system="Return JSON.", prompt="Plan.")
    assert "do-not-leak" not in str(captured.value)
