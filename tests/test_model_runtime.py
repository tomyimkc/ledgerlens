"""Tests for model runtime helpers including RecordingJsonClient."""

from __future__ import annotations

from typing import Any

from ledgerlens.model_runtime import RecordingJsonClient


class _FakeInner:
    model = "gpt-4o"
    base_url = "https://api.openai.com/v1"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"confidence": 0.9, "summary": "ok", "actions": []}

    def close(self) -> None:
        return None


def test_recording_json_client_captures_prompts_and_output() -> None:
    records: list[dict[str, Any]] = []
    client = RecordingJsonClient(_FakeInner(), role="planner", records=records)  # type: ignore[arg-type]
    result = client.complete_json(
        system="You are a planner.",
        prompt="Plan tools.",
        context={"agentToolCatalog": {"tools": []}},
        temperature=0.0,
    )
    assert result["summary"] == "ok"
    assert len(records) == 1
    assert records[0]["role"] == "planner"
    assert records[0]["model"] == "gpt-4o"
    assert records[0]["input"]["system"] == "You are a planner."
    assert records[0]["input"]["userPrompt"] == "Plan tools."
    assert records[0]["input"]["context"]["agentToolCatalog"]["tools"] == []
    assert records[0]["output"]["json"]["confidence"] == 0.9


def test_anthropic_json_client_parses_text_blocks() -> None:
    import json

    import httpx

    from ledgerlens.model_runtime import AnthropicJsonClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/messages")
        assert "x-api-key" in request.headers
        body = json.loads(request.content)
        assert body["model"] == "claude-3-5-haiku-latest"
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": json.dumps({"ok": True, "n": 1})}]},
            request=request,
        )

    client = AnthropicJsonClient(
        api_key="secret-anthropic",
        model="claude-3-5-haiku-latest",
        transport=httpx.MockTransport(handler),
    )
    result = client.complete_json(system="sys", prompt="hi")
    assert result == {"ok": True, "n": 1}
    client.close()
