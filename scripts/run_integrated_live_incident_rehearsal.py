#!/usr/bin/env python3
"""One supervised DataHub read -> sealed provider action -> write-back -> read-back run.

This is deliberately separate from the public fixture and from the historical E-16/E-07
receipts. It may execute real provider actions and one DataHub ``save_document`` mutation,
so it fails closed unless both live-confirmation flags are present.

The model drafts and critiques the plan. Deterministic policy remains the authorization
authority, and the provider executor receives the frozen, fingerprint-bound plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from run_live_incident_rehearsal import (  # noqa: E402
    DEFAULT_INCIDENT,
    DEFAULT_JIRA_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT,
    ProviderCredentials,
    _automation_policy,
    build_action_executor,
    policy_targets,
)

from ledgerlens.actions import ActionAuthorizer  # noqa: E402
from ledgerlens.catalog_runtime import (  # noqa: E402
    incident_from_catalog,
    load_incident_catalog,
)
from ledgerlens.config import LlmProvider, Settings  # noqa: E402
from ledgerlens.datahub_context import DataHubMCPContextProvider  # noqa: E402
from ledgerlens.datahub_writeback import (  # noqa: E402
    DataHubWritebackService,
    MCPStateSnapshotReader,
)
from ledgerlens.datahub_writeback import (  # noqa: E402
    DeterministicPolicyGate as DataHubWritebackPolicy,
)
from ledgerlens.incident_integration import (  # noqa: E402
    DataHubIncidentWriteback,
    OrchestratorIncidentBackend,
)
from ledgerlens.incident_models import (  # noqa: E402
    ActionReceiptStatus,
    EvidenceKind,
    EvidencePointer,
    Incident,
    IncidentContext,
    IncidentFact,
)
from ledgerlens.mcp_client import DataHubMCPClient, StdioMCPTransport  # noqa: E402
from ledgerlens.mcp_mutations import MCPMutationClient, redact_text  # noqa: E402
from ledgerlens.orchestrator import OrchestrationState  # noqa: E402
from ledgerlens.runtime_factory import build_ai_roles, build_policy_gate  # noqa: E402
from ledgerlens.tool_catalog import DATAHUB_INCIDENT_EVIDENCE_CONTRACTS  # noqa: E402

DEFAULT_OUTPUT = Path(
    "benchmarks/incident_commander/integrated-live-incident-rehearsal-receipt.json"
)
DEFAULT_PREFLIGHT_OUTPUT = Path("artifacts/integrated-live-rehearsal/preflight.json")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", default=DEFAULT_INCIDENT)
    parser.add_argument(
        "--root-urn",
        default="",
        help="Live DataHub root entity. Defaults to the catalog incident root URN.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Read-only prerequisite and live DataHub context check; no model or provider call.",
    )
    parser.add_argument(
        "--confirm-live-provider-actions",
        action="store_true",
        help="Required acknowledgment for GitHub/Slack/PagerDuty/Jira actions.",
    )
    parser.add_argument(
        "--confirm-live-datahub-writeback",
        action="store_true",
        help="Required acknowledgment for one policy-gated DataHub save_document call.",
    )
    parser.add_argument("--readback-timeout-seconds", type=float, default=60.0)
    return parser.parse_args()


def _mcp_env(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    env["DATAHUB_GMS_URL"] = settings.datahub_gms_url
    token = settings.datahub_token_value()
    if token:
        env["DATAHUB_GMS_TOKEN"] = token
        env["DATAHUB_TOKEN"] = token
    return env


def _role_settings() -> Settings:
    """Resolve native model providers without sending one vendor's key to another."""

    explicit_default = os.getenv("LEDGERLENS_LLM_PROVIDER")
    if explicit_default:
        default_provider = explicit_default
    elif os.getenv("OPENAI_API_KEY"):
        default_provider = LlmProvider.OPENAI.value
    elif os.getenv("ANTHROPIC_API_KEY"):
        default_provider = LlmProvider.ANTHROPIC.value
    else:
        default_provider = LlmProvider.OPENAI.value

    planner_provider = os.getenv("LEDGERLENS_PLANNER_PROVIDER", default_provider)
    verifier_provider = os.getenv("LEDGERLENS_VERIFIER_PROVIDER", default_provider)
    planner_model = os.getenv("LEDGERLENS_PLANNER_MODEL")
    verifier_models = os.getenv("LEDGERLENS_VERIFIER_MODELS")
    if planner_provider == LlmProvider.ANTHROPIC.value and not planner_model:
        raise ValueError(
            "LEDGERLENS_PLANNER_MODEL is required when the planner provider is Anthropic"
        )
    if verifier_provider == LlmProvider.ANTHROPIC.value and not verifier_models:
        raise ValueError(
            "LEDGERLENS_VERIFIER_MODELS is required when the verifier provider is Anthropic"
        )

    settings = Settings.model_validate(
        {
            "ai_verification_enabled": True,
            "llm_provider": default_provider,
            "planner_provider": planner_provider,
            "verifier_provider": verifier_provider,
            "llm_base_url": os.getenv(
                "LEDGERLENS_LLM_BASE_URL",
                "https://api.openai.com/v1",
            ),
            "planner_model": planner_model or "gpt-4.1",
            "verifier_models": verifier_models or "gpt-4o-mini,gpt-4o",
            "verifier_quorum": 2,
            "verifier_min_confidence": 0.85,
            "llm_timeout_seconds": 60,
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "llm_api_key": os.getenv("LEDGERLENS_LLM_API_KEY"),
        }
    )
    settings.api_key_for_provider(settings.resolved_planner_provider())
    settings.api_key_for_provider(settings.resolved_verifier_provider())
    return settings


