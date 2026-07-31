"""Dependency-light, read-only adapter for the official DataHub MCP server."""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
from collections.abc import Mapping, Sequence
from contextlib import suppress
from itertools import count
from typing import Any, Protocol

import httpx

JsonObject = dict[str, Any]
_PROTOCOL_VERSION = "2025-06-18"
_READ_ONLY_TOOLS = frozenset({"search", "get_entities", "get_lineage"})


class MCPError(RuntimeError):
    """Base MCP adapter error."""


class MCPReadOnlyError(MCPError):
    """Raised when a non-allowlisted tool is requested."""


class MCPTimeoutError(MCPError):
    """Raised when the MCP server misses a request deadline."""


class MCPTransportError(MCPError):
    """Raised for process, connection, or protocol failures."""


class MCPRemoteError(MCPError):
    """Raised for JSON-RPC errors or MCP tool error responses."""

    def __init__(self, code: int | None, message: str, data: Any = None) -> None:
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.data = data


class MCPTransport(Protocol):
    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and return its result."""

    def close(self) -> None:
        """Release transport resources."""


class HttpMCPTransport:
    """MCP Streamable HTTP transport with JSON and SSE response support."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout: float = 12.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "ledgerlens/0.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.timeout = httpx.Timeout(timeout, connect=min(timeout, 3.0))
        self._owns_client = client is None
        self._client = client or httpx.Client(
            headers=headers,
            timeout=self.timeout,
            transport=transport,
        )
        self.url = url
        self._ids = count(1)
        self._session_id: str | None = None
        self._initialized = False
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _post(self, payload: Mapping[str, Any], *, expect_response: bool = True) -> Any:
        headers = {"Mcp-Session-Id": self._session_id} if self._session_id else {}
        try:
            response = self._client.post(self.url, json=dict(payload), headers=headers)
        except httpx.TimeoutException as exc:
            raise MCPTimeoutError(f"MCP HTTP request timed out: {self.url}") from exc
        except httpx.HTTPError as exc:
            raise MCPTransportError(f"MCP HTTP request failed: {exc}") from exc
        if response.is_error:
            raise MCPTransportError(
                f"MCP HTTP {response.status_code}: {response.text[:500].strip()}"
            )
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        if not expect_response or response.status_code == 202 or not response.content:
            return None
        message = _decode_http_message(response)
        return _unwrap_jsonrpc(message)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "ledgerlens", "version": "0.2.0"},
                },
            }
        )
        if not isinstance(result, Mapping):
            raise MCPTransportError("MCP initialize returned an invalid result")
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            expect_response=False,
        )
        self._initialized = True

    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        with self._lock:
            self._ensure_initialized()
            return self._post(
                {
                    "jsonrpc": "2.0",
                    "id": next(self._ids),
                    "method": method,
                    "params": dict(params or {}),
                }
            )


