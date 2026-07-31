"""Configuration safety and environment contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ledgerlens.config import Settings


def test_safe_defaults_are_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATAHUB_GMS_URL",
        "DATAHUB_GMS_TOKEN",
        "DATAHUB_TOKEN",
        "DATAHUB_MCP_URL",
        "DATAHUB_MCP_COMMAND",
        "SOPHIA_020S_KEY",
        "LEDGERLENS_LLM_ENABLED",
        "LEDGERLENS_LLM_BASE_URL",
        "LEDGERLENS_LLM_MODEL",
        "LEDGERLENS_MUTATIONS_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.datahub_gms_url == "http://localhost:8080"
    assert settings.llm_base_url == "https://api.020s.com/v1"
    assert settings.llm_model == "gpt-5.6-sol"
    assert settings.llm_enabled is False
    assert settings.mutations_enabled is False
    assert settings.sophia_020s_key is None


def test_environment_aliases_and_shell_free_mcp_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://datahub:8080/")
    monkeypatch.setenv("DATAHUB_GMS_TOKEN", "datahub-secret")
    monkeypatch.setenv("DATAHUB_MCP_COMMAND", "uvx mcp-server-datahub --transport stdio")
    monkeypatch.setenv("SOPHIA_020S_KEY", "top-secret")
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
    assert settings.require_020s_key() == "top-secret"
    assert "top-secret" not in repr(settings)
    assert "datahub-secret" not in repr(settings)


def test_llm_enabled_requires_exact_key_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_LLM_ENABLED", "true")
    monkeypatch.delenv("SOPHIA_020S_KEY", raising=False)
    with pytest.raises(ValidationError, match="requires SOPHIA_020S_KEY"):
        Settings(_env_file=None)


def test_mutations_cannot_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_MUTATIONS_ENABLED", "true")
    with pytest.raises(ValidationError, match="mutations cannot be enabled"):
        Settings(_env_file=None)


def test_020s_key_cannot_be_redirected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_LLM_BASE_URL", "https://example.invalid/v1")
    with pytest.raises(ValidationError, match="only sends SOPHIA_020S_KEY"):
        Settings(_env_file=None)