def _readiness(
    *,
    settings: Settings,
    require_provider_credentials: bool,
) -> dict[str, Any]:
    credential_names = {
        "llm": bool(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("LEDGERLENS_LLM_API_KEY")
        ),
        "actionAuthorizationSecret": bool(
            os.getenv("LEDGERLENS_ACTION_AUTHORIZATION_SECRET")
            and len(os.environ["LEDGERLENS_ACTION_AUTHORIZATION_SECRET"].encode("utf-8")) >= 32
        ),
        "dataHubGms": bool(settings.datahub_gms_url),
        "dataHubToken": settings.datahub_token_value() is not None,
        "mcpCommand": bool(
            settings.mcp_command_argv and shutil.which(settings.mcp_command_argv[0])
        ),
    }
    credentials, missing_provider = ProviderCredentials.from_env()
    credential_names["providers"] = credentials is not None
    model_error: str | None = None
    try:
        _role_settings()
        credential_names["modelRuntime"] = True
    except (TypeError, ValueError) as exc:
        credential_names["modelRuntime"] = False
        model_error = _sanitized_error(exc)
    required = ["dataHubGms", "mcpCommand"]
    if require_provider_credentials:
        required.extend(
            (
                "llm",
                "modelRuntime",
                "actionAuthorizationSecret",
                "dataHubToken",
                "providers",
            )
        )
    missing = [name for name in required if not credential_names[name]]
    return {
        "ready": not missing,
        "checks": credential_names,
        "missingChecks": missing,
        "missingProviderCredentialNames": missing_provider,
        "modelRuntimeError": model_error,
        "secretsSerialized": False,
    }


def _source_fact(
    fact_id: str,
    statement: str,
    reference: str,
) -> IncidentFact:
    return IncidentFact(
        fact_id=fact_id,
        statement=statement,
        evidence=(
            EvidencePointer(
                reference=reference,
                kind=EvidenceKind.SOURCE_RECORD,
            ),
        ),
    )


def _live_context(
    client: DataHubMCPClient,
    incident: Incident,
    *,
    jira_project: str,
    jira_issue_type: str,
) -> IncidentContext:
    context = DataHubMCPContextProvider(client)(incident)
    additional = (
        _source_fact(
            "incident-id",
            f"The source assertion identifies incident {incident.incident_id}.",
            f"incident:{incident.incident_id}",
        ),
        _source_fact(
            "incident-severity",
            f"The source assertion records severity {incident.severity.value}.",
            f"incident:{incident.incident_id}#severity",
        ),
    )
    facts_by_id = {fact.fact_id: fact for fact in context.facts}
    for fact in additional:
        facts_by_id.setdefault(fact.fact_id, fact)
    facts = tuple(facts_by_id.values())
    fact_ids = [fact.fact_id for fact in facts]
    automation = _automation_policy(
        incident,
        jira_project=jira_project,
        jira_issue_type=jira_issue_type,
    )
    for action in automation["requiredActions"]:
        action["evidence_fact_ids"] = fact_ids
    metadata = dict(context.metadata)
    metadata["automationPolicy"] = automation
    metadata["claimBoundary"] = {
        "candidateOnly": True,
        "canClaimAGI": False,
        "causality": False,
        "recovery": False,
    }
    return context.model_copy(update={"facts": facts, "metadata": metadata})


