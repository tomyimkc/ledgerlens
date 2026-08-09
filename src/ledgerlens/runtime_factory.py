"""Factories for autonomous 020s planner/verifier roles and deterministic policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from ledgerlens.ai_roles import JsonIncidentPlanner, JsonPlanVerifier
from ledgerlens.config import Settings
from ledgerlens.incident_models import ActionRisk
from ledgerlens.model_runtime import (
    OpenAICompatibleJsonClient,
    RecordingJsonClient,
    close_clients,
)
from ledgerlens.tool_catalog import TOOL_SPECS, AgentToolCatalog, build_agent_tool_catalog
from ledgerlens.verification import (
    ActionAllowance,
    PolicyConfig,
    PolicyGate,
    VerifierPanel,
    VerifierPanelConfig,
)


@dataclass
class AIRoleBundle:
    """Owned planner, verifier panel, and clients for deterministic cleanup."""

    planner: JsonIncidentPlanner
    verifier_panel: VerifierPanel
    clients: tuple[OpenAICompatibleJsonClient, ...]

    def close(self) -> None:
        close_clients(self.clients)


def build_020s_ai_roles(
    settings: Settings,
    *,
    transports: Mapping[str, httpx.BaseTransport] | None = None,
    action_targets: Mapping[str, Sequence[str]] | None = None,
    tool_catalog: AgentToolCatalog | None = None,
    record_llm_io: bool = False,
    llm_io_records: list | None = None,
) -> AIRoleBundle:
    """Create one planner and a distinct-model verifier panel from the configured LLM.

    Pass ``action_targets`` (same map as ``build_policy_gate``) so the planner agent
    receives an explicit tool catalog and can flexibly choose among allowlisted tools
    instead of free-form inventing action types.

    Set ``record_llm_io=True`` (optionally with a shared ``llm_io_records`` list) to
    capture system/user prompts and JSON outputs for demo traces — no API keys stored.
    """

    if not settings.ai_verification_enabled:
        raise ValueError("LEDGERLENS_AI_VERIFICATION_ENABLED must be true")
    key = settings.require_llm_api_key()
    model_ids = settings.verifier_model_ids
    if settings.planner_model in model_ids:
        raise ValueError("planner model must not also be a verifier model")
    transport_map = dict(transports or {})
    records: list = llm_io_records if llm_io_records is not None else []
    planner_inner = OpenAICompatibleJsonClient(
        base_url=settings.llm_base_url,
        api_key=key,
        model=settings.planner_model,
        timeout_seconds=settings.llm_timeout_seconds,
        transport=transport_map.get(settings.planner_model),
    )
    planner_client: OpenAICompatibleJsonClient | RecordingJsonClient = (
        RecordingJsonClient(planner_inner, role="planner", records=records)
        if record_llm_io
        else planner_inner
    )
    verifier_inners = tuple(
        OpenAICompatibleJsonClient(
            base_url=settings.llm_base_url,
            api_key=key,
            model=model_id,
            timeout_seconds=settings.llm_timeout_seconds,
            transport=transport_map.get(model_id),
        )
        for model_id in model_ids
    )
    verifier_clients: tuple = (
        tuple(
            RecordingJsonClient(client, role=f"verifier:{client.model}", records=records)
            for client in verifier_inners
        )
        if record_llm_io
        else verifier_inners
    )
    catalog = tool_catalog
    if catalog is None and action_targets is not None:
        catalog = build_agent_tool_catalog(action_targets)
    planner = JsonIncidentPlanner(
        planner_client,
        planner_id=f"020s:{settings.planner_model}",
        family=settings.planner_model,
        tool_catalog=catalog,
    )
    verifiers = tuple(
        JsonPlanVerifier(
            client,
            verifier_id=f"020s:{getattr(client, 'model', model_id)}",
            family=str(getattr(client, "model", model_id)),
        )
        for model_id, client in zip(model_ids, verifier_clients, strict=True)
    )
    panel = VerifierPanel(
        verifiers,
        config=VerifierPanelConfig(
            quorum=settings.verifier_quorum,
            minimum_families=settings.verifier_quorum,
            confidence_threshold=settings.verifier_min_confidence,
            require_planner_independence=True,
            fail_on_verifier_error=True,
        ),
    )
    # Always close underlying HTTP clients (wrappers share the same close()).
    owned = (planner_inner, *verifier_inners)
    return AIRoleBundle(
        planner=planner,
        verifier_panel=panel,
        clients=owned,
    )


def build_policy_gate(
    targets: Mapping[str, Sequence[str]],
    *,
    maximum_risk: ActionRisk = ActionRisk.MEDIUM,
    minimum_plan_confidence: float = 0.8,
    minimum_verifier_confidence: float = 0.85,
    quorum: int = 2,
) -> PolicyGate:
    """Build exact target/parameter allowlists for the supported action fanout."""

    allowances = []
    for action_type, action_targets in sorted(targets.items()):
        base = TOOL_SPECS.get(action_type)
        if base is None:
            raise ValueError(
                f"unsupported policy action type: {action_type}. "
                "Register it with ledgerlens.tool_catalog.register_tool_spec first."
            )
        allowances.append(
            ActionAllowance(
                action_type=action_type,
                targets=frozenset(action_targets),
                allowed_parameter_keys=frozenset(base["allowed_parameter_keys"]),
                required_parameter_keys=frozenset(base["required_parameter_keys"]),
                maximum_risk=maximum_risk,
                automatable=True,
            )
        )
    return PolicyGate(
        PolicyConfig(
            version="incident-commander/v2",
            allowances=tuple(allowances),
            minimum_plan_confidence=minimum_plan_confidence,
            minimum_verifier_confidence=minimum_verifier_confidence,
            required_quorum=quorum,
            minimum_verifier_families=quorum,
            max_actions=10,
        )
    )
