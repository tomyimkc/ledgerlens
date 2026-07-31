"""Environment-backed configuration with conservative, read-only defaults."""

from __future__ import annotations

import shlex
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    The 020s credential deliberately has exactly one environment alias:
    ``SOPHIA_020S_KEY``.  ``SecretStr`` prevents accidental disclosure through
    repr/serialization, and callers must explicitly request the secret value.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    datahub_gms_url: str = Field(
        default="http://localhost:8080",
        validation_alias="DATAHUB_GMS_URL",
    )
    datahub_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DATAHUB_GMS_TOKEN", "DATAHUB_TOKEN"),
        repr=False,
    )
    datahub_timeout_seconds: float = Field(
        default=8.0,
        gt=0,
        le=60,
        validation_alias="DATAHUB_TIMEOUT_SECONDS",
    )

    datahub_mcp_url: str | None = Field(default=None, validation_alias="DATAHUB_MCP_URL")
    datahub_mcp_command: str | None = Field(
        default="mcp-server-datahub",
        validation_alias="DATAHUB_MCP_COMMAND",
    )
    mcp_timeout_seconds: float = Field(
        default=12.0,
        gt=0,
        le=120,
        validation_alias="LEDGERLENS_MCP_TIMEOUT_SECONDS",
    )

    llm_enabled: bool = Field(default=False, validation_alias="LEDGERLENS_LLM_ENABLED")
    llm_base_url: str = Field(
        default="https://api.020s.com/v1",
        validation_alias="LEDGERLENS_LLM_BASE_URL",
    )
    llm_model: str = Field(
        default="gpt-5.6-sol",
        min_length=1,
        validation_alias="LEDGERLENS_LLM_MODEL",
    )
    llm_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=120,
        validation_alias="LEDGERLENS_LLM_TIMEOUT_SECONDS",
    )
    sophia_020s_key: SecretStr | None = Field(
        default=None,
        validation_alias="SOPHIA_020S_KEY",
        repr=False,
    )

    mutations_enabled: bool = Field(
        default=False,
        validation_alias="LEDGERLENS_MUTATIONS_ENABLED",
    )

    @field_validator("datahub_gms_url", "llm_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must use http:// or https://")
        return value

    @field_validator("datahub_mcp_url")
    @classmethod
    def normalize_optional_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("MCP URL must use http:// or https://")
        return value

    @field_validator("datahub_mcp_command")
    @classmethod
    def normalize_optional_command(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()

    @model_validator(mode="after")
    def enforce_safe_defaults(self) -> Settings:
        if self.mutations_enabled:
            raise ValueError("LedgerLens is read-only; mutations cannot be enabled")
        if self.llm_enabled and self.sophia_020s_key is None:
            raise ValueError("LEDGERLENS_LLM_ENABLED requires SOPHIA_020S_KEY")
        if self.llm_base_url != "https://api.020s.com/v1":
            raise ValueError("LedgerLens only sends SOPHIA_020S_KEY to https://api.020s.com/v1")
        return self

    @property
    def mcp_command_argv(self) -> tuple[str, ...] | None:
        """Return a shell-free argv tuple for the configured stdio server."""

        if self.datahub_mcp_command is None:
            return None
        argv = tuple(shlex.split(self.datahub_mcp_command))
        if not argv:
            return None
        return argv

    def datahub_token_value(self) -> str | None:
        return self.datahub_token.get_secret_value() if self.datahub_token else None

    def require_020s_key(self) -> str:
        if self.sophia_020s_key is None:
            raise ValueError("SOPHIA_020S_KEY is required for 020s mode")
        return self.sophia_020s_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process settings once; tests may call ``cache_clear``."""

    return Settings()
