"""Environment-backed configuration with conservative, read-only defaults."""

from __future__ import annotations

import shlex
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Bring your own LLM: the planner/verifier key is ``LEDGERLENS_LLM_API_KEY`` (the legacy
    ``SOPHIA_020S_KEY`` name is still accepted), and the endpoint is any OpenAI-compatible
    ``LEDGERLENS_LLM_BASE_URL`` + ``LEDGERLENS_LLM_MODEL``. ``SecretStr`` prevents accidental
    disclosure through repr/serialization; callers must explicitly request the secret value,
    and the key is only ever sent to the configured (https) base URL.
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
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LEDGERLENS_LLM_API_KEY", "SOPHIA_020S_KEY"),
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
        default="gpt-5.6-sol",
        min_length=1,
        validation_alias="LEDGERLENS_PLANNER_MODEL",
    )
    verifier_models: str = Field(
        default="gpt-5.6-terra,gpt-5.5",
        min_length=1,
        validation_alias="LEDGERLENS_VERIFIER_MODELS",
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
        if self.llm_enabled and self.llm_api_key is None:
            raise ValueError("LEDGERLENS_LLM_ENABLED requires LEDGERLENS_LLM_API_KEY")
        if self.llm_api_key is not None and not (
            self.llm_base_url.startswith("https://")
            or self.llm_base_url.startswith("http://localhost")
            or self.llm_base_url.startswith("http://127.0.0.1")
        ):
            raise ValueError(
                "the LLM API key may only be sent over https:// (or a localhost endpoint)"
            )
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

    def require_llm_api_key(self) -> str:
        if self.llm_api_key is None:
            raise ValueError("LEDGERLENS_LLM_API_KEY is required to enable the LLM")
        return self.llm_api_key.get_secret_value()

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
