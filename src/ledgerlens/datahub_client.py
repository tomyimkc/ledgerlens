"""Small read-only DataHub GraphQL/OpenAPI client."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

JsonObject = dict[str, Any]


class DataHubError(RuntimeError):
    """Base class for useful, typed DataHub client failures."""


class DataHubReadOnlyError(DataHubError):
    """Raised when a caller attempts to execute a mutation."""


class DataHubTimeoutError(DataHubError):
    """Raised when DataHub exceeds the configured deadline."""


class DataHubTransportError(DataHubError):
    """Raised for connection/protocol failures below HTTP."""


class DataHubHTTPError(DataHubError):
    """Raised for non-success HTTP responses."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"DataHub HTTP {status_code}: {message}")
        self.status_code = status_code


class DataHubGraphQLError(DataHubError):
    """Raised when GraphQL returns an ``errors`` collection."""

    def __init__(self, errors: Sequence[Mapping[str, Any]]) -> None:
        self.errors = tuple(dict(error) for error in errors)
        messages = "; ".join(str(error.get("message", "unknown error")) for error in errors)
        super().__init__(f"DataHub GraphQL error: {messages}")


class DataHubResponseError(DataHubError):
    """Raised when a successful response has an invalid shape."""


@dataclass(frozen=True)
class SearchHit:
    urn: str
    entity_type: str | None = None
    name: str | None = None
    description: str | None = None
    matched_fields: tuple[Mapping[str, Any], ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchPage:
    start: int
    count: int
    total: int
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True)
class LineageHit:
    urn: str
    entity_type: str | None = None
    degree: int | None = None
    direction: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LineagePage:
    start: int
    count: int
    total: int
    hits: tuple[LineageHit, ...]


@dataclass(frozen=True)
class AuditStamp:
    aspect: str
    kind: str
    time_ms: int | None
    actor: str | None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditMetadata:
    urn: str
    entity_type: str
    audit_stamps: tuple[AuditStamp, ...]
    system_metadata: Mapping[str, Mapping[str, Any]]
    aspect_values: Mapping[str, Any]
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def latest_ingestion_time_ms(self) -> int | None:
        """Newest DataHub metadata observation time, never a validation timestamp."""

        values: list[int] = []
        for stamp in self.audit_stamps:
            if stamp.time_ms is not None:
                values.append(stamp.time_ms)
        for metadata in self.system_metadata.values():
            observed = _as_int(metadata.get("lastObserved"))
            if observed is not None:
                values.append(observed)
        return max(values) if values else None


_SEARCH_QUERY = """
query LedgerLensSearch($input: SearchAcrossEntitiesInput!) {
  searchAcrossEntities(input: $input) {
    start
    count
    total
    searchResults {
      matchedFields { name value }
      entity {
        urn
        type
        ... on Dataset {
          name
          properties { name description }
        }
      }
    }
  }
}
"""

_ENTITY_QUERY = """
query LedgerLensEntity($urn: String!) {
  entity(urn: $urn) {
    urn
    type
    ... on Dataset {
      name
      properties {
        name
        description
        customProperties { key value }
      }
      ownership {
        owners {
          owner {
            ... on CorpUser { urn type }
            ... on CorpGroup { urn type }
          }
          type
        }
      }
      globalTags {
        tags { tag { urn name } }
      }
      status { removed }
    }
  }
}
"""

_LINEAGE_QUERY = """
query LedgerLensLineage($input: SearchAcrossLineageInput!) {
  searchAcrossLineage(input: $input) {
    start
    count
    total
    searchResults {
      degree
      entity { urn type }
    }
  }
}
"""


