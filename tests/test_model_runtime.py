"""Tests for model runtime helpers including RecordingJsonClient."""

from __future__ import annotations

from typing import Any

from ledgerlens.model_runtime import RecordingJsonClient


class _FakeInner:
    model = "gpt-5.6-sol"
    base_url = "https://api.020s.com/v1"

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
    assert records[0]["model"] == "gpt-5.6-sol"
    assert records[0]["input"]["system"] == "You are a planner."
    assert records[0]["input"]["userPrompt"] == "Plan tools."
    assert records[0]["input"]["context"]["agentToolCatalog"]["tools"] == []
    assert records[0]["output"]["json"]["confidence"] == 0.9
