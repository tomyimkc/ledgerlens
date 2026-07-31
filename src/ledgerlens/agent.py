"""Deterministic LedgerLens policy with optional 020s phrasing."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from ledgerlens.config import Settings
from ledgerlens.datahub_client import DataHubClient, DataHubError
from ledgerlens.datahub_ingest import is_ledgerlens_finding_urn
from ledgerlens.mcp_client import DataHubMCPClient, MCPError
from ledgerlens.provenance import (
    ProvenanceConflictError,
    ProvenanceRecord,
    extract_custom_properties,
    merge_provenance,
)

JsonObject = dict[str, Any]
_CLAIM_CEILING = (
    "Working prototype for metadata triage; not independent validation and not evidence of AGI."
)


class AgentError(RuntimeError):
    """Base agent workflow error."""


class AgentGroundingError(AgentError):
    """Raised when a requested finding cannot be grounded."""


class AgentModelError(AgentError):
    """Raised when optional model phrasing fails."""


class PhraseModel(Protocol):
    def phrase(self, facts: Mapping[str, Any]) -> str:
        """Phrase immutable grounded facts without adding claims."""


class OpenAICompatible020s:
    """Minimal OpenAI-compatible client fixed to the 020s API."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = settings.require_020s_key()
        if settings.llm_base_url != "https://api.020s.com/v1":
            raise ValueError("020s credentials may only be sent to https://api.020s.com/v1")
        self.model = settings.llm_model
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=settings.llm_base_url,
            timeout=httpx.Timeout(
                settings.llm_timeout_seconds,
                connect=min(settings.llm_timeout_seconds, 5.0),
            ),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "ledgerlens/0.1",
            },
            transport=transport,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def phrase(self, facts: Mapping[str, Any]) -> str:
        """Generate prose only; the returned text cannot alter factual fields."""

        prompt = (
            "Phrase the supplied grounded DataHub facts in at most 90 words. "
            "Do not add facts, validation claims, causal claims, or AGI claims. "
            "Explicitly say missing metadata is unknown. Facts:\n"
            + json.dumps(facts, sort_keys=True)
        )
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You only phrase immutable facts selected by deterministic policy."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AgentModelError("020s phrasing request failed") from exc
        if not isinstance(text, str) or not text.strip():
            raise AgentModelError("020s returned an empty phrase")
        return text.strip()


