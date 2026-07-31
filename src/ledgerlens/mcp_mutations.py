"""Policy-gated adapter for the official DataHub MCP mutation tools.

This module is intentionally separate from :mod:`ledgerlens.mcp_client`.  The
existing client stays read-only; callers must opt in to this adapter, inject an
MCP transport, and supply a typed authorization minted by a deterministic
policy gate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Protocol

from ledgerlens.mcp_client import MCPTransport, StdioMCPTransport, _extract_tool_payload

JsonObject = dict[str, Any]


class MutationTool(StrEnum):
    """Official DataHub MCP mutation tools used by LedgerLens."""

    SAVE_DOCUMENT = "save_document"
    ADD_TAGS = "add_tags"
    REMOVE_TAGS = "remove_tags"
    UPDATE_DESCRIPTION = "update_description"
    ADD_STRUCTURED_PROPERTIES = "add_structured_properties"
    REMOVE_STRUCTURED_PROPERTIES = "remove_structured_properties"


OFFICIAL_MUTATION_TOOLS = frozenset(MutationTool)

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "password",
        "secret",
        "token",
    }
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|cookie|credential|password|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


class MCPMutationError(RuntimeError):
    """Base error for the isolated MCP mutation adapter."""


class MCPMutationDisabledError(MCPMutationError):
    """Raised when the explicit mutation adapter has not been enabled."""


class MCPMutationNotAllowedError(MCPMutationError):
    """Raised when a tool is outside the configured mutation allowlist."""


class MCPMutationUnsupportedError(MCPMutationError):
    """Raised when the connected MCP deployment does not support a tool."""


class MCPMutationAuthorizationError(MCPMutationError):
    """Raised when a typed policy authorization is absent or invalid."""


class MCPMutationResponseError(MCPMutationError):
    """Raised when a mutation tool reports an unsuccessful result."""


@dataclass(frozen=True)
class MutationCall:
    """A canonical, idempotency-keyed call to one official mutation tool."""

    tool: MutationTool
    arguments: Mapping[str, Any]
    idempotency_key: str

    def __post_init__(self) -> None:
        tool = self.tool if isinstance(self.tool, MutationTool) else MutationTool(self.tool)
        key = self.idempotency_key.strip()
        if not key:
            raise ValueError("idempotency_key cannot be blank")
        if len(key) > 200 or any(character.isspace() for character in key):
            raise ValueError("idempotency_key must be at most 200 characters with no whitespace")
        arguments = dict(self.arguments)
        _reject_sensitive_keys(arguments)
        try:
            json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("mutation arguments must be finite JSON-compatible values") from exc
        _validate_official_arguments(tool, arguments)
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "arguments", MappingProxyType(arguments))
        object.__setattr__(self, "idempotency_key", key)

    @property
    def digest(self) -> str:
        """Stable digest binding authorization and idempotency to this exact call."""

        return _digest(
            {
                "tool": self.tool.value,
                "arguments": dict(self.arguments),
                "idempotencyKey": self.idempotency_key,
            }
        )

    @property
    def target_urns(self) -> tuple[str, ...]:
        """Entity or document URNs directly changed by this call."""

        if self.tool is MutationTool.SAVE_DOCUMENT:
            urn = self.arguments.get("urn")
            return (urn,) if isinstance(urn, str) and urn else ()
        if self.tool is MutationTool.UPDATE_DESCRIPTION:
            urn = self.arguments.get("entity_urn")
            return (urn,) if isinstance(urn, str) and urn else ()
        urns = self.arguments.get("entity_urns")
        if not isinstance(urns, list):
            return ()
        return tuple(urn for urn in urns if isinstance(urn, str) and urn)


@dataclass(frozen=True)
class MutationAuthorization:
    """Opaque, request-bound authorization minted by a policy gate.

    ``_issuer`` is deliberately process-local and excluded from repr/comparison.
    It is not a bearer token and is never copied into a receipt.
    """

    authorization_id: str
    policy_version: str
    actor: str
    reason: str
    tool: MutationTool
    idempotency_key: str
    call_digest: str
    preview_only: bool
    incident_context: Mapping[str, Any] | None = None
    _issuer: object | None = field(default=None, repr=False, compare=False)

    def public_summary(self) -> JsonObject:
        """Return receipt-safe authorization metadata without the issuer proof."""

        return {
            "authorizationId": self.authorization_id,
            "policyVersion": self.policy_version,
            "actor": self.actor,
            "reason": self.reason,
            "tool": self.tool.value,
            "idempotencyKey": self.idempotency_key,
            "callDigest": self.call_digest,
            "previewOnly": self.preview_only,
            "incidentContext": redact_sensitive(self.incident_context),
        }


class MutationAuthorizationVerifier(Protocol):
    """Policy-gate verification required by :class:`MCPMutationClient`."""

    def verify(
        self,
        authorization: MutationAuthorization,
        call: MutationCall,
        *,
        preview: bool = False,
    ) -> None:
        """Raise when ``authorization`` does not permit ``call``."""


class MCPMutationClient:
    """Explicit opt-in facade over the official DataHub MCP mutation surface."""

    def __init__(
        self,
        transport: MCPTransport,
        *,
        enabled: bool = False,
        allowlisted_tools: Iterable[MutationTool | str] = OFFICIAL_MUTATION_TOOLS,
        supported_tools: Iterable[MutationTool | str] | None = None,
        authorization_verifier: MutationAuthorizationVerifier | None = None,
    ) -> None:
        self._transport = transport
        self.enabled = enabled
        self.allowlisted_tools = _tool_set(allowlisted_tools)
        self.supported_tools = (
            _tool_set(supported_tools) if supported_tools is not None else OFFICIAL_MUTATION_TOOLS
        )
        self._authorization_verifier = authorization_verifier

    @classmethod
    def from_stdio(
        cls,
        command: Sequence[str],
        *,
        enabled: bool = False,
        timeout: float = 12.0,
        env: Mapping[str, str] | None = None,
        allowlisted_tools: Iterable[MutationTool | str] = OFFICIAL_MUTATION_TOOLS,
        supported_tools: Iterable[MutationTool | str] | None = None,
        authorization_verifier: MutationAuthorizationVerifier | None = None,
    ) -> MCPMutationClient:
        """Create an explicit opt-in mutation client over the official stdio server."""

        return cls(
            StdioMCPTransport(
                command,
                timeout=timeout,
                env=env,
                allow_mutations=enabled,
            ),
            enabled=enabled,
            allowlisted_tools=allowlisted_tools,
            supported_tools=supported_tools,
            authorization_verifier=authorization_verifier,
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> MCPMutationClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def call_tool(
        self,
        call: MutationCall | MutationTool | str,
        arguments: Mapping[str, Any] | None = None,
        *,
        authorization: MutationAuthorization | None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Call one allowlisted mutation after typed authorization verification."""

        normalized_call = _coerce_call(call, arguments, idempotency_key)
        if not self.enabled:
            raise MCPMutationDisabledError("DataHub MCP mutations are disabled")
        if normalized_call.tool not in self.allowlisted_tools:
            raise MCPMutationNotAllowedError(
                f"MCP mutation tool is not allowlisted: {normalized_call.tool.value}"
            )
        if normalized_call.tool not in self.supported_tools:
            raise MCPMutationUnsupportedError(
                f"MCP mutation tool is not supported by this deployment: "
                f"{normalized_call.tool.value}"
            )
        if authorization is None or self._authorization_verifier is None:
            raise MCPMutationAuthorizationError(
                "A typed authorization from the deterministic policy gate is required"
            )
        self._authorization_verifier.verify(authorization, normalized_call)
        try:
            result = self._transport.request(
                "tools/call",
                {
                    "name": normalized_call.tool.value,
                    "arguments": dict(normalized_call.arguments),
                },
            )
            payload = _extract_tool_payload(result)
        except Exception as exc:
            raise MCPMutationResponseError(redact_text(str(exc))) from None
        if isinstance(payload, Mapping) and payload.get("success") is False:
            message = str(payload.get("message", "mutation tool reported failure"))
            raise MCPMutationResponseError(redact_text(message))
        return redact_sensitive(payload)

    def save_document(
        self,
        *,
        document_type: str,
        title: str,
        content: str,
        idempotency_key: str,
        authorization: MutationAuthorization,
        urn: str | None = None,
        topics: Sequence[str] | None = None,
        related_documents: Sequence[str] | None = None,
        related_assets: Sequence[str] | None = None,
    ) -> Any:
        arguments: JsonObject = {
            "document_type": document_type,
            "title": title,
            "content": content,
        }
        if urn is not None:
            arguments["urn"] = urn
        if topics is not None:
            arguments["topics"] = list(topics)
        if related_documents is not None:
            arguments["related_documents"] = list(related_documents)
        if related_assets is not None:
            arguments["related_assets"] = list(related_assets)
        return self.call_tool(
            MutationTool.SAVE_DOCUMENT,
            arguments,
            authorization=authorization,
            idempotency_key=idempotency_key,
        )

    def add_tags(
        self,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        authorization: MutationAuthorization,
        column_paths: Sequence[str | None] | None = None,
    ) -> Any:
        return self._tag_call(
            MutationTool.ADD_TAGS,
            tag_urns=tag_urns,
            entity_urns=entity_urns,
            column_paths=column_paths,
            idempotency_key=idempotency_key,
            authorization=authorization,
        )

    def remove_tags(
        self,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        authorization: MutationAuthorization,
        column_paths: Sequence[str | None] | None = None,
    ) -> Any:
        return self._tag_call(
            MutationTool.REMOVE_TAGS,
            tag_urns=tag_urns,
            entity_urns=entity_urns,
            column_paths=column_paths,
            idempotency_key=idempotency_key,
            authorization=authorization,
        )

    def _tag_call(
        self,
        tool: MutationTool,
        *,
        tag_urns: Sequence[str],
        entity_urns: Sequence[str],
        column_paths: Sequence[str | None] | None,
        idempotency_key: str,
        authorization: MutationAuthorization,
    ) -> Any:
        arguments: JsonObject = {
            "tag_urns": list(tag_urns),
            "entity_urns": list(entity_urns),
        }
        if column_paths is not None:
            arguments["column_paths"] = list(column_paths)
        return self.call_tool(
            tool,
            arguments,
            authorization=authorization,
            idempotency_key=idempotency_key,
        )

    def update_description(
        self,
        *,
        entity_urn: str,
        operation: str,
        idempotency_key: str,
        authorization: MutationAuthorization,
        description: str | None = None,
        column_path: str | None = None,
    ) -> Any:
        arguments: JsonObject = {"entity_urn": entity_urn, "operation": operation}
        if description is not None:
            arguments["description"] = description
        if column_path is not None:
            arguments["column_path"] = column_path
        return self.call_tool(
            MutationTool.UPDATE_DESCRIPTION,
            arguments,
            authorization=authorization,
            idempotency_key=idempotency_key,
        )

    def set_structured_properties(
        self,
        *,
        property_values: Mapping[str, Sequence[str | float | int]],
        entity_urns: Sequence[str],
        idempotency_key: str,
        authorization: MutationAuthorization,
    ) -> Any:
        return self.call_tool(
            MutationTool.ADD_STRUCTURED_PROPERTIES,
            {
                "property_values": {urn: list(values) for urn, values in property_values.items()},
                "entity_urns": list(entity_urns),
            },
            authorization=authorization,
            idempotency_key=idempotency_key,
        )

    add_structured_properties = set_structured_properties

    def remove_structured_properties(
        self,
        *,
        property_urns: Sequence[str],
        entity_urns: Sequence[str],
        idempotency_key: str,
        authorization: MutationAuthorization,
    ) -> Any:
        return self.call_tool(
            MutationTool.REMOVE_STRUCTURED_PROPERTIES,
            {
                "property_urns": list(property_urns),
                "entity_urns": list(entity_urns),
            },
            authorization=authorization,
            idempotency_key=idempotency_key,
        )


