"""Secret-safe OpenAI and Anthropic JSON model runtimes for planner/verifier roles."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import httpx

from ledgerlens.config import LlmProvider

JsonObject = dict[str, Any]
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class ModelRuntimeError(RuntimeError):
    """Raised when a model transport or response violates the JSON contract."""


class JsonModelClient(Protocol):
    """Shared contract for planner/verifier JSON clients."""

    model: str
    base_url: str

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> JsonObject:
        """Return exactly one parsed JSON object."""

    def close(self) -> None:
        """Release HTTP resources."""


class OpenAICompatibleJsonClient:
    """OpenAI Chat Completions (native api.openai.com or any /v1 compatible host).

    Credentials never appear in request bodies, exceptions, or repr output.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        normalized = base_url.strip().rstrip("/")
        if not (
            normalized.startswith("https://")
            or normalized.startswith("http://localhost")
            or normalized.startswith("http://127.0.0.1")
        ):
            raise ValueError("model base_url must use https:// (or localhost http)")
        if not api_key:
            raise ValueError("model api_key is required")
        if not model.strip():
            raise ValueError("model is required")
        self.base_url = normalized
        self.model = model.strip()
        self.provider = "openai"
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized,
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ledgerlens-incident-commander/0.2",
            },
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(base_url={self.base_url!r}, model={self.model!r})"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> JsonObject:
        """Return a JSON object or fail closed without retrying with looser parsing."""

        if not 0 <= temperature <= 1:
            raise ValueError("temperature must be between 0 and 1")
        user_content = _user_content(prompt, context)
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            raw = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # Some OpenAI-compatible hosts reject response_format; retry once without it.
            if _is_response_format_error(exc):
                return self._complete_json_without_format(
                    system=system,
                    user_content=user_content,
                    temperature=temperature,
                )
            raise ModelRuntimeError(
                f"model request failed for provider={self.base_url} model={self.model}"
            ) from exc
        if not isinstance(raw, str) or not raw.strip():
            raise ModelRuntimeError("model returned empty content")
        return parse_json_object(raw)

    def _complete_json_without_format(
        self,
        *,
        system: str,
        user_content: str,
        temperature: float,
    ) -> JsonObject:
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            raw = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelRuntimeError(
                f"model request failed for provider={self.base_url} model={self.model}"
            ) from exc
        if not isinstance(raw, str) or not raw.strip():
            raise ModelRuntimeError("model returned empty content")
        return parse_json_object(raw)


class AnthropicJsonClient:
    """Native Anthropic Messages API client returning one JSON object."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.anthropic.com",
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        max_tokens: int = 4096,
    ) -> None:
        normalized = base_url.strip().rstrip("/")
        if not normalized.startswith("https://"):
            raise ValueError("Anthropic base_url must use https://")
        if not api_key:
            raise ValueError("model api_key is required")
        if not model.strip():
            raise ValueError("model is required")
        self.base_url = normalized
        self.model = model.strip()
        self.provider = "anthropic"
        self.max_tokens = max_tokens
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized,
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": "ledgerlens-incident-commander/0.2",
            },
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(base_url={self.base_url!r}, model={self.model!r})"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> JsonObject:
        if not 0 <= temperature <= 1:
            raise ValueError("temperature must be between 0 and 1")
        user_content = _user_content(prompt, context)
        # Ask for JSON explicitly; Anthropic has no OpenAI response_format field.
        system_json = (
            system.rstrip()
            + "\n\nRespond with a single JSON object only. No markdown fences or prose."
        )
        try:
            response = self._client.post(
                "/v1/messages",
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": temperature,
                    "system": system_json,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            blocks = payload.get("content") or []
            raw_parts = [
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            raw = "\n".join(part for part in raw_parts if part)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelRuntimeError(
                f"model request failed for provider={self.base_url} model={self.model}"
            ) from exc
        if not isinstance(raw, str) or not raw.strip():
            raise ModelRuntimeError("model returned empty content")
        return parse_json_object(raw)


def create_json_client(
    *,
    provider: LlmProvider,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> OpenAICompatibleJsonClient | AnthropicJsonClient:
    """Construct a native OpenAI or Anthropic JSON client."""

    if provider is LlmProvider.ANTHROPIC:
        return AnthropicJsonClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
    return OpenAICompatibleJsonClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )


def _user_content(prompt: str, context: Mapping[str, Any] | None) -> str:
    user_content = prompt
    if context is not None:
        user_content += "\n\nImmutable context JSON:\n" + json.dumps(
            context,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return user_content


def _is_response_format_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "response_format" in text or "json_object" in text


def parse_json_object(raw: str) -> JsonObject:
    """Parse exactly one JSON object, allowing only a surrounding JSON code fence."""

    text = raw.strip()
    fenced = _JSON_FENCE.fullmatch(text)
    if fenced is not None:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelRuntimeError("model response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise ModelRuntimeError("model response must be one JSON object")
    return {str(key): item for key, item in value.items()}


def close_clients(clients: Sequence[Any]) -> None:
    """Close a set of clients even when one close implementation raises."""

    first_error: Exception | None = None
    for client in clients:
        try:
            client.close()
        except Exception as exc:  # pragma: no cover - defensive provider cleanup
            first_error = first_error or exc
    if first_error is not None:
        raise first_error


class RecordingJsonClient:
    """Wrap a JSON model client and record system/user prompts + JSON responses.

    Used for demo traces and debugging agent I/O. Does not log API keys. Callers
    should still sanitize context before publishing (redact tokens, PII).
    """

    def __init__(
        self,
        inner: JsonModelClient,
        *,
        role: str,
        records: list[JsonObject] | None = None,
    ) -> None:
        self.inner = inner
        self.role = role
        self.records: list[JsonObject] = records if records is not None else []
        self.model = inner.model
        self.base_url = inner.base_url
        self.provider = getattr(inner, "provider", "unknown")

    def __repr__(self) -> str:
        return f"RecordingJsonClient(role={self.role!r}, model={self.model!r})"

    def close(self) -> None:
        self.inner.close()

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> JsonObject:
        user_content = _user_content(prompt, context)
        entry: JsonObject = {
            "role": self.role,
            "model": self.model,
            "provider": self.base_url,
            "providerFamily": self.provider,
            "temperature": temperature,
            "input": {
                "system": system,
                "userPrompt": prompt,
                "context": dict(context) if context is not None else None,
                "userMessageFull": user_content,
            },
            "output": None,
            "error": None,
        }
        try:
            result = self.inner.complete_json(
                system=system,
                prompt=prompt,
                context=context,
                temperature=temperature,
            )
            entry["output"] = {
                "kind": "json_object",
                "json": result,
            }
            return result
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.records.append(entry)