class LedgerLensAgent:
    """Grounded workflows whose factual policy never depends on an LLM."""

    def __init__(
        self,
        mcp_client: DataHubMCPClient,
        datahub_client: DataHubClient,
        *,
        phrase_model: PhraseModel | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.datahub = datahub_client
        self.phrase_model = phrase_model
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        mcp_client: DataHubMCPClient,
        datahub_client: DataHubClient,
    ) -> LedgerLensAgent:
        model: PhraseModel | None = OpenAICompatible020s(settings) if settings.llm_enabled else None
        return cls(mcp_client, datahub_client, phrase_model=model)

    def explain_finding(self, urn: str) -> JsonObject:
        record = self._load_record(urn)
        factual = record.to_dict()
        result = self._envelope("explainFinding")
        result.update(
            {
                "finding": factual,
                "decision": "blocked" if record.missing_metadata else "grounded",
                "explanation": self._deterministic_explanation(record),
            }
        )
        self._add_optional_narrative(result, factual)
        return result

    def supersession_chain(self, urn: str, *, max_hops: int = 8) -> JsonObject:
        """Follow explicit supersession properties; lineage is context, not proof."""

        if max_hops < 1:
            raise ValueError("max_hops must be positive")
        root = self._load_record(urn)
        visited = {root.urn}
        ancestors: list[ProvenanceRecord] = []
        descendants: list[ProvenanceRecord] = []
        cycle_detected = False
        truncated = False

        current = root
        while current.supersedes:
            if len(ancestors) + 1 + len(descendants) >= max_hops:
                truncated = True
                break
            target_urn = _finding_reference_to_urn(current.supersedes[0])
            if target_urn in visited:
                cycle_detected = True
                break
            current = self._load_record(target_urn)
            visited.add(current.urn)
            ancestors.append(current)

        current = root
        while current.superseded_by and not cycle_detected:
            if len(ancestors) + 1 + len(descendants) >= max_hops:
                truncated = True
                break
            target_urn = _finding_reference_to_urn(current.superseded_by[0])
            if target_urn in visited:
                cycle_detected = True
                break
            current = self._load_record(target_urn)
            visited.add(current.urn)
            descendants.append(current)

        chain = [record.to_dict() for record in [*reversed(ancestors), root, *descendants]]
        lineage_direction = "upstream" if root.supersedes else "downstream"
        lineage = self.mcp.get_lineage(
            urn,
            direction=lineage_direction,
            max_hops=max_hops,
            count=50,
        )
        result = self._envelope("supersessionChain")
        result.update(
            {
                "rootUrn": urn,
                "chain": chain,
                "cycleDetected": cycle_detected,
                "truncated": truncated,
                "lineageContext": lineage,
                "lineageWarning": (
                    "DataHub lineage is contextual only. An entity joins the supersession "
                    "chain only when explicit supersededBy metadata names it."
                ),
            }
        )
        return result

    def missing_metadata_query(
        self,
        query: str = "*",
        *,
        count: int = 100,
    ) -> JsonObject:
        records, conflicts = self._search_records(query, count=count)
        missing = [
            {
                "urn": record.urn,
                "title": record.title,
                "missingMetadata": list(record.missing_metadata),
                "candidateOnly": True,
                "canClaimAGI": False,
            }
            for record in records
            if record.missing_metadata
        ]
        missing.sort(key=lambda item: (item["urn"], item["missingMetadata"]))
        result = self._envelope("missingMetadataQuery")
        result.update(
            {
                "query": query,
                "items": missing,
                "conflicts": conflicts,
                "decision": "blocked" if conflicts else "grounded",
            }
        )
        return result

    def prioritized_remediation_queue(
        self,
        query: str = "*",
        *,
        count: int = 100,
    ) -> JsonObject:
        records, conflicts = self._search_records(query, count=count)
        items: list[JsonObject] = []
        for record in records:
            status = (record.status or "unknown").lower()
            if status in {"resolved", "closed", "rejected", "superseded"} or record.superseded_by:
                continue
            score, reasons = _priority(record)
            items.append(
                {
                    "urn": record.urn,
                    "title": record.title,
                    "status": record.status,
                    "owners": list(record.owners),
                    "evidenceReferences": list(record.evidence_references),
                    "missingMetadata": list(record.missing_metadata),
                    "priorityScore": score,
                    "priorityReasons": reasons,
                    "candidateOnly": True,
                    "canClaimAGI": False,
                }
            )
        items.sort(key=lambda item: (-item["priorityScore"], item["urn"]))
        result = self._envelope("prioritizedRemediationQueue")
        result.update(
            {
                "query": query,
                "items": items,
                "conflicts": conflicts,
                "decision": "blocked" if conflicts else "grounded",
            }
        )
        return result

    def write_report(
        self,
        report: Mapping[str, Any],
        path: str | Path,
        *,
        format: str | None = None,
    ) -> Path:
        """Write grounded JSON or Markdown without model involvement."""

        destination = Path(path)
        output_format = (format or destination.suffix.lstrip(".") or "json").lower()
        if output_format not in {"json", "md", "markdown"}:
            raise ValueError("report format must be json or markdown")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "json":
            text = json.dumps(dict(report), indent=2, sort_keys=True) + "\n"
        else:
            text = _render_markdown(report)
        destination.write_text(text, encoding="utf-8")
        return destination

    def _load_record(self, urn: str) -> ProvenanceRecord:
        entities = self.mcp.get_entities([urn])
        exact = [entity for entity in entities if entity.get("urn") == urn]
        if not exact:
            raise AgentGroundingError(f"MCP did not return the requested URN: {urn}")
        try:
            graph = self.datahub.get_entity(urn)
            audit = self.datahub.get_audit_metadata(urn)
            return merge_provenance(exact[0], graphql_entity=graph, audit_metadata=audit)
        except ProvenanceConflictError as exc:
            raise AgentGroundingError(f"Contradictory metadata for {urn}: {exc}") from exc
        except (DataHubError, MCPError) as exc:
            raise AgentGroundingError(f"Could not ground {urn}: {exc}") from exc

    def _search_records(
        self,
        query: str,
        *,
        count: int,
    ) -> tuple[list[ProvenanceRecord], list[JsonObject]]:
        search_results = self.mcp.search(query, count=count)
        urns = sorted(
            {str(result["urn"]) for result in search_results if isinstance(result.get("urn"), str)}
        )
        urns = [urn for urn in urns if is_ledgerlens_finding_urn(urn)]
        if not urns:
            return [], []
        entities = {item.get("urn"): item for item in self.mcp.get_entities(urns)}
        records: list[ProvenanceRecord] = []
        conflicts: list[JsonObject] = []
        for urn in urns:
            mcp_entity = entities.get(urn)
            if not isinstance(mcp_entity, Mapping):
                conflicts.append({"urn": urn, "error": "missing MCP entity"})
                continue
            try:
                graph = self.datahub.get_entity(urn)
                audit = self.datahub.get_audit_metadata(urn)
                records.append(
                    merge_provenance(
                        mcp_entity,
                        graphql_entity=graph,
                        audit_metadata=audit,
                    )
                )
            except (ProvenanceConflictError, DataHubError, MCPError) as exc:
                conflicts.append({"urn": urn, "error": str(exc)})
        return records, conflicts

    def _envelope(self, workflow: str) -> JsonObject:
        return {
            "schemaVersion": "1.0",
            "workflow": workflow,
            "generatedAt": self._clock().astimezone(UTC).isoformat(),
            "candidateOnly": True,
            "canClaimAGI": False,
            "claimCeiling": _CLAIM_CEILING,
        }

    def _deterministic_explanation(self, record: ProvenanceRecord) -> str:
        state = record.status or "unknown status"
        missing = (
            f" Missing metadata: {', '.join(record.missing_metadata)}."
            if record.missing_metadata
            else ""
        )
        return (
            f"{record.urn} is recorded with {state}. "
            f"LedgerLens does not independently validate the finding.{missing}"
        )

    def _add_optional_narrative(
        self,
        result: JsonObject,
        immutable_facts: Mapping[str, Any],
    ) -> None:
        if self.phrase_model is not None:
            result["modelNarrative"] = self.phrase_model.phrase(immutable_facts)
            result["modelNarrativeRole"] = "phrasing only; factual fields are deterministic"


