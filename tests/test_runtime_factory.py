"""Tests for 020s role and deterministic policy factories."""

from __future__ import annotations

import json

import httpx
import pytest

from ledgerlens.config import Settings
from ledgerlens.runtime_factory import build_020s_ai_roles, build_policy_gate


def _transport(content: dict[str, object]) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(content)}}]},
            request=request,
        )
    )


def test_020s_roles_use_distinct_configured_models() -> None:
    settings = Settings(
        _env_file=None,
        ai_verification_enabled=True,
        llm_api_key="safe-test-key",
        planner_model="gpt-5.6-sol",
        verifier_models="gpt-5.6-terra,gpt-5.5",
        verifier_quorum=2,
    )
    roles = build_020s_ai_roles(
        settings,
        transports={
            "gpt-5.6-sol": _transport({}),
            "gpt-5.6-terra": _transport({}),
            "gpt-5.5": _transport({}),
        },
    )

    assert roles.planner.family == "gpt-5.6-sol"
    assert roles.verifier_panel.config.quorum == 2
    assert len(roles.clients) == 3
    assert "safe-test-key" not in repr(roles.clients)
    roles.close()


def test_planner_cannot_overlap_verifier_models() -> None:
    settings = Settings(
        _env_file=None,
        ai_verification_enabled=True,
        llm_api_key="safe-test-key",
        planner_model="gpt-5.6-sol",
        verifier_models="gpt-5.6-sol,gpt-5.5",
        verifier_quorum=2,
    )
    with pytest.raises(ValueError, match="must not also be"):
        build_020s_ai_roles(settings)


def test_policy_gate_uses_exact_targets_and_parameter_contracts() -> None:
    gate = build_policy_gate(
        {
            "github.issue.create": ["tomyimkc/ledgerlens"],
            "slack.message.post": ["#inc-data-platform"],
            "pagerduty.event.trigger": ["pagerduty:events-v2"],
            "jira.issue.create": ["DATAOPS"],
        }
    )

    assert gate.config.required_quorum == 2
    assert {item.action_type for item in gate.config.allowances} == {
        "github.issue.create",
        "slack.message.post",
        "pagerduty.event.trigger",
        "jira.issue.create",
    }