def redact_text(value: str) -> str:
    """Redact common bearer and assignment-style credential forms."""

    redacted = _BEARER_RE.sub("Bearer [REDACTED]", value)
    return _ASSIGNMENT_SECRET_RE.sub(r"\1\2[REDACTED]", redacted)


def redact_sensitive(value: Any) -> Any:
    """Recursively sanitize data before returning it or storing it in receipts."""

    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]" if _is_sensitive_key(str(key)) else redact_sensitive(nested_value)
            )
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def _coerce_call(
    call: MutationCall | MutationTool | str,
    arguments: Mapping[str, Any] | None,
    idempotency_key: str | None,
) -> MutationCall:
    if isinstance(call, MutationCall):
        if arguments is not None or idempotency_key is not None:
            raise ValueError("arguments and idempotency_key must be omitted for a MutationCall")
        return call
    if arguments is None or idempotency_key is None:
        raise ValueError("arguments and idempotency_key are required")
    try:
        tool = call if isinstance(call, MutationTool) else MutationTool(call)
    except ValueError as exc:
        raise MCPMutationNotAllowedError(f"Unknown MCP mutation tool: {call}") from exc
    return MutationCall(tool=tool, arguments=arguments, idempotency_key=idempotency_key)


def _tool_set(values: Iterable[MutationTool | str]) -> frozenset[MutationTool]:
    tools: set[MutationTool] = set()
    for value in values:
        try:
            tools.add(value if isinstance(value, MutationTool) else MutationTool(value))
        except ValueError as exc:
            raise ValueError(f"Unknown official mutation tool: {value}") from exc
    return frozenset(tools)