class StdioMCPTransport:
    """Persistent newline-delimited JSON-RPC transport for MCP stdio servers."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout: float = 12.0,
        env: Mapping[str, str] | None = None,
        allow_mutations: bool = False,
    ) -> None:
        if not command:
            raise ValueError("MCP stdio command cannot be empty")
        child_env = dict(os.environ)
        if env:
            child_env.update(env)
        # Defense in depth: read-only is the default even if the parent process
        # has a permissive environment. Controlled mutation callers must opt in
        # explicitly and still pass the separate typed authorization gate.
        child_env["TOOLS_IS_MUTATION_ENABLED"] = "true" if allow_mutations else "false"
        child_env["DATAHUB_MCP_MUTATIONS_ENABLED"] = "true" if allow_mutations else "false"
        try:
            self._process = subprocess.Popen(
                list(command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=child_env,
                shell=False,
            )
        except OSError as exc:
            raise MCPTransportError(f"Could not start MCP command {command[0]!r}: {exc}") from exc
        self.timeout = timeout
        self._ids = count(1)
        self._initialized = False
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            with suppress(subprocess.TimeoutExpired):
                self._process.wait(timeout=2)

    def __enter__(self) -> StdioMCPTransport:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _write(self, payload: Mapping[str, Any]) -> None:
        if self._process.poll() is not None:
            raise MCPTransportError("MCP stdio process exited")
        if self._process.stdin is None:
            raise MCPTransportError("MCP stdio input is unavailable")
        try:
            self._process.stdin.write(json.dumps(dict(payload), separators=(",", ":")) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise MCPTransportError("MCP stdio write failed") from exc

    def _read(self) -> Any:
        if self._process.stdout is None:
            raise MCPTransportError("MCP stdio output is unavailable")
        ready, _, _ = select.select([self._process.stdout], [], [], self.timeout)
        if not ready:
            raise MCPTimeoutError("MCP stdio request timed out")
        line = self._process.stdout.readline()
        if not line:
            raise MCPTransportError("MCP stdio process closed its output")
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPTransportError("MCP stdio returned invalid JSON") from exc
        return _unwrap_jsonrpc(message)

    def _send_request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        self._write(
            {
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": method,
                "params": dict(params or {}),
            }
        )
        return self._read()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        result = self._send_request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ledgerlens", "version": "0.2.0"},
            },
        )
        if not isinstance(result, Mapping):
            raise MCPTransportError("MCP initialize returned an invalid result")
        self._write({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        self._initialized = True

    def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        with self._lock:
            self._ensure_initialized()
            return self._send_request(method, params)


class DataHubMCPClient:
    """Normalized read-only facade over the official DataHub MCP tools."""

    def __init__(self, transport: MCPTransport) -> None:
        self._transport = transport

    @classmethod
    def from_http(
        cls,
        url: str,
        *,
        token: str | None = None,
        timeout: float = 12.0,
        transport: httpx.BaseTransport | None = None,
    ) -> DataHubMCPClient:
        return cls(HttpMCPTransport(url, token=token, timeout=timeout, transport=transport))

    @classmethod
    def from_stdio(
        cls,
        command: Sequence[str],
        *,
        timeout: float = 12.0,
        env: Mapping[str, str] | None = None,
    ) -> DataHubMCPClient:
        return cls(StdioMCPTransport(command, timeout=timeout, env=env))

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> DataHubMCPClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        if name not in _READ_ONLY_TOOLS:
            raise MCPReadOnlyError(f"MCP tool is not in the read-only allowlist: {name}")
        result = self._transport.request(
            "tools/call",
            {"name": name, "arguments": dict(arguments)},
        )
        return _extract_tool_payload(result)

    def search(
        self,
        query: str,
        *,
        count: int = 20,
        entity_types: Sequence[str] = ("DATASET",),
    ) -> list[JsonObject]:
        payload = self.call_tool(
            "search",
            {
                "query": query,
                "num_results": count,
            },
        )
        records = _records(payload, ("searchResults", "results", "entities", "items"))
        normalized = [_normalize_entity_record(record) for record in records]
        allowed_types = {value.upper() for value in entity_types}
        if not allowed_types:
            return normalized
        return [
            record
            for record in normalized
            if not isinstance(record.get("type"), str)
            or str(record["type"]).upper() in allowed_types
        ]

    def get_entities(self, urns: Sequence[str]) -> list[JsonObject]:
        payload = self.call_tool("get_entities", {"urns": list(urns)})
        records = _records(payload, ("result", "entities", "results", "items"))
        return [_normalize_entity_record(record) for record in records]

    def get_lineage(
        self,
        urn: str,
        *,
        direction: str = "downstream",
        max_hops: int = 3,
        count: int = 50,
    ) -> list[JsonObject]:
        normalized_direction = direction.lower()
        if normalized_direction not in {"upstream", "downstream"}:
            raise ValueError("direction must be upstream or downstream")
        payload = self.call_tool(
            "get_lineage",
            {
                "urn": urn,
                "upstream": normalized_direction == "upstream",
                "max_hops": max_hops,
                "max_results": count,
            },
        )
        section_key = "upstreams" if normalized_direction == "upstream" else "downstreams"
        section = payload.get(section_key) if isinstance(payload, Mapping) else None
        record_keys = (
            "lineage",
            "relationships",
            "searchResults",
            "results",
            "entities",
            "items",
        )
        lineage_payload = section if isinstance(section, Mapping) else payload
        if isinstance(lineage_payload, Mapping) and not any(
            isinstance(lineage_payload.get(key), list) for key in record_keys
        ):
            records: list[Mapping[str, Any]] = []
        else:
            records = _records(lineage_payload, record_keys)
        normalized: list[JsonObject] = []
        for record in records:
            item = _normalize_entity_record(record)
            item["direction"] = str(record.get("direction", normalized_direction)).lower()
            if "degree" in record:
                item["degree"] = record["degree"]
            if "relationship" in record:
                item["relationship"] = record["relationship"]
            normalized.append(item)
        return normalized


MCPClient = DataHubMCPClient


def _decode_http_message(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        messages: list[Any] = []
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise MCPTransportError("MCP SSE event contained invalid JSON") from exc
        if not messages:
            raise MCPTransportError("MCP SSE response contained no data event")
        return messages[-1]
    try:
        return response.json()
    except ValueError as exc:
        raise MCPTransportError("MCP HTTP response was not JSON") from exc


def _unwrap_jsonrpc(message: Any) -> Any:
    if not isinstance(message, Mapping):
        raise MCPTransportError("MCP JSON-RPC response must be an object")
    error = message.get("error")
    if isinstance(error, Mapping):
        code = error.get("code")
        raise MCPRemoteError(
            code if isinstance(code, int) else None,
            str(error.get("message", "unknown remote error")),
            error.get("data"),
        )
    if "result" not in message:
        raise MCPTransportError("MCP JSON-RPC response is missing result")
    return message["result"]


def _extract_tool_payload(result: Any) -> Any:
    if not isinstance(result, Mapping):
        return result
    if result.get("isError") is True:
        raise MCPRemoteError(None, _content_text(result.get("content")) or "tool failed")
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    content = result.get("content")
    if isinstance(content, list):
        texts = [
            item.get("text")
            for item in content
            if isinstance(item, Mapping) and item.get("type") == "text"
        ]
        text = "\n".join(item for item in texts if isinstance(item, str)).strip()
        if not text:
            return []
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
    return result


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    return " ".join(
        str(item.get("text")) for item in content if isinstance(item, Mapping) and item.get("text")
    )


def _records(payload: Any, keys: Sequence[str]) -> list[Mapping[str, Any]]:
    current = payload
    if isinstance(current, Mapping):
        for key in keys:
            candidate = current.get(key)
            if isinstance(candidate, list):
                current = candidate
                break
        else:
            if isinstance(current.get("data"), (Mapping, list)):
                return _records(current["data"], keys)
            current = [current]
    if not isinstance(current, list):
        return []
    return [item for item in current if isinstance(item, Mapping)]


def _normalize_entity_record(record: Mapping[str, Any]) -> JsonObject:
    entity = record.get("entity")
    source = entity if isinstance(entity, Mapping) else record
    result = dict(source)
    urn = source.get("urn") or record.get("urn")
    if isinstance(urn, str):
        result["urn"] = urn
    entity_type = source.get("type") or source.get("entityType") or record.get("type")
    if isinstance(entity_type, str):
        result["type"] = entity_type
    elif isinstance(urn, str):
        inferred_type = _entity_type_from_urn(urn)
        if inferred_type:
            result["type"] = inferred_type
    if "matchedFields" in record:
        result["matchedFields"] = record["matchedFields"]
    result["raw"] = dict(record)
    return result


def _entity_type_from_urn(urn: str) -> str | None:
    prefix = "urn:li:"
    if not urn.startswith(prefix):
        return None
    entity_name = urn[len(prefix) :].split(":", 1)[0].lower()
    return {
        "container": "CONTAINER",
        "corpgroup": "CORP_GROUP",
        "corpuser": "CORP_USER",
        "dataset": "DATASET",
        "tag": "TAG",
    }.get(entity_name)
