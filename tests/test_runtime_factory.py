"""Tests for LLM role and deterministic policy factories."""

from __future__ import annotations

import json

import httpx
import pytest

from ledgerlens.config import Settings
from ledgerlens.runtime_factory import build_ai_roles, build_policy_gate


def _transport(content: dict[str, object]) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(content)}}]},
            request=request,
        )
    )


def test_ai_roles_use_distinct_configured_models() -> None:
    settings = Settings(
        _env_file=None,
        ai_verification_enabled=True,
        openai_api_key="safe-test-key",
        planner_model="gpt-4o",
        verifier_models="gpt-4o-mini,gpt-4-turbo",
        verifier_quorum=2,
    )
    roles = build_ai_roles(
        settings,
        transports={
            "gpt-4o": _transport({}),
            "gpt-4o-mini": _transport({}),
            "gpt-4-turbo": _transport({}),
        },
    )

    assert roles.planner.family == "gpt-4o"
    assert roles.verifier_panel.config.quorum == 2
    assert len(roles.clients) == 3
    assert "safe-test-key" not in repr(roles.clients)
    roles.close()


def test_planner_cannot_overlap_verifier_models() -> None:
    settings = Settings(
        _env_file=None,
        ai_verification_enabled=True,
        openai_api_key="safe-test-key",
        planner_model="gpt-4o",
        verifier_models="gpt-4o,gpt-4o-mini",
        verifier_quorum=2,
    )
    with pytest.raises(ValueError, match="must not also be"):
        build_ai_roles(settings)


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


def test_fact_contract_is_shared_by_agent_catalog_and_policy_gate() -> None:
    required = {
        "github.issue.create": ["incident-id", "primary-owner"],
    }
    settings = Settings(
        _env_file=None,
        ai_verification_enabled=True,
        openai_api_key="safe-test-key",
        planner_model="gpt-4o",
        verifier_models="gpt-4o-mini,gpt-4-turbo",
        verifier_quorum=2,
    )
    targets = {"github.issue.create": ["tomyimkc/ledgerlens"]}
    roles = build_ai_roles(
        settings,
        transports={
            "gpt-4o": _transport({}),
            "gpt-4o-mini": _transport({}),
            "gpt-4-turbo": _transport({}),
        },
        action_targets=targets,
        required_evidence_fact_ids=required,
    )
    gate = build_policy_gate(targets, required_evidence_fact_ids=required)

    assert roles.planner.tool_catalog is not None
    assert roles.planner.tool_catalog.tools[0].required_evidence_fact_ids == (
        "incident-id",
        "primary-owner",
    )
    assert gate.config.allowances[0].required_evidence_fact_ids == frozenset(
        {"incident-id", "primary-owner"}
    )
    roles.close()
