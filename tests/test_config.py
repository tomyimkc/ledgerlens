"""Configuration safety and environment contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ledgerlens.config import LlmProvider, Settings


def test_safe_defaults_are_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATAHUB_GMS_URL",
        "DATAHUB_GMS_TOKEN",
        "DATAHUB_TOKEN",
        "DATAHUB_MCP_URL",
        "DATAHUB_MCP_COMMAND",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LEDGERLENS_LLM_API_KEY",
        "LEDGERLENS_LLM_ENABLED",
        "LEDGERLENS_LLM_BASE_URL",
        "LEDGERLENS_LLM_MODEL",
        "LEDGERLENS_LLM_PROVIDER",
        "LEDGERLENS_MUTATIONS_ENABLED",
        "LEDGERLENS_INCIDENT_COMMANDER_ENABLED",
        "LEDGERLENS_AUTONOMOUS_EXECUTION_ENABLED",
        "LEDGERLENS_AI_VERIFICATION_ENABLED",
        "LEDGERLENS_PLANNER_MODEL",
        "LEDGERLENS_VERIFIER_MODELS",
        "LEDGERLENS_VERIFIER_QUORUM",
        "LEDGERLENS_VERIFIER_MIN_CONFIDENCE",
        "LEDGERLENS_ACTION_AUTHORIZATION_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.datahub_gms_url == "http://localhost:8080"
    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == "gpt-4o"
    assert settings.llm_provider is LlmProvider.OPENAI
    assert settings.llm_enabled is False
    assert settings.mutations_enabled is False
    assert settings.incident_commander_enabled is False
    assert settings.autonomous_execution_enabled is False
    assert settings.ai_verification_enabled is False
    assert settings.planner_model == "gpt-4o"
    assert settings.verifier_model_ids == ("gpt-4o-mini", "gpt-4-turbo")
    assert settings.verifier_quorum == 2
    assert settings.verifier_min_confidence == 0.85
    assert settings.llm_api_key is None
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None


def test_environment_aliases_and_shell_free_mcp_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://datahub:8080/")
    monkeypatch.setenv("DATAHUB_GMS_TOKEN", "datahub-secret")
    monkeypatch.setenv("DATAHUB_MCP_COMMAND", "uvx mcp-server-datahub --transport stdio")
    monkeypatch.setenv("OPENAI_API_KEY", "top-secret")
    monkeypatch.setenv("LEDGERLENS_LLM_ENABLED", "true")
    settings = Settings(_env_file=None)
    assert settings.datahub_gms_url == "http://datahub:8080"
    assert settings.datahub_token_value() == "datahub-secret"
    assert settings.mcp_command_argv == (
        "uvx",
        "mcp-server-datahub",
        "--transport",
        "stdio",
    )
    assert settings.require_llm_api_key() == "top-secret"
    assert "top-secret" not in repr(settings)
    assert "datahub-secret" not in repr(settings)


def test_openai_and_anthropic_keys_resolve_by_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LEDGERLENS_LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    settings = Settings(_env_file=None)
    assert settings.api_key_for_provider(LlmProvider.OPENAI) == "openai-secret"
    assert settings.api_key_for_provider(LlmProvider.ANTHROPIC) == "anthropic-secret"
    assert settings.base_url_for_provider(LlmProvider.ANTHROPIC) == "https://api.anthropic.com"


def test_llm_enabled_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_LLM_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LEDGERLENS_LLM_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None)


def test_mutations_cannot_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_MUTATIONS_ENABLED", "true")
    with pytest.raises(ValidationError, match="mutations cannot be enabled"):
        Settings(_env_file=None)


def test_autonomous_incident_commander_requires_full_verification_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDGERLENS_INCIDENT_COMMANDER_ENABLED", "true")
    monkeypatch.setenv("LEDGERLENS_MUTATIONS_ENABLED", "true")
    monkeypatch.setenv("LEDGERLENS_AUTONOMOUS_EXECUTION_ENABLED", "true")
    with pytest.raises(ValidationError, match="requires AI verification"):
        Settings(_env_file=None)

    monkeypatch.setenv("LEDGERLENS_AI_VERIFICATION_ENABLED", "true")
    with pytest.raises(ValidationError, match="authorization secret"):
        Settings(_env_file=None)

    monkeypatch.setenv("LEDGERLENS_ACTION_AUTHORIZATION_SECRET", "signing-secret")
    settings = Settings(_env_file=None)
    assert settings.autonomous_execution_enabled is True
    assert settings.require_action_authorization_secret() == "signing-secret"
    assert "signing-secret" not in repr(settings)


def test_verifier_quorum_cannot_exceed_configured_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDGERLENS_AI_VERIFICATION_ENABLED", "true")
    monkeypatch.setenv("LEDGERLENS_VERIFIER_MODELS", "gpt-4o-mini")
    monkeypatch.setenv("LEDGERLENS_VERIFIER_QUORUM", "2")
    with pytest.raises(ValidationError, match="quorum exceeds"):
        Settings(_env_file=None)


def test_any_https_llm_endpoint_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "byo-key")
    monkeypatch.setenv("LEDGERLENS_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LEDGERLENS_LLM_MODEL", "gpt-4o")
    settings = Settings(_env_file=None)
    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == "gpt-4o"


def test_llm_key_is_not_sent_over_plaintext_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "byo-key")
    monkeypatch.setenv("LEDGERLENS_LLM_BASE_URL", "http://api.example.com/v1")
    with pytest.raises(ValidationError, match="only be sent over https"):
        Settings(_env_file=None)
