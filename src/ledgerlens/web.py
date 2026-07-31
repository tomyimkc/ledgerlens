"""FastAPI demo surface and a small adapter contract for LedgerLens.

Importing this module does not require FastAPI.  Optional web dependencies are
loaded inside :func:`create_app`, while the deterministic fixture adapter remains
available to the CLI and tests.
"""

import asyncio
import copy
import importlib
import inspect
import json
import os
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

AdapterFactory = Callable[..., Any]

_PACKAGE_ROOT = Path(__file__).resolve().parent
_TEMPLATE_ROOT = _PACKAGE_ROOT / "templates"
_STATIC_ROOT = _PACKAGE_ROOT / "static"
_FACTORY_ENV = "LEDGERLENS_ADAPTER_FACTORY"
_INCIDENT_FACTORY_ENV = "LEDGERLENS_INCIDENT_BACKEND_FACTORY"
_FACTORY_CANDIDATES = (
    "ledgerlens.runtime:create_adapter",
    "ledgerlens.services:create_adapter",
    "ledgerlens.core:create_adapter",
)
_SECRET_KEY = re.compile(
    r"(authorization|cookie|password|secret|token|api[_-]?key|credential)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_SECRET = re.compile(r"(?i)\b(token|password|secret|api[_-]?key)=([^&\s]+)")

DEMO_FINDINGS: tuple[dict[str, Any], ...] = (
    {
        "id": "ledger-validator-blind-spots-2026-07-26",
        "title": "Ledger parser needs strict malformed-row detection",
        "summary": (
            "A historical parser accepted duplicate identifiers and ambiguous Markdown "
            "boundaries. The fixture preserves the finding as an unverified engineering "
            "record, not independent validation."
        ),
        "status": "superseded",
        "kind": "methodology",
        "priority": "high",
        "owner": {"name": "Provenance Engineering", "type": "group"},
        "evidence_receipts": [
            {
                "label": "Sanitized parser regression receipt",
                "uri": "fixture://receipts/parser-regression-v1.json",
                "verified": False,
            }
        ],
        "audit": {
            "ingested_at": "2026-07-31T02:00:00Z",
            "ingested_by": "ledgerlens-demo",
            "datahub_urn": (
                "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,"
                "ledger-validator-blind-spots-2026-07-26,PROD)"
            ),
            "source_mode": "deterministic-fixture",
        },
        "supersedes": [],
        "superseded_by": ["strict-parser-fixture-suite-2026-07-31"],
        "stale": True,
        "unverified": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "required_action": "Use the strict parser fixture suite for current remediation.",
    },
    {
        "id": "strict-parser-fixture-suite-2026-07-31",
        "title": "Strict parser fixture suite is awaiting integration",
        "summary": (
            "A deterministic test plan covers duplicate IDs, escaped pipes, backticks, "
            "and malformed rows. Integration status remains open until the executable "
            "adapter and receipts are attached."
        ),
        "status": "open",
        "kind": "engineering",
        "priority": "medium",
        "owner": {"name": "Ledger Adapter", "type": "group"},
        "evidence_receipts": [
            {
                "label": "Fixture specification",
                "uri": "fixture://receipts/strict-parser-cases.json",
                "verified": False,
            }
        ],
        "audit": {
            "ingested_at": "2026-07-31T02:00:00Z",
            "ingested_by": "ledgerlens-demo",
            "datahub_urn": (
                "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,"
                "strict-parser-fixture-suite-2026-07-31,PROD)"
            ),
            "source_mode": "deterministic-fixture",
        },
        "supersedes": ["ledger-validator-blind-spots-2026-07-26"],
        "superseded_by": [],
        "stale": False,
        "unverified": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "required_action": "Attach executable test receipts after adapter integration.",
    },
    {
        "id": "mcp-audit-surface-gap-2026-07-26",
        "title": "MCP surface omits provenance audit fields used by triage",
        "summary": (
            "The historical infrastructure probe reported that agent-facing metadata "
            "did not include every audit field needed for the proposed workflow. This "
            "demo uses a read-only audit bridge and labels the source of each field."
        ),
        "status": "open",
        "kind": "infrastructure",
        "priority": "high",
        "owner": {"name": "DataHub Integration", "type": "group"},
        "evidence_receipts": [
            {
                "label": "Sanitized MCP response shape",
                "uri": "fixture://receipts/mcp-audit-surface.json",
                "verified": False,
            }
        ],
        "audit": {
            "ingested_at": "2026-07-31T02:00:00Z",
            "ingested_by": "ledgerlens-demo",
            "datahub_urn": (
                "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,"
                "mcp-audit-surface-gap-2026-07-26,PROD)"
            ),
            "source_mode": "deterministic-fixture",
        },
        "supersedes": [],
        "superseded_by": [],
        "stale": False,
        "unverified": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "required_action": "Verify current MCP fields and retain the bridge only if needed.",
    },
    {
        "id": "unowned-evidence-receipt-2026-07-31",
        "title": "Finding has neither an owner nor an evidence receipt",
        "summary": (
            "This synthetic contest fixture demonstrates the remediation queue's "
            "fail-closed behavior when provenance metadata is incomplete."
        ),
        "status": "unverified",
        "kind": "governance",
        "priority": "critical",
        "owner": None,
        "evidence_receipts": [],
        "audit": {
            "ingested_at": "2026-07-31T02:00:00Z",
            "ingested_by": "ledgerlens-demo",
            "datahub_urn": (
                "urn:li:dataset:(urn:li:dataPlatform:ledgerlens,"
                "unowned-evidence-receipt-2026-07-31,PROD)"
            ),
            "source_mode": "deterministic-fixture",
        },
        "supersedes": [],
        "superseded_by": [],
        "stale": False,
        "unverified": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "required_action": "Assign an owner and attach a reviewable evidence receipt.",
    },
)


class AdapterUnavailableError(RuntimeError):
    """Raised when no live adapter factory can be located."""


def _safe_text(value: object) -> str:
    text = str(value)
    text = _BEARER.sub(r"\1[REDACTED]", text)
    return _ASSIGNMENT_SECRET.sub(r"\1=[REDACTED]", text)


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_plain(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_plain(model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return _to_plain(vars(value))
    return _safe_text(value)


def redact_diagnostics(value: Any) -> Any:
    """Return a JSON-safe structure with credential-like fields removed."""

    plain = _to_plain(value)
    if isinstance(plain, dict):
        return {
            key: "[REDACTED]" if _SECRET_KEY.search(key) else redact_diagnostics(item)
            for key, item in plain.items()
        }
    if isinstance(plain, list):
        return [redact_diagnostics(item) for item in plain]
    if isinstance(plain, str):
        return _safe_text(plain)
    return plain


def _public_endpoint(url: str | None) -> str:
    if not url:
        return "not configured"
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "configured (hidden)"
    if not parsed.scheme or not parsed.hostname:
        return "configured (hidden)"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _priority_score(finding: Mapping[str, Any]) -> int:
    score = {
        "critical": 400,
        "high": 300,
        "medium": 200,
        "low": 100,
    }.get(str(finding.get("priority", "")).lower(), 0)
    if not finding.get("owner"):
        score += 40
    if not finding.get("evidence_receipts"):
        score += 30
    if finding.get("stale"):
        score += 20
    if finding.get("unverified"):
        score += 10
    return score


class DemoDataAdapter:
    """Deterministic, read-only fixture adapter.

    Every response labels fixture mode and reports that no live DataHub request or
    mutation occurred.
    """

    mode = "demo"

    def __init__(self, findings: Sequence[Mapping[str, Any]] | None = None) -> None:
        source = findings if findings is not None else DEMO_FINDINGS
        self._findings = [copy.deepcopy(dict(item)) for item in source]
        self._by_id = {str(item["id"]): item for item in self._findings}

    def connection_status(self) -> dict[str, Any]:
        return {
            "mode": "demo",
            "connected": False,
            "label": "Demo fixture — DataHub was not contacted",
            "endpoint": _public_endpoint(os.getenv("DATAHUB_GMS_URL")),
            "mcp": "not contacted",
            "ingested_findings": len(self._findings),
            "checked_at": "2026-07-31T02:00:00Z",
            "diagnostic": "Deterministic in-memory fixture; no live state is implied.",
        }

    def list_findings(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._findings)

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        finding = self._by_id.get(finding_id)
        return copy.deepcopy(finding) if finding is not None else None

    def validate(self, source: Path | None = None) -> dict[str, Any]:
        return {
            "valid": True,
            "mode": "demo",
            "source": str(source) if source else "built-in deterministic fixture",
            "finding_count": len(self._findings),
            "errors": [],
            "warnings": [
                "Fixture findings are unverified and do not constitute independent validation."
            ],
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def ingest(self, source: Path | None = None) -> dict[str, Any]:
        return {
            "mode": "demo",
            "mutated": False,
            "source": str(source) if source else "built-in deterministic fixture",
            "finding_count": len(self._findings),
            "message": "Fixture loaded in memory; DataHub was not contacted or mutated.",
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def explain(self, finding_id: str) -> dict[str, Any]:
        finding = self.get_finding(finding_id)
        if finding is None:
            raise KeyError(f"Finding not found: {finding_id}")
        return {
            "mode": "demo",
            "finding": finding,
            "explanation": (
                "LedgerLens reports the recorded metadata and its gaps. It does not "
                "independently validate the underlying claim."
            ),
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def supersession(self, finding_id: str) -> dict[str, Any]:
        if finding_id not in self._by_id:
            raise KeyError(f"Finding not found: {finding_id}")

        def ancestors(identifier: str, seen: set[str]) -> list[str]:
            if identifier in seen:
                return []
            seen.add(identifier)
            item = self._by_id[identifier]
            result: list[str] = []
            for previous in item.get("supersedes", []):
                if previous in self._by_id:
                    result.extend(ancestors(previous, seen))
            result.append(identifier)
            return result

        ordered = ancestors(finding_id, set())
        cursor = finding_id
        seen_forward = set(ordered)
        while True:
            successors = [
                item_id
                for item_id in self._by_id[cursor].get("superseded_by", [])
                if item_id in self._by_id and item_id not in seen_forward
            ]
            if not successors:
                break
            cursor = sorted(successors)[0]
            ordered.append(cursor)
            seen_forward.add(cursor)

        chain = [self.get_finding(identifier) for identifier in ordered]
        return {
            "mode": "demo",
            "requested_id": finding_id,
            "chain": chain,
            "current_id": ordered[-1],
            "note": "History is preserved; supersession does not validate either record.",
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def triage(self) -> dict[str, Any]:
        actionable = [
            item
            for item in self._findings
            if str(item.get("status", "")).lower() not in {"resolved", "superseded"}
        ]
        queue: list[dict[str, Any]] = []
        for item in actionable:
            gaps: list[str] = []
            if not item.get("owner"):
                gaps.append("missing owner")
            if not item.get("evidence_receipts"):
                gaps.append("missing evidence receipt")
            if item.get("stale"):
                gaps.append("stale")
            if item.get("unverified"):
                gaps.append("unverified")
            queue.append(
                {
                    "rank": 0,
                    "score": _priority_score(item),
                    "finding_id": item["id"],
                    "title": item["title"],
                    "priority": item["priority"],
                    "owner": item.get("owner"),
                    "gaps": gaps,
                    "required_action": item["required_action"],
                    "datahub_urn": item["audit"]["datahub_urn"],
                }
            )
        queue.sort(key=lambda item: (-int(item["score"]), str(item["finding_id"])))
        for rank, item in enumerate(queue, start=1):
            item["rank"] = rank
        return {
            "mode": "demo",
            "generated_at": "2026-07-31T02:00:00Z",
            "queue": queue,
            "summary": {
                "actionable": len(queue),
                "missing_owner": sum(not item.get("owner") for item in actionable),
                "missing_evidence": sum(not item.get("evidence_receipts") for item in actionable),
                "unverified": sum(bool(item.get("unverified")) for item in actionable),
            },
            "note": "Deterministic fixture output; DataHub was not contacted.",
            "candidateOnly": True,
            "canClaimAGI": False,
        }


class CoreDataAdapter:
    """Lazy integration adapter for the parser, DataHub clients, and agent modules."""

    mode = "live"

    def __init__(self) -> None:
        self._settings: Any | None = None
        self._datahub: Any | None = None
        self._mcp: Any | None = None
        self._agent: Any | None = None
        self._lock = threading.RLock()

    def _get_settings(self) -> Any:
        if self._settings is None:
            from ledgerlens.config import get_settings

            self._settings = get_settings()
        return self._settings

    def _get_datahub(self) -> Any:
        with self._lock:
            if self._datahub is None:
                from ledgerlens.datahub_client import DataHubClient

                settings = self._get_settings()
                self._datahub = DataHubClient(
                    settings.datahub_gms_url,
                    token=settings.datahub_token_value(),
                    timeout=settings.datahub_timeout_seconds,
                )
            return self._datahub

    def _get_mcp(self) -> Any:
        with self._lock:
            if self._mcp is None:
                from ledgerlens.mcp_client import DataHubMCPClient

                settings = self._get_settings()
                if settings.datahub_mcp_url:
                    self._mcp = DataHubMCPClient.from_http(
                        settings.datahub_mcp_url,
                        token=settings.datahub_token_value(),
                        timeout=settings.mcp_timeout_seconds,
                    )
                elif settings.mcp_command_argv:
                    self._mcp = DataHubMCPClient.from_stdio(
                        settings.mcp_command_argv,
                        timeout=settings.mcp_timeout_seconds,
                    )
                else:
                    raise AdapterUnavailableError(
                        "Neither DATAHUB_MCP_URL nor DATAHUB_MCP_COMMAND is configured."
                    )
            return self._mcp

    def _get_agent(self) -> Any:
        with self._lock:
            if self._agent is None:
                from ledgerlens.agent import LedgerLensAgent

                self._agent = LedgerLensAgent.from_settings(
                    self._get_settings(),
                    mcp_client=self._get_mcp(),
                    datahub_client=self._get_datahub(),
                )
            return self._agent

    def close(self) -> None:
        """Release live HTTP, MCP, and optional phrasing clients."""

        with self._lock:
            phrase_model = getattr(self._agent, "phrase_model", None)
            close_model = getattr(phrase_model, "close", None)
            if callable(close_model):
                close_model()
            for client in (self._mcp, self._datahub):
                close = getattr(client, "close", None)
                if callable(close):
                    close()
            self._agent = None
            self._mcp = None
            self._datahub = None

    def validate(self, source: Path | None = None) -> dict[str, Any]:
        if source is None:
            raise ValueError("A ledger source path is required.")
        from ledgerlens.parser import parse_ledger_file

        result = parse_ledger_file(source, strict=False)
        return {
            "mode": "local-validation",
            "source": str(source),
            "valid": result.is_valid,
            "finding_count": len(result.findings),
            "valid_finding_count": len(result.valid_findings),
            "malformed_finding_count": len(result.malformed_findings),
            "diagnostics": [
                diagnostic.model_dump(mode="json", exclude_none=True)
                for diagnostic in result.diagnostics
            ],
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def ingest(self, source: Path | None = None) -> dict[str, Any]:
        if source is None:
            raise ValueError("A ledger source path is required.")
        try:
            from datahub.emitter.rest_emitter import DatahubRestEmitter
            from datahub.metadata.schema_classes import (
                ChangeTypeClass,
                GenericAspectClass,
                MetadataChangeProposalClass,
            )
        except ImportError as exc:
            raise AdapterUnavailableError(
                "Live ingestion requires the LedgerLens 'datahub' extra."
            ) from exc
        from ledgerlens.datahub_ingest import build_datahub_bundle
        from ledgerlens.parser import parse_ledger_file

        result = parse_ledger_file(source, strict=True)
        bundle = build_datahub_bundle(result)
        settings = self._get_settings()
        emitter = DatahubRestEmitter(
            settings.datahub_gms_url,
            token=settings.datahub_token_value(),
            timeout_sec=settings.datahub_timeout_seconds,
        )
        emitted = 0
        try:
            for proposal in bundle["mcps"]:
                aspect = proposal["aspect"]
                aspect_value = aspect["value"]
                encoded_value = json.dumps(
                    aspect_value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                emitter.emit_mcp(
                    MetadataChangeProposalClass(
                        entityType=proposal["entityType"],
                        entityUrn=proposal["entityUrn"],
                        changeType=ChangeTypeClass.UPSERT,
                        aspectName=proposal["aspectName"],
                        aspect=GenericAspectClass(
                            contentType=aspect["contentType"],
                            value=encoded_value,
                        ),
                    )
                )
                emitted += 1
        finally:
            close = getattr(emitter, "close", None)
            if callable(close):
                close()

        return {
            "mode": "live",
            "mutated": True,
            "source": str(source),
            "finding_count": len(result.valid_findings),
            "dataset_count": len(bundle["datasets"]),
            "tag_count": len(bundle["tags"]),
            "lineage_edge_count": len(bundle["lineage"]),
            "proposals_emitted": emitted,
            "datahub_endpoint": _public_endpoint(settings.datahub_gms_url),
            "dataset_urns": [dataset["urn"] for dataset in bundle["datasets"]],
            "candidateOnly": True,
            "canClaimAGI": False,
            "note": (
                "DataHub accepted metadata proposals. This is an ingestion receipt, "
                "not independent validation of any finding."
            ),
        }

    def connection_status(self) -> dict[str, Any]:
        settings = self._get_settings()
        checked_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        datahub_ok = False
        mcp_ok = False
        total = 0
        diagnostics: list[str] = []
        try:
            page = self._get_datahub().search("ledgerlens.failure_ledger", count=1)
            total = int(page.total)
            datahub_ok = True
        except Exception as exc:
            diagnostics.append(f"DataHub: {_safe_text(exc)}")
        try:
            self._get_mcp().search("ledgerlens.failure_ledger", count=1)
            mcp_ok = True
        except Exception as exc:
            diagnostics.append(f"MCP: {_safe_text(exc)}")
        connected = datahub_ok and mcp_ok
        return {
            "mode": "live",
            "connected": connected,
            "label": (
                "DataHub and MCP connected" if connected else "Live integration needs attention"
            ),
            "endpoint": _public_endpoint(settings.datahub_gms_url),
            "mcp": "connected" if mcp_ok else "unavailable",
            "ingested_findings": total,
            "checked_at": checked_at,
            "diagnostic": "; ".join(diagnostics) or "Read-only health checks passed.",
        }

    @staticmethod
    def _urn_for(identifier: str) -> str:
        if identifier.startswith("urn:li:"):
            return identifier
        from ledgerlens.datahub_ingest import dataset_urn

        return dataset_urn(identifier)

    @staticmethod
    def _priority_from_record(record: Mapping[str, Any]) -> str:
        missing = record.get("missingMetadata", [])
        count = len(missing) if isinstance(missing, list) else 0
        if count >= 3:
            return "critical"
        if count == 2:
            return "high"
        if count == 1:
            return "medium"
        return "low"

    @classmethod
    def _finding_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        properties = record.get("customProperties")
        props = properties if isinstance(properties, Mapping) else {}
        urn = str(record.get("urn", ""))
        finding_id = str(
            props.get("ledgerlens.findingId")
            or props.get("findingId")
            or record.get("title")
            or urn
        )
        owners_raw = record.get("owners")
        owners = owners_raw if isinstance(owners_raw, list) else []
        evidence_raw = record.get("evidenceReferences")
        evidence = evidence_raw if isinstance(evidence_raw, list) else []
        audit_raw = record.get("datahubIngestionAudit")
        audit = audit_raw if isinstance(audit_raw, Mapping) else {}
        missing_raw = record.get("missingMetadata")
        missing = missing_raw if isinstance(missing_raw, list) else []
        validation_raw = record.get("scientificValidation")
        validation = validation_raw if isinstance(validation_raw, Mapping) else {}
        status = str(
            record.get("status")
            or props.get("ledgerlens.status")
            or props.get("status")
            or "unknown"
        ).lower()
        return {
            "id": finding_id,
            "title": str(record.get("title") or finding_id),
            "summary": str(
                props.get("ledgerlens.claimImpact")
                or props.get("claimImpact")
                or "No claim-impact summary is recorded."
            ),
            "status": status,
            "kind": str(props.get("ledgerlens.kind") or props.get("kind") or "unknown"),
            "priority": cls._priority_from_record(record),
            "owner": ({"name": str(owners[0]), "type": "recorded"} if owners else None),
            "evidence_receipts": [
                {
                    "label": "Recorded evidence reference",
                    "uri": str(reference),
                    "verified": False,
                }
                for reference in evidence
            ],
            "audit": {
                "ingested_at": audit.get("time"),
                "ingested_by": audit.get("actor"),
                "datahub_urn": urn,
                "source_mode": "live-datahub",
            },
            "supersedes": list(record.get("supersedes") or []),
            "superseded_by": list(record.get("supersededBy") or []),
            "stale": status == "stale",
            "unverified": validation.get("status", "unverified") == "unverified",
            "candidateOnly": True,
            "canClaimAGI": False,
            "required_action": str(
                props.get("ledgerlens.requiredResponse")
                or props.get("requiredResponse")
                or "Review the recorded metadata gaps."
            ),
            "missing_metadata": [str(item) for item in missing],
        }

    def explain(self, finding_id: str) -> dict[str, Any]:
        report = self._get_agent().explain_finding(self._urn_for(finding_id))
        finding_raw = report.get("finding")
        finding = (
            self._finding_from_record(finding_raw) if isinstance(finding_raw, Mapping) else None
        )
        return {
            "mode": "live",
            "finding": finding,
            "decision": report.get("decision", "blocked"),
            "explanation": report.get("explanation"),
            "model_narrative": report.get("modelNarrative"),
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        try:
            finding = self.explain(finding_id).get("finding")
            return dict(finding) if isinstance(finding, Mapping) else None
        except Exception:
            return None

    def list_findings(self) -> list[dict[str, Any]]:
        from ledgerlens.datahub_ingest import is_ledgerlens_finding_urn

        hits = self._get_mcp().search("ledgerlens.failure_ledger", count=100)
        findings: list[dict[str, Any]] = []
        for hit in sorted(hits, key=lambda item: str(item.get("urn", ""))):
            urn = hit.get("urn")
            if not isinstance(urn, str) or not is_ledgerlens_finding_urn(urn):
                continue
            try:
                explained = self.explain(urn)
            except Exception:
                continue
            finding = explained.get("finding")
            if isinstance(finding, dict):
                findings.append(finding)
        return findings

    def supersession(self, finding_id: str) -> dict[str, Any]:
        report = self._get_agent().supersession_chain(self._urn_for(finding_id))
        raw_chain = report.get("chain")
        records = raw_chain if isinstance(raw_chain, list) else []
        chain = [self._finding_from_record(item) for item in records if isinstance(item, Mapping)]
        return {
            "mode": "live",
            "requested_id": finding_id,
            "chain": chain,
            "current_id": chain[-1]["id"] if chain else None,
            "lineage_context": report.get("lineageContext", []),
            "note": report.get("lineageWarning"),
            "cycle_detected": report.get("cycleDetected", False),
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def triage(self) -> dict[str, Any]:
        report = self._get_agent().prioritized_remediation_queue()
        raw_items = report.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        queue: list[dict[str, Any]] = []
        for rank, raw_item in enumerate(items, start=1):
            if not isinstance(raw_item, Mapping):
                continue
            owners_raw = raw_item.get("owners")
            owners = owners_raw if isinstance(owners_raw, list) else []
            evidence_raw = raw_item.get("evidenceReferences")
            evidence = evidence_raw if isinstance(evidence_raw, list) else []
            gaps_raw = raw_item.get("missingMetadata")
            gaps = gaps_raw if isinstance(gaps_raw, list) else []
            score = int(raw_item.get("priorityScore", 0))
            queue.append(
                {
                    "rank": rank,
                    "score": score,
                    "finding_id": str(raw_item.get("urn", "")),
                    "title": str(raw_item.get("title") or raw_item.get("urn", "Finding")),
                    "priority": (
                        "critical"
                        if score >= 250
                        else "high"
                        if score >= 160
                        else "medium"
                        if score >= 80
                        else "low"
                    ),
                    "owner": ({"name": str(owners[0]), "type": "recorded"} if owners else None),
                    "gaps": [str(item) for item in gaps],
                    "required_action": (
                        "Review the recorded metadata gaps: "
                        + (", ".join(str(item) for item in gaps) or "none recorded")
                    ),
                    "datahub_urn": str(raw_item.get("urn", "")),
                    "evidence_count": len(evidence),
                }
            )
        return {
            "mode": "live",
            "generated_at": report.get("generatedAt"),
            "queue": queue,
            "summary": {
                "actionable": len(queue),
                "missing_owner": sum("owner" in item.get("gaps", []) for item in queue),
                "missing_evidence": sum(
                    "evidenceReferences" in item.get("gaps", []) for item in queue
                ),
                "unverified": sum("scientificValidation" in item.get("gaps", []) for item in queue),
            },
            "conflicts": report.get("conflicts", []),
            "decision": report.get("decision", "blocked"),
            "note": (
                "Live DataHub/MCP metadata triage; this does not independently "
                "validate any finding."
            ),
            "candidateOnly": True,
            "canClaimAGI": False,
        }


class UnavailableDataAdapter:
    """Read-only empty adapter used to render a clear live-mode error state."""

    mode = "unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = _safe_text(reason)

    def connection_status(self) -> dict[str, Any]:
        return {
            "mode": "unavailable",
            "connected": False,
            "label": "Live adapter unavailable",
            "endpoint": _public_endpoint(os.getenv("DATAHUB_GMS_URL")),
            "mcp": "unavailable",
            "ingested_findings": 0,
            "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "diagnostic": self.reason,
        }

    def list_findings(self) -> list[dict[str, Any]]:
        return []

    def get_finding(self, finding_id: str) -> None:
        del finding_id
        return None

    def triage(self) -> dict[str, Any]:
        return {
            "mode": "unavailable",
            "generated_at": None,
            "queue": [],
            "summary": {
                "actionable": 0,
                "missing_owner": 0,
                "missing_evidence": 0,
                "unverified": 0,
            },
            "note": self.reason,
            "candidateOnly": True,
            "canClaimAGI": False,
        }

    def supersession(self, finding_id: str) -> dict[str, Any]:
        return {
            "mode": "unavailable",
            "requested_id": finding_id,
            "chain": [],
            "current_id": None,
            "note": self.reason,
            "candidateOnly": True,
            "canClaimAGI": False,
        }


def _load_factory(spec: str) -> AdapterFactory:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise AdapterUnavailableError(f"{_FACTORY_ENV} must use the form 'module:callable'.")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AdapterUnavailableError(f"Could not import adapter module '{module_name}'.") from exc
    factory = getattr(module, attribute, None)
    if not callable(factory):
        raise AdapterUnavailableError(f"Adapter factory is not callable: {spec}")
    return cast(AdapterFactory, factory)


def _call_factory(factory: AdapterFactory, demo: bool) -> Any:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(demo)
    parameters = signature.parameters
    if "demo_mode" in parameters:
        return factory(demo_mode=demo)
    if "demo" in parameters:
        return factory(demo=demo)
    if not parameters:
        return factory()
    return factory(demo)


def resolve_adapter(
    *,
    demo: bool = False,
    factory: AdapterFactory | None = None,
) -> Any:
    """Resolve an injected, configured, or conventional adapter lazily."""

    if demo:
        return DemoDataAdapter()
    if factory is not None:
        return _call_factory(factory, demo)

    configured = os.getenv(_FACTORY_ENV)
    if configured:
        return _call_factory(_load_factory(configured), demo)

    for candidate in _FACTORY_CANDIDATES:
        try:
            discovered = _load_factory(candidate)
        except AdapterUnavailableError:
            continue
        return _call_factory(discovered, demo)

    try:
        importlib.import_module("ledgerlens.parser")
        importlib.import_module("ledgerlens.agent")
    except ImportError as exc:
        raise AdapterUnavailableError(
            "No live LedgerLens adapter is installed. Configure "
            f"{_FACTORY_ENV}=module:callable or use explicit --demo mode."
        ) from exc
    return CoreDataAdapter()


def resolve_incident_backend(*, factory: AdapterFactory | None = None) -> Any | None:
    """Resolve an optional live Incident Commander backend factory lazily."""

    selected = factory
    if selected is None:
        configured = os.getenv(_INCIDENT_FACTORY_ENV)
        if not configured:
            return None
        selected = _load_factory(configured)
    return _call_factory(selected, False)


async def _adapter_call(adapter: Any, method: str, *args: Any) -> Any:
    function = getattr(adapter, method, None)
    if not callable(function):
        raise RuntimeError(f"The configured adapter does not implement '{method}'.")
    if inspect.iscoroutinefunction(function):
        value = await function(*args)
    else:
        value = await asyncio.to_thread(function, *args)
    if inspect.isawaitable(value):
        value = await value
    return redact_diagnostics(value)


def _normalise_status(
    status: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result = dict(status)
    result.setdefault("mode", getattr(status, "mode", "live"))
    result.setdefault("connected", False)
    result.setdefault("label", "DataHub status unknown")
    result.setdefault("endpoint", "not reported")
    result.setdefault("mcp", "not reported")
    result.setdefault("ingested_findings", len(findings))
    result.setdefault("checked_at", None)
    result.setdefault("diagnostic", "")
    redacted = redact_diagnostics(result)
    return dict(redacted) if isinstance(redacted, Mapping) else result


def _markdown_escape(value: object) -> str:
    text = _safe_text(value).replace("\\", "\\\\")
    for character in ("`", "*", "_", "{", "}", "[", "]", "<", ">", "#", "|"):
        text = text.replace(character, f"\\{character}")
    return text.replace("\r", " ").replace("\n", " ")


def render_markdown_report(
    payload: Mapping[str, Any],
    *,
    title: str = "LedgerLens remediation queue",
) -> str:
    """Render a safe, deterministic Markdown representation."""

    clean = redact_diagnostics(payload)
    if not isinstance(clean, dict):
        clean = {"result": clean}

    lines = [
        f"# {_markdown_escape(title)}",
        "",
        "> LedgerLens reports recorded metadata; it does not independently validate findings.",
        "",
    ]
    mode = clean.get("mode")
    if mode:
        lines.extend([f"**Mode:** `{_markdown_escape(mode)}`", ""])

    queue = clean.get("queue")
    if isinstance(queue, list):
        lines.extend(["## Remediation queue", ""])
        if not queue:
            lines.extend(["No actionable findings are available.", ""])
        for raw_item in queue:
            item = raw_item if isinstance(raw_item, dict) else {"result": raw_item}
            rank = item.get("rank", "?")
            title_text = item.get("title", item.get("finding_id", "Finding"))
            lines.append(f"### {rank}. {_markdown_escape(title_text)}")
            lines.append("")
            lines.append(f"- ID: `{_markdown_escape(item.get('finding_id', 'unknown'))}`")
            lines.append(f"- Priority: `{_markdown_escape(item.get('priority', 'unknown'))}`")
            owner = item.get("owner")
            if isinstance(owner, dict):
                owner = owner.get("name")
            lines.append(f"- Owner: {_markdown_escape(owner or 'Unassigned')}")
            gaps = item.get("gaps", [])
            if isinstance(gaps, list):
                lines.append(
                    "- Metadata gaps: "
                    + (", ".join(_markdown_escape(gap) for gap in gaps) or "None recorded")
                )
            lines.append(
                "- Required action: "
                f"{_markdown_escape(item.get('required_action', 'Not recorded'))}"
            )
            lines.append(
                f"- DataHub URN: `{_markdown_escape(item.get('datahub_urn', 'not recorded'))}`"
            )
            lines.append("")
    else:
        lines.extend(["```json", json.dumps(clean, indent=2, sort_keys=True), "```", ""])

    lines.extend(
        [
            "---",
            "",
            "`candidateOnly: true`  ",
            "`canClaimAGI: false`",
            "",
        ]
    )
    return "\n".join(lines)


def create_app(
    *,
    adapter: Any | None = None,
    demo_mode: bool | None = None,
    incident_backend: Any | None = None,
    incident_fixture_mode: bool | None = None,
    incident_autonomous_execution: bool | None = None,
) -> Any:
    """Create the optional FastAPI application."""

    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import HTMLResponse, JSONResponse, Response
        from fastapi.staticfiles import StaticFiles
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from starlette.templating import Jinja2Templates
    except ImportError as exc:
        raise RuntimeError("The web extra is required. Install LedgerLens with '[web]'.") from exc

    resolved_demo = (
        demo_mode
        if demo_mode is not None
        else os.getenv("LEDGERLENS_DEMO_MODE", "").lower() in {"1", "true", "yes"}
    )
    resolved_incident_fixture = (
        incident_fixture_mode if incident_fixture_mode is not None else resolved_demo
    )
    resolved_incident_autonomous = (
        incident_autonomous_execution
        if incident_autonomous_execution is not None
        else resolved_demo
    )
    if adapter is None:
        try:
            adapter = resolve_adapter(demo=resolved_demo)
        except AdapterUnavailableError as exc:
            adapter = UnavailableDataAdapter(str(exc))

    if incident_backend is None and not resolved_incident_fixture:
        try:
            incident_backend = resolve_incident_backend()
        except AdapterUnavailableError as exc:
            from ledgerlens.incident_dashboard import UnavailableIncidentBackend

            incident_backend = UnavailableIncidentBackend(str(exc))

    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
        enable_async=False,
    )
    templates = Jinja2Templates(env=environment)

    application = FastAPI(
        title="LedgerLens",
        description="Evidence-grounded failure-ledger triage through DataHub.",
        version="0.2.0",
    )
    application.state.adapter = adapter
    application.state.demo_mode = getattr(adapter, "mode", "") == "demo"
    application.mount("/static", StaticFiles(directory=str(_STATIC_ROOT)), name="static")

    from ledgerlens.incident_dashboard import create_incident_router

    application.include_router(
        create_incident_router(
            backend=incident_backend,
            fixture_mode=resolved_incident_fixture,
            prefix="/incident",
            autonomous_execution=resolved_incident_autonomous,
        )
    )

    def template_context(request: Request, **values: Any) -> dict[str, Any]:
        return {
            "request": request,
            "demo_mode": application.state.demo_mode,
            "candidate_only": True,
            "can_claim_agi": False,
            **values,
        }

    async def dashboard_data() -> dict[str, Any]:
        findings_raw = await _adapter_call(adapter, "list_findings")
        findings = findings_raw if isinstance(findings_raw, list) else []
        status_raw = await _adapter_call(adapter, "connection_status")
        status = (
            _normalise_status(status_raw, findings)
            if isinstance(status_raw, dict)
            else _normalise_status({}, findings)
        )
        triage_raw = await _adapter_call(adapter, "triage")
        triage = triage_raw if isinstance(triage_raw, dict) else {"queue": []}
        return {"status": status, "findings": findings, "triage": triage}

    @application.get("/", response_class=HTMLResponse, name="dashboard")
    async def dashboard(request: Request) -> Any:
        try:
            data = await dashboard_data()
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context=template_context(request, error=None, **data),
            )
        except Exception as exc:
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                status_code=503,
                context=template_context(
                    request,
                    error=_safe_text(exc),
                    status=_normalise_status({}, []),
                    findings=[],
                    triage={"queue": [], "summary": {}},
                ),
            )

    @application.get("/findings/{finding_id}", response_class=HTMLResponse, name="finding")
    async def finding_detail(request: Request, finding_id: str) -> Any:
        try:
            finding = await _adapter_call(adapter, "get_finding", finding_id)
            if not finding:
                return templates.TemplateResponse(
                    request=request,
                    name="error.html",
                    status_code=404,
                    context=template_context(
                        request,
                        status_code=404,
                        title="Finding not found",
                        message=f"No finding is available for ID '{finding_id}'.",
                    ),
                )
            chain_raw = await _adapter_call(adapter, "supersession", finding_id)
            chain = chain_raw if isinstance(chain_raw, dict) else {"chain": []}
            status_raw = await _adapter_call(adapter, "connection_status")
            status = status_raw if isinstance(status_raw, dict) else {}
            return templates.TemplateResponse(
                request=request,
                name="finding.html",
                context=template_context(
                    request,
                    finding=finding,
                    chain=chain,
                    status=_normalise_status(status, [finding]),
                ),
            )
        except Exception as exc:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                status_code=503,
                context=template_context(
                    request,
                    status_code=503,
                    title="Finding unavailable",
                    message=_safe_text(exc),
                ),
            )

    @application.get("/queue", response_class=HTMLResponse, name="queue")
    async def remediation_queue(request: Request) -> Any:
        try:
            triage_raw = await _adapter_call(adapter, "triage")
            triage = triage_raw if isinstance(triage_raw, dict) else {"queue": []}
            return templates.TemplateResponse(
                request=request,
                name="queue.html",
                context=template_context(request, triage=triage, error=None),
            )
        except Exception as exc:
            return templates.TemplateResponse(
                request=request,
                name="queue.html",
                status_code=503,
                context=template_context(
                    request,
                    triage={"queue": [], "summary": {}},
                    error=_safe_text(exc),
                ),
            )

    @application.get("/api/status", response_class=JSONResponse)
    async def api_status() -> Any:
        status = await _adapter_call(adapter, "connection_status")
        return JSONResponse(status)

    @application.get("/api/findings", response_class=JSONResponse)
    async def api_findings() -> Any:
        findings = await _adapter_call(adapter, "list_findings")
        return JSONResponse(findings)

    @application.get("/api/findings/{finding_id}", response_class=JSONResponse)
    async def api_finding(finding_id: str) -> Any:
        finding = await _adapter_call(adapter, "get_finding", finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        return JSONResponse(finding)

    @application.get("/api/supersession/{finding_id}", response_class=JSONResponse)
    async def api_supersession(finding_id: str) -> Any:
        try:
            chain = await _adapter_call(adapter, "supersession", finding_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Finding not found") from exc
        return JSONResponse(chain)

    @application.get("/api/triage", response_class=JSONResponse)
    async def api_triage() -> Any:
        triage = await _adapter_call(adapter, "triage")
        return JSONResponse(triage)

    @application.get("/reports/triage.json", response_class=Response)
    async def download_triage_json() -> Any:
        triage = await _adapter_call(adapter, "triage")
        body = json.dumps(triage, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-triage.json"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.get("/reports/triage.md", response_class=Response)
    async def download_triage_markdown() -> Any:
        triage = await _adapter_call(adapter, "triage")
        payload = triage if isinstance(triage, dict) else {"queue": []}
        return Response(
            content=render_markdown_report(payload),
            media_type="text/markdown",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-triage.md"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.get("/healthz", response_class=JSONResponse)
    async def health() -> Any:
        mode = getattr(adapter, "mode", "live")
        ok = mode == "demo"
        if not ok:
            try:
                status = await _adapter_call(adapter, "connection_status")
                ok = isinstance(status, Mapping) and status.get("connected") is True
            except Exception:
                ok = False
        return JSONResponse(
            {
                "ok": ok,
                "mode": mode,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            status_code=200 if ok else 503,
        )

    return application
