"""Agent tool catalog: flexible AI selection, registered tool types."""

from __future__ import annotations

from ledgerlens.runtime_factory import build_policy_gate
from ledgerlens.tool_catalog import (
    TOOL_SPECS,
    build_agent_tool_catalog,
    register_tool_spec,
)


def test_build_catalog_from_targets() -> None:
    catalog = build_agent_tool_catalog(
        {
            "github.issue.create": ["org/repo"],
            "slack.message.post": ["#inc"],
        }
    )
    assert len(catalog.tools) == 2
    gh = catalog.get("github.issue.create")
    assert gh is not None
    assert gh.targets == ("org/repo",)
    payload = catalog.to_agent_dict()
    assert payload["version"].startswith("agent-tool-catalog")
    assert {t["action_type"] for t in payload["tools"]} == {
        "github.issue.create",
        "slack.message.post",
    }


def test_register_custom_tool_then_policy_accepts() -> None:
    name = "custom.webhook.post"
    register_tool_spec(
        name,
        title="Post webhook",
        description="Custom operator webhook",
        allowed_parameter_keys=("url", "body"),
        required_parameter_keys=("url",),
        category="custom",
    )
    assert name in TOOL_SPECS
    catalog = build_agent_tool_catalog({name: ["https://hooks.example/inc"]})
    assert catalog.get(name) is not None
    gate = build_policy_gate({name: ["https://hooks.example/inc"]})
    assert any(a.action_type == name for a in gate.config.allowances)
