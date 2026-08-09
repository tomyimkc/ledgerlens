"""Environment-backed configuration with conservative, read-only defaults."""

from __future__ import annotations

import shlex
from enum import StrEnum
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmProvider(StrEnum):
    """Native LLM providers for planner/verifier roles."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"


class Settings(BaseSettings):
    """Runtime settings.

    Planner/verifier models use native OpenAI or Anthropic APIs (or any
    OpenAI-compatible base URL). Prefer ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``;
    ``LEDGERLENS_LLM_API_KEY`` is a generic fallback for either provider.
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
    llm_provider: LlmProvider = Field(
        default=LlmProvider.OPENAI,
        validation_alias="LEDGERLENS_LLM_PROVIDER",
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="LEDGERLENS_LLM_BASE_URL",
    )
    llm_model: str = Field(
        default="gpt-4o",
        min_length=1,
        validation_alias="LEDGERLENS_LLM_MODEL",
    )
    llm_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=120,
        validation_alias="LEDGERLENS_LLM_TIMEOUT_SECONDS",
    )
    # Generic fallback key (either provider). Prefer OPENAI_API_KEY / ANTHROPIC_API_KEY.
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LEDGERLENS_LLM_API_KEY",
        repr=False,
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "LEDGERLENS_OPENAI_API_KEY"),
        repr=False,
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "LEDGERLENS_ANTHROPIC_API_KEY"),
        repr=False,
    )

    mutations_enabled: bool = Field(
        default=False,
        validation_alias="LEDGERLENS_MUTATIONS_ENABLED",
    )
    incident_commander_enabled: bool = Field(
        default=False,
        validation_alias="LEDGERLENS_INCIDENT_COMMANDER_ENABLED",
    )
    autonomous_execution_enabled: bool = Field(
        default=False,
        validation_alias="LEDGERLENS_AUTONOMOUS_EXECUTION_ENABLED",
    )
    ai_verification_enabled: bool = Field(
        default=False,
        validation_alias="LEDGERLENS_AI_VERIFICATION_ENABLED",
    )
    planner_model: str = Field(
        default="gpt-4o",
        min_length=1,
        validation_alias="LEDGERLENS_PLANNER_MODEL",
    )
    planner_provider: LlmProvider | None = Field(
        default=None,
        validation_alias="LEDGERLENS_PLANNER_PROVIDER",
    )
    verifier_models: str = Field(
        # Must not include planner_model (independence rule).
        default="gpt-4o-mini,gpt-4-turbo",
        min_length=1,
        validation_alias="LEDGERLENS_VERIFIER_MODELS",
    )
    verifier_provider: LlmProvider | None = Field(
        default=None,
        validation_alias="LEDGERLENS_VERIFIER_PROVIDER",
    )
    verifier_quorum: int = Field(
        default=2,
        ge=1,
        le=5,
        validation_alias="LEDGERLENS_VERIFIER_QUORUM",
    )
    verifier_min_confidence: float = Field(
        default=0.85,
        ge=0,
        le=1,
        validation_alias="LEDGERLENS_VERIFIER_MIN_CONFIDENCE",
    )
    action_authorization_secret: SecretStr | None = Field(
        default=None,
        validation_alias="LEDGERLENS_ACTION_AUTHORIZATION_SECRET",
        repr=False,
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

    @field_validator("llm_provider", "planner_provider", "verifier_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if value is None or value == "":
            return value
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_")
        return value

    @model_validator(mode="after")
    def enforce_safe_defaults(self) -> Settings:
        if self.mutations_enabled and not self.incident_commander_enabled:
            raise ValueError("LedgerLens is read-only; mutations cannot be enabled")
        if self.autonomous_execution_enabled and not self.mutations_enabled:
            raise ValueError("autonomous execution requires controlled mutations")
        if self.autonomous_execution_enabled and not self.ai_verification_enabled:
            raise ValueError("autonomous execution requires AI verification")
        if self.autonomous_execution_enabled and self.action_authorization_secret is None:
            raise ValueError("autonomous execution requires an action authorization secret")
        if self.ai_verification_enabled and self.verifier_quorum > len(self.verifier_model_ids):
            raise ValueError("verifier quorum exceeds configured verifier models")
        if self.llm_enabled and not self._has_any_llm_key():
            raise ValueError(
                "LEDGERLENS_LLM_ENABLED requires OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                "or LEDGERLENS_LLM_API_KEY"
            )
        for url in (self.llm_base_url,):
            if self._has_any_llm_key() and not (
                url.startswith("https://")
                or url.startswith("http://localhost")
                or url.startswith("http://127.0.0.1")
            ):
                raise ValueError(
                    "LLM API keys may only be sent over https:// (or a localhost endpoint)"
                )
        return self

    def _has_any_llm_key(self) -> bool:
        return any(
            key is not None
            for key in (self.llm_api_key, self.openai_api_key, self.anthropic_api_key)
        )

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

    def resolved_planner_provider(self) -> LlmProvider:
        return self.planner_provider or self.llm_provider

    def resolved_verifier_provider(self) -> LlmProvider:
        return self.verifier_provider or self.llm_provider

    def base_url_for_provider(self, provider: LlmProvider) -> str:
        """Default native base URL unless a custom openai_compatible URL is set."""

        if provider is LlmProvider.ANTHROPIC:
            if "anthropic" in self.llm_base_url:
                return self.llm_base_url
            return "https://api.anthropic.com"
        if provider is LlmProvider.OPENAI:
            if "openai.com" in self.llm_base_url or self.llm_provider is LlmProvider.OPENAI:
                return self.llm_base_url if self.llm_base_url else "https://api.openai.com/v1"
            if self.llm_provider is LlmProvider.OPENAI_COMPATIBLE:
                return self.llm_base_url
            return "https://api.openai.com/v1"
        return self.llm_base_url

    def api_key_for_provider(self, provider: LlmProvider) -> str:
        """Resolve the secret for a provider without logging it."""

        if provider is LlmProvider.ANTHROPIC:
            if self.anthropic_api_key is not None:
                return self.anthropic_api_key.get_secret_value()
            if self.llm_api_key is not None:
                return self.llm_api_key.get_secret_value()
            raise ValueError("ANTHROPIC_API_KEY or LEDGERLENS_LLM_API_KEY is required")
        # OpenAI + OpenAI-compatible share the OpenAI-style Bearer key.
        if self.openai_api_key is not None:
            return self.openai_api_key.get_secret_value()
        if self.llm_api_key is not None:
            return self.llm_api_key.get_secret_value()
        raise ValueError("OPENAI_API_KEY or LEDGERLENS_LLM_API_KEY is required")

    def require_llm_api_key(self) -> str:
        """Return the key for the default ``llm_provider``."""

        return self.api_key_for_provider(self.llm_provider)

    @property
    def verifier_model_ids(self) -> tuple[str, ...]:
        """Return unique configured verifier IDs without implying family independence."""

        models = tuple(item.strip() for item in self.verifier_models.split(",") if item.strip())
        return tuple(dict.fromkeys(models))

    def require_action_authorization_secret(self) -> str:
        if self.action_authorization_secret is None:
            raise ValueError("LEDGERLENS_ACTION_AUTHORIZATION_SECRET is required")
        return self.action_authorization_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process settings once; tests may call ``cache_clear``."""

    return Settings()
