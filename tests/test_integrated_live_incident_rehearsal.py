"""Offline safety tests for the supervised combined live-run harness."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _load_script() -> Any:
    path = ROOT / "scripts" / "run_integrated_live_incident_rehearsal.py"
    spec = importlib.util.spec_from_file_location(
        "run_integrated_live_incident_rehearsal",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


class _ReadClient:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def get_entities(self, urns: list[str]) -> list[dict[str, Any]]:
        self.calls.append(list(urns))
        return self.responses.pop(0)


class _Settings:
    datahub_gms_url = "http://127.0.0.1:18080"
    mcp_command_argv = ("python3",)

    def __init__(self, token: str | None) -> None:
        self._token = token

    def datahub_token_value(self) -> str | None:
        return self._token


def _provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "OPENAI_API_KEY": "test-openai-key",
        "LEDGERLENS_ACTION_AUTHORIZATION_SECRET": "x" * 32,
        "GITHUB_TOKEN": "test-github-token",
        "LEDGERLENS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/services/T/B/SECRET",
        "LEDGERLENS_PAGERDUTY_ROUTING_KEY": "test-routing-key",
        "LEDGERLENS_JIRA_SITE_URL": "https://ledgerlens.test",
        "LEDGERLENS_JIRA_EMAIL": "owner@example.test",
        "LEDGERLENS_JIRA_API_TOKEN": "test-jira-token",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_live_readiness_requires_datahub_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _provider_env(monkeypatch)

    missing = SCRIPT._readiness(
        settings=_Settings(None),
        require_provider_credentials=True,
    )
    ready = SCRIPT._readiness(
        settings=_Settings("datahub-service-token"),
        require_provider_credentials=True,
    )

    assert missing["ready"] is False
    assert "dataHubToken" in missing["missingChecks"]
    assert ready["ready"] is True
    assert ready["secretsSerialized"] is False


def test_preflight_readiness_does_not_require_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LEDGERLENS_LLM_API_KEY",
        "LEDGERLENS_ACTION_AUTHORIZATION_SECRET",
        "GITHUB_TOKEN",
        "LEDGERLENS_SLACK_WEBHOOK_URL",
        "LEDGERLENS_PAGERDUTY_ROUTING_KEY",
        "LEDGERLENS_JIRA_SITE_URL",
        "LEDGERLENS_JIRA_EMAIL",
        "LEDGERLENS_JIRA_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    receipt = SCRIPT._readiness(
        settings=_Settings(None),
        require_provider_credentials=False,
    )

    assert receipt["ready"] is True
    assert receipt["checks"]["providers"] is False
    assert receipt["checks"]["dataHubToken"] is False


def test_anthropic_only_configuration_requires_explicit_model_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.delenv("LEDGERLENS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LEDGERLENS_PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("LEDGERLENS_VERIFIER_PROVIDER", raising=False)
    monkeypatch.delenv("LEDGERLENS_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("LEDGERLENS_VERIFIER_MODELS", raising=False)

    receipt = SCRIPT._readiness(
        settings=_Settings("datahub-service-token"),
        require_provider_credentials=True,
    )

    assert receipt["checks"]["modelRuntime"] is False
    assert "modelRuntime" in receipt["missingChecks"]
    assert "LEDGERLENS_PLANNER_MODEL" in receipt["modelRuntimeError"]
    assert "test-anthropic-key" not in receipt["modelRuntimeError"]


def test_anthropic_only_configuration_stays_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("LEDGERLENS_PLANNER_MODEL", "claude-planner-test")
    monkeypatch.setenv(
        "LEDGERLENS_VERIFIER_MODELS",
        "claude-verifier-one-test,claude-verifier-two-test",
    )

    settings = SCRIPT._role_settings()

    assert settings.resolved_planner_provider().value == "anthropic"
    assert settings.resolved_verifier_provider().value == "anthropic"
    assert settings.planner_model == "claude-planner-test"
    assert settings.verifier_model_ids == (
        "claude-verifier-one-test",
        "claude-verifier-two-test",
    )
    assert settings.anthropic_api_key is not None
    assert settings.openai_api_key is None


def test_read_back_requires_exact_document_urn() -> None:
    urn = "urn:li:document:ledgerlens-integrated-test"
    client = _ReadClient(
        [
            [
                {"urn": "urn:li:document:different"},
                {"urn": urn, "title": "LedgerLens receipt"},
            ]
        ]
    )

    result = SCRIPT._read_back(client, urn, timeout_seconds=0)

    assert result["retrieved"] is True
    assert result["urn"] == urn
    assert result["via"] == "official-datahub-mcp:get_entities"
    assert result["entityDigest"].startswith("sha256:")
    assert client.calls == [[urn]]


def test_read_back_fails_closed_without_result_urn() -> None:
    client = _ReadClient([])

    result = SCRIPT._read_back(client, None, timeout_seconds=0)

    assert result == {
        "retrieved": False,
        "urn": None,
        "attempts": 0,
        "limitation": "write-back result did not expose a document URN",
    }
    assert client.calls == []


def test_failure_text_is_redacted() -> None:
    error = RuntimeError("Authorization: Bearer secret-value")

    rendered = SCRIPT._sanitized_error(error)

    assert "secret-value" not in rendered
    assert "RuntimeError" in rendered