def _validate_official_arguments(tool: MutationTool, arguments: Mapping[str, Any]) -> None:
    required: Mapping[MutationTool, frozenset[str]] = {
        MutationTool.SAVE_DOCUMENT: frozenset({"document_type", "title", "content"}),
        MutationTool.ADD_TAGS: frozenset({"tag_urns", "entity_urns"}),
        MutationTool.REMOVE_TAGS: frozenset({"tag_urns", "entity_urns"}),
        MutationTool.UPDATE_DESCRIPTION: frozenset({"entity_urn", "operation"}),
        MutationTool.ADD_STRUCTURED_PROPERTIES: frozenset({"property_values", "entity_urns"}),
        MutationTool.REMOVE_STRUCTURED_PROPERTIES: frozenset({"property_urns", "entity_urns"}),
    }
    allowed: Mapping[MutationTool, frozenset[str]] = {
        MutationTool.SAVE_DOCUMENT: required[tool]
        | frozenset({"urn", "topics", "related_documents", "related_assets"}),
        MutationTool.ADD_TAGS: required[tool] | frozenset({"column_paths"}),
        MutationTool.REMOVE_TAGS: required[tool] | frozenset({"column_paths"}),
        MutationTool.UPDATE_DESCRIPTION: required[tool] | frozenset({"description", "column_path"}),
        MutationTool.ADD_STRUCTURED_PROPERTIES: required[tool],
        MutationTool.REMOVE_STRUCTURED_PROPERTIES: required[tool],
    }
    missing = required[tool] - arguments.keys()
    if missing:
        raise ValueError(
            f"{tool.value} is missing required arguments: {', '.join(sorted(missing))}"
        )
    unexpected = arguments.keys() - allowed[tool]
    if unexpected:
        raise ValueError(
            f"{tool.value} received unsupported arguments: {', '.join(sorted(unexpected))}"
        )
    if tool is MutationTool.UPDATE_DESCRIPTION:
        operation = arguments.get("operation")
        if operation not in {"replace", "append", "remove"}:
            raise ValueError("update_description operation must be replace, append, or remove")
        if operation in {"replace", "append"} and not arguments.get("description"):
            raise ValueError(f"description is required for {operation}")
    if tool is MutationTool.SAVE_DOCUMENT and arguments.get("document_type") not in {
        "Insight",
        "Decision",
        "FAQ",
        "Analysis",
        "Summary",
        "Recommendation",
        "Note",
        "Context",
    }:
        raise ValueError("save_document document_type is not supported")
    for key in ("tag_urns", "entity_urns", "property_urns"):
        if key in arguments and not _nonempty_string_list(arguments[key]):
            raise ValueError(f"{key} must be a non-empty list of strings")
    if tool is MutationTool.ADD_STRUCTURED_PROPERTIES:
        property_values = arguments.get("property_values")
        if not isinstance(property_values, Mapping) or not property_values:
            raise ValueError("property_values must be a non-empty mapping")
        for urn, values in property_values.items():
            if not isinstance(urn, str) or not urn or not isinstance(values, list) or not values:
                raise ValueError("structured properties require non-empty URN value lists")


def _nonempty_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _reject_sensitive_keys(value: Any, path: str = "arguments") -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                raise ValueError(f"sensitive credential field is not allowed in {path}: {key_text}")
            _reject_sensitive_keys(nested_value, f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_sensitive_keys(item, f"{path}[{index}]")
    elif isinstance(value, str) and redact_text(value) != value:
        raise ValueError(f"raw credential-like value is not allowed in {path}")


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


MutationClient = MCPMutationClient