class DataHubClient:
    """Read-only client for DataHub GMS.

    GraphQL is used for search/entity/lineage. OpenAPI v3 aspect envelopes are
    used for ``auditStamp`` and ``systemMetadata`` because those are ingestion
    provenance fields rather than scientific-validation assertions.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        *,
        token: str | None = None,
        timeout: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=min(timeout, 3.0))
        headers = {"Accept": "application/json", "User-Agent": "ledgerlens/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            transport=transport,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> DataHubClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise DataHubTimeoutError(f"DataHub request timed out: {path}") from exc
        except httpx.HTTPError as exc:
            raise DataHubTransportError(f"DataHub request failed: {exc}") from exc
        if response.is_error:
            detail = response.text.strip()
            if len(detail) > 500:
                detail = detail[:497] + "..."
            raise DataHubHTTPError(response.status_code, detail or response.reason_phrase)
        return response

    def graphql(self, query: str, variables: Mapping[str, Any] | None = None) -> JsonObject:
        """Execute a GraphQL query while refusing mutation operations."""

        without_comments = re.sub(r"(?m)#.*$", "", query)
        if re.search(r"\bmutation\b", without_comments, flags=re.IGNORECASE):
            raise DataHubReadOnlyError("GraphQL mutations are disabled")
        response = self._request(
            "POST",
            "/api/graphql",
            json={"query": query, "variables": dict(variables or {})},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DataHubResponseError("DataHub returned non-JSON GraphQL content") from exc
        if not isinstance(payload, dict):
            raise DataHubResponseError("DataHub GraphQL response must be an object")
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            raise DataHubGraphQLError([item for item in errors if isinstance(item, Mapping)])
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DataHubResponseError("DataHub GraphQL response is missing data")
        return data

    def search(
        self,
        query: str,
        *,
        entity_types: Sequence[str] = ("DATASET",),
        start: int = 0,
        count: int = 20,
    ) -> SearchPage:
        data = self.graphql(
            _SEARCH_QUERY,
            {
                "input": {
                    "query": query,
                    "types": list(entity_types),
                    "start": start,
                    "count": count,
                }
            },
        )
        page = data.get("searchAcrossEntities")
        if not isinstance(page, Mapping):
            raise DataHubResponseError("searchAcrossEntities is missing")
        raw_hits = page.get("searchResults", [])
        if not isinstance(raw_hits, list):
            raise DataHubResponseError("searchResults must be a list")
        hits: list[SearchHit] = []
        for raw_hit in raw_hits:
            if not isinstance(raw_hit, Mapping):
                continue
            entity = raw_hit.get("entity")
            if not isinstance(entity, Mapping) or not isinstance(entity.get("urn"), str):
                continue
            properties = entity.get("properties")
            name = entity.get("name")
            description = None
            if isinstance(properties, Mapping):
                name = name or properties.get("name")
                description = properties.get("description")
            matched = raw_hit.get("matchedFields", [])
            hits.append(
                SearchHit(
                    urn=str(entity["urn"]),
                    entity_type=_optional_str(entity.get("type")),
                    name=_optional_str(name),
                    description=_optional_str(description),
                    matched_fields=tuple(item for item in matched if isinstance(item, Mapping))
                    if isinstance(matched, list)
                    else (),
                    raw=dict(raw_hit),
                )
            )
        return SearchPage(
            start=_as_int(page.get("start")) or start,
            count=_as_int(page.get("count")) or len(hits),
            total=_as_int(page.get("total")) or len(hits),
            hits=tuple(hits),
        )

    def get_entity(self, urn: str) -> JsonObject:
        data = self.graphql(_ENTITY_QUERY, {"urn": urn})
        entity = data.get("entity")
        if entity is None:
            raise DataHubResponseError(f"DataHub entity not found: {urn}")
        if not isinstance(entity, dict):
            raise DataHubResponseError("DataHub entity response must be an object")
        return entity

    def get_audit_metadata(
        self,
        urn: str,
        *,
        entity_type: str = "dataset",
        aspects: Sequence[str] = (
            "datasetProperties",
            "ownership",
            "globalTags",
            "upstreamLineage",
        ),
    ) -> AuditMetadata:
        """Read OpenAPI aspect envelopes and normalize audit/system metadata."""

        encoded_type = quote(entity_type, safe="")
        encoded_urn = quote(urn, safe="")
        response = self._request(
            "GET",
            f"/openapi/v3/entity/{encoded_type}/{encoded_urn}",
            params={
                "aspects": ",".join(aspects),
                "systemMetadata": "true",
            },
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DataHubResponseError("DataHub returned non-JSON OpenAPI content") from exc
        if not isinstance(payload, dict):
            raise DataHubResponseError("DataHub OpenAPI response must be an object")
        raw_aspects = payload.get("aspects")
        if raw_aspects is None:
            raw_aspects = {
                key: value
                for key, value in payload.items()
                if key != "urn" and isinstance(value, Mapping)
            }
        if not isinstance(raw_aspects, Mapping):
            raise DataHubResponseError("DataHub OpenAPI response has invalid aspects")

        stamps: list[AuditStamp] = []
        systems: dict[str, Mapping[str, Any]] = {}
        values: dict[str, Any] = {}
        for aspect_name, raw_envelope in raw_aspects.items():
            if not isinstance(aspect_name, str) or not isinstance(raw_envelope, Mapping):
                continue
            envelope = dict(raw_envelope)
            values[aspect_name] = envelope.get("value")
            system = envelope.get("systemMetadata")
            if isinstance(system, Mapping):
                systems[aspect_name] = dict(system)
            for key in ("auditStamp", "created", "lastModified"):
                raw_stamp = envelope.get(key)
                if isinstance(raw_stamp, Mapping):
                    stamps.append(
                        AuditStamp(
                            aspect=aspect_name,
                            kind=key,
                            time_ms=_as_int(raw_stamp.get("time")),
                            actor=_optional_str(
                                raw_stamp.get("actor") or raw_stamp.get("lastModifiedBy")
                            ),
                            raw=dict(raw_stamp),
                        )
                    )
            value = envelope.get("value")
            if isinstance(value, Mapping):
                raw_stamp = value.get("auditStamp")
                if isinstance(raw_stamp, Mapping):
                    stamps.append(
                        AuditStamp(
                            aspect=aspect_name,
                            kind="value.auditStamp",
                            time_ms=_as_int(raw_stamp.get("time")),
                            actor=_optional_str(raw_stamp.get("actor")),
                            raw=dict(raw_stamp),
                        )
                    )

        return AuditMetadata(
            urn=urn,
            entity_type=entity_type,
            audit_stamps=tuple(stamps),
            system_metadata=systems,
            aspect_values=values,
            raw=payload,
        )

    def get_lineage(
        self,
        urn: str,
        *,
        direction: str = "DOWNSTREAM",
        start: int = 0,
        count: int = 50,
    ) -> LineagePage:
        normalized_direction = direction.upper()
        if normalized_direction not in {"UPSTREAM", "DOWNSTREAM"}:
            raise ValueError("direction must be UPSTREAM or DOWNSTREAM")
        data = self.graphql(
            _LINEAGE_QUERY,
            {
                "input": {
                    "urn": urn,
                    "direction": normalized_direction,
                    "query": "*",
                    "start": start,
                    "count": count,
                }
            },
        )
        page = data.get("searchAcrossLineage")
        if not isinstance(page, Mapping):
            raise DataHubResponseError("searchAcrossLineage is missing")
        raw_hits = page.get("searchResults", [])
        if not isinstance(raw_hits, list):
            raise DataHubResponseError("lineage searchResults must be a list")
        hits: list[LineageHit] = []
        for raw_hit in raw_hits:
            if not isinstance(raw_hit, Mapping):
                continue
            entity = raw_hit.get("entity")
            if not isinstance(entity, Mapping) or not isinstance(entity.get("urn"), str):
                continue
            hits.append(
                LineageHit(
                    urn=str(entity["urn"]),
                    entity_type=_optional_str(entity.get("type")),
                    degree=_as_int(raw_hit.get("degree")),
                    direction=normalized_direction,
                    raw=dict(raw_hit),
                )
            )
        return LineagePage(
            start=_as_int(page.get("start")) or start,
            count=_as_int(page.get("count")) or len(hits),
            total=_as_int(page.get("total")) or len(hits),
            hits=tuple(hits),
        )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
