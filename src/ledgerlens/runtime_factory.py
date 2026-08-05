"""Factories for autonomous 020s planner/verifier roles and deterministic policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from ledgerlens.ai_roles import JsonIncidentPlanner, JsonPlanVerifier
from ledgerlens.config import Settings
from ledgerlens.incident_models import ActionRisk
from ledgerlens.model_runtime import OpenAICompatibleJsonClient, close_clients
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
) -> AIRoleBundle:
    """Create one planner and a distinct-model verifier panel from the configured LLM."""

    if not settings.ai_verification_enabled:
        raise ValueError("LEDGERLENS_AI_VERIFICATION_ENABLED must be true")
    key = settings.require_llm_api_key()
    model_ids = settings.verifier_model_ids
    if settings.planner_model in model_ids:
        raise ValueError("planner model must not also be a verifier model")
    transport_map = dict(transports or {})
    planner_client = OpenAICompatibleJsonClient(
        base_url=settings.llm_base_url,
        api_key=key,
        model=settings.planner_model,
        timeout_seconds=settings.llm_timeout_seconds,
        transport=transport_map.get(settings.planner_model),
    )
    verifier_clients = tuple(
        OpenAICompatibleJsonClient(
            base_url=settings.llm_base_url,
            api_key=key,
            model=model_id,
            timeout_seconds=settings.llm_timeout_seconds,
            transport=transport_map.get(model_id),
        )
        for model_id in model_ids
    )
    planner = JsonIncidentPlanner(
        planner_client,
        planner_id=f"020s:{settings.planner_model}",
        family=settings.planner_model,
    )
    verifiers = tuple(
        JsonPlanVerifier(
            client,
            verifier_id=f"020s:{model_id}",
            family=model_id,
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
    return AIRoleBundle(
        planner=planner,
        verifier_panel=panel,
        clients=(planner_client, *verifier_clients),
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

    specs: dict[str, tuple[frozenset[str], frozenset[str]]] = {
        "github.issue.create": (
            frozenset({"owner", "repository", "title", "body", "labels", "assignees"}),
            frozenset({"owner", "repository", "title"}),
        ),
        "slack.message.post": (
            frozenset({"text", "channel", "blocks", "thread_ts"}),
            frozenset({"text"}),
        ),
        "pagerduty.event.trigger": (
            frozenset(
                {
                    "summary",
                    "source",
                    "severity",
                    "dedup_key",
                    "component",
                    "group",
                    "event_class",
                    "custom_details",
                }
            ),
            frozenset({"summary", "source", "severity"}),
        ),
        "jira.issue.create": (
            frozenset({"project_key", "summary", "description", "issue_type", "labels"}),
            frozenset({"project_key", "summary"}),
        ),
    }
    allowances = []
    for action_type, action_targets in sorted(targets.items()):
        if action_type not in specs:
            raise ValueError(f"unsupported policy action type: {action_type}")
        allowed_keys, required_keys = specs[action_type]
        allowances.append(
            ActionAllowance(
                action_type=action_type,
                targets=frozenset(action_targets),
                allowed_parameter_keys=allowed_keys,
                required_parameter_keys=required_keys,
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
