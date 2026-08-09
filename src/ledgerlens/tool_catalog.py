"""Agent-visible tool catalog: what the LLM may *propose*, not what may *run*.

LedgerLens separates three layers:

1. **Tool catalog (this module)** — descriptions + allowlisted targets the planner
   model sees. The agent chooses among these tools flexibly.
2. **Policy gate** — deterministic authorization of the exact sealed plan.
3. **Adapters** — code that actually performs I/O for a tool type.

Adapters and the orchestration *skeleton* stay in code (you cannot safely invent
a GitHub client from prose). Which tools to call, with which targets, is agent work
bounded by this catalog.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Shared parameter contracts — keep in sync with runtime_factory.build_policy_gate.
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "github.issue.create": {
        "title": "Create a GitHub issue",
        "description": (
            "Open an auditable work item in an allowlisted repository. "
            "Reversible collaboration record only."
        ),
        "allowed_parameter_keys": frozenset(
            {"owner", "repository", "title", "body", "labels", "assignees"}
        ),
        "required_parameter_keys": frozenset({"owner", "repository", "title"}),
        "reversible": True,
        "category": "collaboration",
    },
    "slack.message.post": {
        "title": "Post a Slack message",
        "description": (
            "Post a bounded status update to an allowlisted channel. "
            "Does not grant the model free broadcast rights."
        ),
        "allowed_parameter_keys": frozenset({"text", "channel", "blocks", "thread_ts"}),
        "required_parameter_keys": frozenset({"text"}),
        "reversible": True,
        "category": "collaboration",
    },
    "pagerduty.event.trigger": {
        "title": "Trigger or annotate a PagerDuty event",
        "description": (
            "Send an Events API v2 payload for an allowlisted routing key / incident path."
        ),
        "allowed_parameter_keys": frozenset(
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
        "required_parameter_keys": frozenset({"summary", "source", "severity"}),
        "reversible": True,
        "category": "collaboration",
    },
    "pagerduty.incident.note": {
        "title": "Append a PagerDuty incident note",
        "description": "Attach provenance context to an allowlisted active page.",
        "allowed_parameter_keys": frozenset({"note", "incident_id", "text"}),
        "required_parameter_keys": frozenset(),
        "reversible": True,
        "category": "collaboration",
    },
    "jira.issue.create": {
        "title": "Create a Jira issue",
        "description": "Create a recovery/follow-up task in an allowlisted project.",
        "allowed_parameter_keys": frozenset(
            {"project_key", "summary", "description", "issue_type", "labels"}
        ),
        "required_parameter_keys": frozenset({"project_key", "summary"}),
        "reversible": True,
        "category": "collaboration",
    },
    "datahub.incident.writeback": {
        "title": "Write DataHub incident receipt",
        "description": (
            "Allowlisted MCP save_document-style write-back of the incident command receipt."
        ),
        "allowed_parameter_keys": frozenset({"entity", "document_type", "title", "content"}),
        "required_parameter_keys": frozenset(),
        "reversible": True,
        "category": "catalog",
    },
}


class AgentToolSpec(BaseModel):
    """One tool the agent may select when drafting a plan."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    action_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    targets: tuple[str, ...] = Field(default_factory=tuple)
    allowed_parameter_keys: tuple[str, ...] = Field(default_factory=tuple)
    required_parameter_keys: tuple[str, ...] = Field(default_factory=tuple)
    reversible: bool = True
    category: str = "collaboration"

    def to_agent_dict(self) -> dict[str, Any]:
        """JSON-serializable view embedded in the planner context."""

        return {
            "action_type": self.action_type,
            "title": self.title,
            "description": self.description,
            "allowed_targets": list(self.targets),
            "allowed_parameter_keys": list(self.allowed_parameter_keys),
            "required_parameter_keys": list(self.required_parameter_keys),
            "reversible": self.reversible,
            "category": self.category,
        }


class AgentToolCatalog(BaseModel):
    """Immutable set of tools the planner agent may choose from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: tuple[AgentToolSpec, ...] = Field(default_factory=tuple)
    version: str = "agent-tool-catalog/v1"

    def action_types(self) -> frozenset[str]:
        return frozenset(tool.action_type for tool in self.tools)

    def get(self, action_type: str) -> AgentToolSpec | None:
        for tool in self.tools:
            if tool.action_type == action_type:
                return tool
        return None

    def to_agent_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "note": (
                "Select only from these tools and targets. Do not invent action types. "
                "Authorization is enforced later by deterministic policy; this catalog "
                "is the agent-visible tool belt, not a grant of authority."
            ),
            "tools": [tool.to_agent_dict() for tool in self.tools],
        }

    def __bool__(self) -> bool:
        return bool(self.tools)


def build_agent_tool_catalog(
    targets: Mapping[str, Sequence[str]],
    *,
    include_unknown_types: bool = False,
) -> AgentToolCatalog:
    """Build an agent-visible catalog from the same target map used for policy.

    ``targets`` maps ``action_type`` → allowed destination strings (repos, channels, …).
    Only types present in ``TOOL_SPECS`` are included unless ``include_unknown_types``.
    """

    tools: list[AgentToolSpec] = []
    for action_type, action_targets in sorted(targets.items()):
        base = TOOL_SPECS.get(action_type)
        if base is None:
            if not include_unknown_types:
                continue
            base = {
                "title": action_type,
                "description": f"Operator-registered tool {action_type}.",
                "allowed_parameter_keys": frozenset(),
                "required_parameter_keys": frozenset(),
                "reversible": True,
                "category": "custom",
            }
        target_tuple = tuple(str(t) for t in action_targets)
        tools.append(
            AgentToolSpec(
                action_type=action_type,
                title=str(base["title"]),
                description=str(base["description"]),
                targets=target_tuple,
                allowed_parameter_keys=tuple(sorted(base["allowed_parameter_keys"])),
                required_parameter_keys=tuple(sorted(base["required_parameter_keys"])),
                reversible=bool(base.get("reversible", True)),
                category=str(base.get("category", "collaboration")),
            )
        )
    return AgentToolCatalog(tools=tuple(tools))


def register_tool_spec(
    action_type: str,
    *,
    title: str,
    description: str,
    allowed_parameter_keys: Sequence[str] = (),
    required_parameter_keys: Sequence[str] = (),
    reversible: bool = True,
    category: str = "custom",
) -> None:
    """Register a new tool type for agent catalogs and policy builders.

    Call this when integrating a custom adapter so the AI planner can see the tool.
    Policy still must allowlist concrete targets before anything runs.
    """

    if not action_type.strip():
        raise ValueError("action_type must be non-empty")
    TOOL_SPECS[action_type.strip()] = {
        "title": title,
        "description": description,
        "allowed_parameter_keys": frozenset(allowed_parameter_keys),
        "required_parameter_keys": frozenset(required_parameter_keys),
        "reversible": reversible,
        "category": category,
    }


__all__ = [
    "TOOL_SPECS",
    "AgentToolCatalog",
    "AgentToolSpec",
    "build_agent_tool_catalog",
    "register_tool_spec",
]