Agent = LedgerLensAgent


def _finding_reference_to_urn(reference: str) -> str:
    if reference.startswith("urn:li:"):
        return reference
    from ledgerlens.datahub_ingest import dataset_urn

    return dataset_urn(reference)


def _priority(record: ProvenanceRecord) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    weights = {
        "evidenceReferences": 100,
        "owner": 80,
        "scientificValidation": 60,
        "datahubIngestionAudit": 40,
        "status": 30,
    }
    for missing in record.missing_metadata:
        weight = weights.get(missing, 20)
        score += weight
        reasons.append(f"missing {missing} (+{weight})")
    status = (record.status or "").lower()
    if status in {"open", "stale", "unverified", "unknown"}:
        score += 20
        reasons.append(f"unresolved status {status or 'unknown'} (+20)")
    properties = extract_custom_properties({"customProperties": record.custom_properties})
    stale = str(properties.get("stale", "")).lower() in {"true", "1", "yes"}
    if stale and status != "stale":
        score += 20
        reasons.append("explicitly stale (+20)")
    return score, reasons


def _render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# LedgerLens grounded report",
        "",
        f"- Workflow: `{report.get('workflow', 'unknown')}`",
        f"- Generated: `{report.get('generatedAt', 'unknown')}`",
        "- `candidateOnly: true`",
        "- `canClaimAGI: false`",
        f"- Claim ceiling: {report.get('claimCeiling', _CLAIM_CEILING)}",
        "",
    ]
    items = report.get("items")
    if not isinstance(items, list):
        finding = report.get("finding")
        items = [finding] if isinstance(finding, Mapping) else []
    lines.extend(["## Findings", ""])
    if not items:
        lines.append("_No grounded findings selected._")
    for item in items:
        if not isinstance(item, Mapping):
            continue
        urn = item.get("urn", "unknown")
        title = item.get("title") or urn
        lines.extend(
            [
                f"### {title}",
                "",
                f"- URN: `{urn}`",
                f"- Status: `{item.get('status', 'unknown')}`",
                f"- Owners: {', '.join(item.get('owners', [])) or 'unknown'}",
                "- Evidence:",
            ]
        )
        evidence = item.get("evidenceReferences", [])
        if isinstance(evidence, list) and evidence:
            lines.extend(f"  - `{reference}`" for reference in evidence)
        else:
            lines.append("  - unknown")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