def _context_digest(context: IncidentContext) -> str:
    payload = context.model_dump(mode="json", by_alias=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _writeback_receipt(result: Any) -> Mapping[str, Any] | None:
    writeback = getattr(result, "writeback", None)
    details = getattr(writeback, "details", None)
    if isinstance(details, Mapping):
        receipt = details.get("writebackReceipt")
        if isinstance(receipt, Mapping):
            return receipt
    return None


def _result_urn(receipt: Mapping[str, Any] | None) -> str | None:
    if not isinstance(receipt, Mapping):
        return None
    result = receipt.get("result")
    if not isinstance(result, Mapping):
        return None
    for key in ("urn", "documentUrn", "document_urn"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _sanitized_error(exc: Exception) -> str:
    return redact_text(f"{type(exc).__name__}: {exc}")


def _read_back(
    client: DataHubMCPClient,
    urn: str | None,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    if not urn:
        return {
            "retrieved": False,
            "urn": None,
            "attempts": 0,
            "limitation": "write-back result did not expose a document URN",
        }
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    attempts = 0
    while True:
        attempts += 1
        entities = client.get_entities([urn])
        exact = next(
            (
                entity
                for entity in entities
                if isinstance(entity, Mapping) and entity.get("urn") == urn
            ),
            None,
        )
        if exact is not None:
            digest = (
                "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        exact,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
            )
            return {
                "retrieved": True,
                "urn": urn,
                "attempts": attempts,
                "entityDigest": digest,
                "via": "official-datahub-mcp:get_entities",
            }
        if time.monotonic() >= deadline:
            return {
                "retrieved": False,
                "urn": urn,
                "attempts": attempts,
                "limitation": "document was not returned before the bounded read-back timeout",
            }
        time.sleep(2)


def _preflight_receipt(
    *,
    readiness: Mapping[str, Any],
    incident: Incident,
    root_urn: str,
    context: IncidentContext | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "ledgerlens.integrated-live-preflight.v1",
        "kind": "integrated-live-rehearsal-preflight",
        "observedAt": datetime.now(UTC).isoformat(),
        "ready": bool(readiness.get("ready")) and context is not None and error is None,
        "networkUsed": context is not None or error is not None,
        "externalMutations": False,
        "providerToolsExecuted": False,
        "incidentId": incident.incident_id,
        "rootUrn": root_urn,
        "context": (
            {
                "source": context.metadata.get("source"),
                "factIds": sorted(context.fact_ids),
                "digest": _context_digest(context),
            }
            if context is not None
            else None
        ),
        "readiness": dict(readiness),
        "error": error,
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def main() -> int:
    args = _arguments()
    settings = Settings()
    readiness = _readiness(
        settings=settings,
        require_provider_credentials=not args.preflight,
    )
    catalog = load_incident_catalog()
    base_incident = incident_from_catalog(catalog, args.incident_id)
    root_urn = args.root_urn or base_incident.affected_entities[0]
    incident = base_incident.model_copy(update={"affected_entities": (root_urn,)})

    command = settings.mcp_command_argv
    if command is None or not shutil.which(command[0]):
        error = "official DataHub MCP command is unavailable"
        if args.preflight:
            receipt = _preflight_receipt(
                readiness=readiness,
                incident=incident,
                root_urn=root_urn,
                context=None,
                error=error,
            )
            args.output = args.output if args.output != DEFAULT_OUTPUT else DEFAULT_PREFLIGHT_OUTPUT
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(error, file=sys.stderr)
        return 2

    if not args.preflight:
        if not args.confirm_live_provider_actions:
            print("--confirm-live-provider-actions is required", file=sys.stderr)
            return 2
        if not args.confirm_live_datahub_writeback:
            print("--confirm-live-datahub-writeback is required", file=sys.stderr)
            return 2
        if not readiness["ready"]:
            print(
                "live prerequisites are missing: " + ", ".join(readiness["missingChecks"]),
                file=sys.stderr,
            )
            return 2
        if args.output.exists() and not args.force:
            print(f"refusing to overwrite existing receipt: {args.output}", file=sys.stderr)
            return 2

    jira_project = os.getenv("LEDGERLENS_JIRA_PROJECT_KEY", DEFAULT_JIRA_PROJECT)
    jira_issue_type = os.getenv(
        "LEDGERLENS_JIRA_ISSUE_TYPE",
        DEFAULT_JIRA_ISSUE_TYPE,
    )
    transport = StdioMCPTransport(
        command,
        timeout=settings.mcp_timeout_seconds,
        env=_mcp_env(settings),
        allow_mutations=not args.preflight,
    )
    read_client = DataHubMCPClient(transport)
    context: IncidentContext | None = None
    try:
        context = _live_context(
            read_client,
            incident,
            jira_project=jira_project,
            jira_issue_type=jira_issue_type,
        )
        if args.preflight:
            receipt = _preflight_receipt(
                readiness=readiness,
                incident=incident,
                root_urn=root_urn,
                context=context,
                error=None,
            )
            output = args.output if args.output != DEFAULT_OUTPUT else DEFAULT_PREFLIGHT_OUTPUT
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            print(
                json.dumps(
                    {
                        "output": str(output),
                        "ready": receipt["ready"],
                        "externalMutations": False,
                        "candidateOnly": True,
                        "canClaimAGI": False,
                    },
                    sort_keys=True,
                )
            )
            return 0 if receipt["ready"] else 2

        live_context = context
        auth_secret = os.environ["LEDGERLENS_ACTION_AUTHORIZATION_SECRET"]
        credentials, missing = ProviderCredentials.from_env()
        if credentials is None:
            raise RuntimeError("provider credential preflight changed: " + ", ".join(missing))
        targets = policy_targets(jira_project)
        evidence_contracts = {
            action_type: DATAHUB_INCIDENT_EVIDENCE_CONTRACTS[action_type] for action_type in targets
        }
        role_settings = _role_settings()
        action_authorizer = ActionAuthorizer(
            auth_secret.encode("utf-8"),
            issuer="ledgerlens-integrated-live-rehearsal",
        )
        executor = build_action_executor(
            credentials,
            action_authorizer,
            subject="policy-sealed-data-incident-commander",
        )
        roles = build_ai_roles(
            role_settings,
            action_targets=targets,
            required_evidence_fact_ids=evidence_contracts,
        )
        writeback_policy = DataHubWritebackPolicy(
            enabled=True,
            allowlisted_tools=("save_document",),
            allowed_urn_prefixes=(
                "urn:li:dataset:",
                "urn:li:document:",
                "urn:li:dashboard:",
                "urn:li:dataProduct:",
                "urn:li:mlModel:",
            ),
            allow_document_creation=True,
            policy_version="ledgerlens-integrated-live-writeback/v1",
        )
        mutation_client = MCPMutationClient(
            transport,
            enabled=True,
            allowlisted_tools=("save_document",),
            supported_tools=("save_document",),
            authorization_verifier=writeback_policy,
        )
        writeback_service = DataHubWritebackService(
            mutation_client,
            writeback_policy,
            snapshot_reader=MCPStateSnapshotReader(read_client),
        )
        writeback = DataHubIncidentWriteback(
            writeback_service,
            actor="ledgerlens-policy-sealed-incident-commander",
        )
        executed_attempted = False
        result = None
        try:
            backend = OrchestratorIncidentBackend(
                incident_resolver=lambda payload: incident,
                context_provider=lambda value: live_context,
                planner=roles.planner,
                verifier_panel=roles.verifier_panel,
                policy_gate=build_policy_gate(
                    targets,
                    required_evidence_fact_ids=evidence_contracts,
                    minimum_plan_confidence=0.8,
                    minimum_verifier_confidence=0.85,
                    quorum=2,
                ),
                executor=executor,
                writeback=writeback,
            )
            state = backend.trigger({"incident_id": incident.incident_id})
            prepared = backend.prepared_run
            if prepared is None:
                raise RuntimeError("backend did not retain the prepared run")
            plan_hash = state.get("planner", {}).get("plan_hash")
            if not prepared.authorization.authorized:
                raise RuntimeError(
                    "deterministic policy denied the prepared plan: "
                    + ", ".join(prepared.authorization.reason_codes)
                )
            executed_attempted = True
            state = backend.execute({"incident_id": incident.incident_id, "plan_hash": plan_hash})
            result = backend.orchestration_result
            if result is None:
                raise RuntimeError("orchestration completed without a result")
            writeback_receipt = _writeback_receipt(result)
            readback = _read_back(
                read_client,
                _result_urn(writeback_receipt),
                timeout_seconds=args.readback_timeout_seconds,
            )
            writeback_succeeded = bool(result.writeback is not None and result.writeback.succeeded)
            provider_actions_succeeded = bool(
                result.state is OrchestrationState.WRITTEN_BACK
                and len(result.receipts) == len(prepared.plan.actions)
                and all(item.status is ActionReceiptStatus.SUCCEEDED for item in result.receipts)
            )
            integrated = bool(
                provider_actions_succeeded and writeback_succeeded and readback["retrieved"]
            )
            receipt = {
                "schemaVersion": "ledgerlens.integrated-live-incident-rehearsal.v1",
                "kind": "integrated-live-incident-rehearsal",
                "status": (
                    "executed-writeback-readback" if integrated else "executed-readback-incomplete"
                ),
                "observedAt": datetime.now(UTC).isoformat(),
                "networkUsed": True,
                "externalMutations": True,
                "providerToolsExecuted": bool(result.receipts),
                "providerActionsSucceeded": provider_actions_succeeded,
                "integratedSameProcessRun": integrated,
                "models": {
                    "planner": role_settings.planner_model,
                    "verifiers": list(role_settings.verifier_model_ids),
                    "providerFamilyIndependenceClaimed": False,
                },
                "incident": prepared.incident.model_dump(
                    mode="json",
                    by_alias=True,
                ),
                "dataHubRead": {
                    "source": prepared.context.metadata.get("source"),
                    "rootUrn": root_urn,
                    "factIds": sorted(prepared.context.fact_ids),
                    "contextDigest": _context_digest(prepared.context),
                },
                "plan": prepared.plan.model_dump(mode="json", by_alias=True),
                "verification": prepared.verification.model_dump(
                    mode="json",
                    by_alias=True,
                ),
                "authorization": prepared.authorization.model_dump(
                    mode="json",
                    by_alias=True,
                ),
                "orchestrationResult": result.model_dump(
                    mode="json",
                    by_alias=True,
                ),
                "dataHubWriteback": writeback_receipt,
                "dataHubReadback": readback,
                "dashboardState": state,
                "limitations": [
                    "Each provider receipt proves one bounded rehearsal action only.",
                    "The combined receipt does not prove incident causality, user impact, "
                    "recovery, sustained operation, provider reliability, or production readiness.",
                    "Configured model variants are advisory; provider-family independence "
                    "is not claimed.",
                    "The DataHub instance and provider destinations are owner-controlled "
                    "rehearsal surfaces.",
                ],
                "candidateOnly": True,
                "canClaimAGI": False,
            }
        except Exception as exc:
            provider_execution_state = "attempted-outcome-unknown" if executed_attempted else "held"
            receipt = {
                "schemaVersion": "ledgerlens.integrated-live-incident-rehearsal.v1",
                "kind": "integrated-live-incident-rehearsal",
                "status": "failed-closed",
                "observedAt": datetime.now(UTC).isoformat(),
                "networkUsed": True,
                "externalMutations": None if executed_attempted else False,
                "externalMutationsMayHaveOccurred": executed_attempted,
                "providerToolsExecuted": None if executed_attempted else False,
                "providerExecutionAttempted": executed_attempted,
                "providerExecutionState": provider_execution_state,
                "providerActionsSucceeded": False,
                "integratedSameProcessRun": False,
                "incidentId": incident.incident_id,
                "rootUrn": root_urn,
                "error": _sanitized_error(exc),
                "limitations": [
                    "The combined run did not complete all required phases.",
                    "If execution was attempted, inspect owner-controlled provider surfaces "
                    "for partial rehearsal artifacts.",
                ],
                "candidateOnly": True,
                "canClaimAGI": False,
            }
        finally:
            roles.close()

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                receipt,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "status": receipt["status"],
                    "integratedSameProcessRun": receipt["integratedSameProcessRun"],
                    "externalMutations": receipt["externalMutations"],
                    "candidateOnly": True,
                    "canClaimAGI": False,
                },
                sort_keys=True,
            )
        )
        return 0 if receipt["integratedSameProcessRun"] else 3
    except Exception as exc:
        if args.preflight:
            receipt = _preflight_receipt(
                readiness=readiness,
                incident=incident,
                root_urn=root_urn,
                context=context,
                error=_sanitized_error(exc),
            )
            output = args.output if args.output != DEFAULT_OUTPUT else DEFAULT_PREFLIGHT_OUTPUT
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(_sanitized_error(exc), file=sys.stderr)
        return 2
    finally:
        transport.close()


if __name__ == "__main__":
    raise SystemExit(main())
