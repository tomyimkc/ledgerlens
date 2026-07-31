"""Secret-safe OpenAI-compatible JSON model runtime for planner and verifier roles."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

JsonObject = dict[str, Any]
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class ModelRuntimeError(RuntimeError):
    """Raised when a model transport or response violates the JSON contract."""


class OpenAICompatibleJsonClient:
    """Small injected client that returns one strict JSON object.

    The client never includes credentials in request bodies, exceptions, or repr output.
    It is suitable for independent planner/verifier instances configured with different
    model IDs or providers.
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
        if not normalized.startswith("https://"):
            raise ValueError("model base_url must use https://")
        if not api_key:
            raise ValueError("model api_key is required")
        if not model.strip():
            raise ValueError("model is required")
        self.base_url = normalized
        self.model = model.strip()
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
        user_content = prompt
        if context is not None:
            user_content += "\n\nImmutable context JSON:\n" + json.dumps(
                context,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
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


def close_clients(clients: Sequence[OpenAICompatibleJsonClient]) -> None:
    """Close a set of clients even when one close implementation raises."""

    first_error: Exception | None = None
    for client in clients:
        try:
            client.close()
        except Exception as exc:  # pragma: no cover - defensive provider cleanup
            first_error = first_error or exc
    if first_error is not None:
        raise first_error
