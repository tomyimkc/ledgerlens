"""Mountable Incident Commander dashboard for LedgerLens.

The module is intentionally self-contained: applications can include the router
without changing :mod:`ledgerlens.web`, and deterministic replay mode requires no
network access. Live mode never substitutes fixture records for unavailable
integrations; callers must inject an incident backend that reports real state.
"""

import asyncio
import copy
import hashlib
import inspect
import json
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

JsonObject = dict[str, Any]

_PACKAGE_ROOT = Path(__file__).resolve().parent
_TEMPLATE_ROOT = _PACKAGE_ROOT / "templates"
_STATIC_ROOT = _PACKAGE_ROOT / "static"
_FIXTURE_TIME = datetime(2026, 7, 31, 3, 14, 0, tzinfo=UTC)
_SECRET_KEY = re.compile(
    r"(authorization|cookie|password|secret|token|api[_-]?key|credential)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_SECRET = re.compile(r"(?i)\b(token|password|secret|api[_-]?key)=([^&\s]+)")
_SAFE_PUBLIC_KEYS = frozenset({"authorization_boundary"})

CLAIM_BOUNDARY: JsonObject = {
    "candidateOnly": True,
    "canClaimAGI": False,
    "label": "Operational metadata, planner proposals, and receipts are not proof of causality.",
    "detail": (
        "LedgerLens separates source assertions, DataHub metadata, deterministic policy "
        "decisions, AI advisory output, executed action receipts, and unknowns."
    ),
    # Machine-readable epistemic humility: refusals encoded as fields, not prose.
    "asserts": {
        "causality": False,
        "userImpact": False,
        "recovery": False,
        "validation": False,
    },
}

ALLOWED_ACTIONS = frozenset(
    {
        "github.issue.create",
        "slack.message.post",
        "pagerduty.incident.note",
        "jira.issue.create",
        "datahub.incident.writeback",
    }
)


class IncidentBackend(Protocol):
    """Runtime contract used by the mountable dashboard."""

    mode: str

    def snapshot(self) -> Mapping[str, Any]:
        """Return current incident state without inventing unavailable fields."""

    def trigger(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Ingest or replay an incident trigger."""

    def execute(self, authorization: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute the authorized action fanout and return current state."""


class IncidentDashboardError(RuntimeError):
    """Base dashboard error with an HTTP-friendly status code."""

    status_code = 503


class AuthorizationDenied(IncidentDashboardError):
    """Raised when the deterministic authorization gate is closed."""

    status_code = 409

    def __init__(self, message: str, authorization: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.authorization = dict(authorization)


class LiveBackendUnavailable(IncidentDashboardError):
    """Raised when live mode has no injected runtime."""


def _safe_text(value: object) -> str:
    text = _BEARER.sub(r"\1[REDACTED]", str(value))
    return _ASSIGNMENT_SECRET.sub(r"\1=[REDACTED]", text)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _plain(model_dump(mode="json"))
    return _safe_text(value)


def _redact(value: Any) -> Any:
    plain = _plain(value)
    if isinstance(plain, dict):
        return {
            key: (
                "[REDACTED]"
                if _SECRET_KEY.search(key) and key not in _SAFE_PUBLIC_KEYS
                else _redact(item)
            )
            for key, item in plain.items()
        }
    if isinstance(plain, list):
        return [_redact(item) for item in plain]
    if isinstance(plain, str):
        return _safe_text(plain)
    return plain


def _isoformat(clock: Callable[[], datetime]) -> str:
    observed = clock()
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fixture_clock() -> datetime:
    return _FIXTURE_TIME


def _canonical_plan_payload(state: Mapping[str, Any]) -> JsonObject | None:
    incident = state.get("incident")
    planner = state.get("planner")
    if not isinstance(incident, Mapping) or not isinstance(planner, Mapping):
        return None
    incident_id = incident.get("id")
    steps = planner.get("steps")
    if not isinstance(incident_id, str) or not isinstance(steps, list):
        return None
    return {
        "incident_id": incident_id,
        "objective": planner.get("objective"),
        "scope": planner.get("scope"),
        "steps": steps,
    }


def plan_fingerprint(state: Mapping[str, Any]) -> str | None:
    """Return a stable fingerprint for the exact proposed plan."""

    payload = _canonical_plan_payload(state)
    if payload is None:
        return None
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _fixture_state() -> JsonObject:
    state: JsonObject = {
        "schemaVersion": "1.0",
        "mode": "fixture",
        "availability": "ready",
        "observed_at": "2026-07-31T03:14:00Z",
        "fixture": {
            "label": "FIXTURE / REPLAY",
            "replay_id": "fixture-inc-2042-v1",
            "network_used": False,
            "external_mutations": False,
            "note": (
                "Deterministic contest replay. No DataHub request or external mutation occurred. "
                "Provider receipts use fixture:// identifiers and do not describe live state."
            ),
        },
        "capabilities": {
            "trigger": True,
            "authorize": True,
            "execute": True,
            "replay": True,
        },
        "incident": {
            "id": "INC-2042",
            "severity": "SEV-1",
            "status": "awaiting_authorization",
            "title": "Revenue dashboard freshness breach after payments model deploy",
            "service": "payments-analytics",
            "environment": "production-metadata-replay",
            "detected_at": "2026-07-31T03:06:18Z",
            "elapsed": "00:07:42",
            "trigger": {
                "source": "DataHub assertion fixture",
                "signal": "freshness_slo",
                "summary": "payments_daily exceeded its recorded 15 minute freshness SLO.",
                "observed": "23 minutes",
                "threshold": "15 minutes",
                "classification": "source assertion",
            },
            "commander": "On-call data platform",
        },
        "context": {
            "status": "grounded",
            "source": "DataHub fixture graph",
            "entity": {
                "urn": (
                    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.payments_daily,PROD)"
                ),
                "name": "analytics.payments_daily",
                "platform": "Snowflake",
                "domain": "Revenue Intelligence",
                "owner": "Data Platform",
                "tier": "Tier 1",
                "last_observed": "2026-07-31T03:06:18Z",
            },
            "blast_radius": {
                "authorization_boundary": "bounded",
                "summary": "8 downstream assets recorded; 3 are Tier 1.",
                "asset_count": 8,
                "critical_count": 3,
                "people_on_call": 4,
                "confidence": "metadata-derived, not causal proof",
                "assets": [
                    {
                        "name": "finance.revenue_executive",
                        "type": "Dashboard",
                        "criticality": "Tier 1",
                        "relationship": "1 hop downstream",
                    },
                    {
                        "name": "risk.payment_anomaly_features",
                        "type": "Feature table",
                        "criticality": "Tier 1",
                        "relationship": "2 hops downstream",
                    },
                    {
                        "name": "growth.checkout_health",
                        "type": "Dashboard",
                        "criticality": "Tier 1",
                        "relationship": "2 hops downstream",
                    },
                    {
                        "name": "finance.daily_close_packet",
                        "type": "Report",
                        "criticality": "Tier 2",
                        "relationship": "3 hops downstream",
                    },
                ],
                "unknowns": [
                    "Query logs outside the fixture window are not represented.",
                    "Lineage proximity does not establish user-visible impact.",
                ],
            },
            "evidence": [
                {
                    "label": "Freshness assertion observation",
                    "kind": "DataHub metadata",
                    "receipt": "fixture://datahub/assertions/payments-daily/obs-8831",
                },
                {
                    "label": "Recorded downstream lineage",
                    "kind": "DataHub metadata",
                    "receipt": "fixture://datahub/lineage/payments-daily/snapshot-77",
                },
                {
                    "label": "Deploy marker",
                    "kind": "source assertion",
                    "receipt": "fixture://github/deployments/payments-model/sha-a81f0e",
                },
            ],
        },
        "planner": {
            "status": "ready",
            "generated_by": "Deterministic incident policy v1",
            "objective": "Coordinate bounded response work without asserting unproven causality.",
            "scope": "Collaboration fanout and metadata write-back only",
            "risk": "No production rollback or incident resolution is authorized by this plan.",
            "steps": [
                {
                    "order": 1,
                    "action": "github.issue.create",
                    "title": "Open an auditable incident work item",
                    "target": "data-platform/operations",
                    "reversible": True,
                    "reason": "Preserve owner, evidence pointers, and remediation checklist.",
                },
                {
                    "order": 2,
                    "action": "slack.message.post",
                    "title": "Notify the bounded incident channel",
                    "target": "#inc-data-platform",
                    "reversible": True,
                    "reason": "Publish the known facts, unknowns, and current authorization scope.",
                },
                {
                    "order": 3,
                    "action": "pagerduty.incident.note",
                    "title": "Attach provenance context to the active page",
                    "target": "PD-INC-PAYMENTS-778",
                    "reversible": True,
                    "reason": (
                        "Give the on-call responder DataHub entity and blast-radius pointers."
                    ),
                },
                {
                    "order": 4,
                    "action": "jira.issue.create",
                    "title": "Create the follow-up recovery task",
                    "target": "DATAOPS",
                    "reversible": True,
                    "reason": "Track freshness recovery and post-incident verification separately.",
                },
                {
                    "order": 5,
                    "action": "datahub.incident.writeback",
                    "title": "Write the bounded response receipt to DataHub",
                    "target": "analytics.payments_daily",
                    "reversible": True,
                    "reason": (
                        "Keep the entity, action receipts, unknowns, and next owner together."
                    ),
                },
            ],
            "assumptions": [
                "The listed ownership and lineage are current as of the recorded observation.",
                "Provider targets are allowlisted by the host runtime.",
            ],
            "unknowns": [
                "The deploy marker is temporally adjacent; causality is not established.",
                "No production rollback has been selected or authorized.",
            ],
        },
        "verifier": {
            "status": "complete",
            "label": "AI verifier — advisory only",
            "model": "replayed verifier output",
            "verdict": "PASS WITH BOUNDS",
            "summary": (
                "The proposed fanout is reversible and grounded in recorded metadata. "
                "The verifier did not establish deploy causality or production impact."
            ),
            "policy_checks": [
                {
                    "name": "Evidence classes remain separated",
                    "status": "pass",
                    "detail": "Source assertions are not relabeled as DataHub-verified facts.",
                },
                {
                    "name": "Unknowns are preserved",
                    "status": "pass",
                    "detail": "Causality and user-visible impact remain explicitly unknown.",
                },
                {
                    "name": "Action scope is reversible",
                    "status": "pass",
                    "detail": (
                        "The plan creates or annotates records; it does not mutate production."
                    ),
                },
                {
                    "name": "Claim ceiling is intact",
                    "status": "pass",
                    "detail": "The plan makes no validation, uplift, promotion, or AGI claim.",
                },
            ],
            "authority_note": "AI output cannot grant authorization. Deterministic policy decides.",
        },
        "actions": [
            {
                "provider": "GitHub",
                "short": "GH",
                "operation": "Create incident issue",
                "target": "data-platform/operations",
                "status": "held",
                "detail": "Waiting for deterministic authorization.",
                "receipt": None,
            },
            {
                "provider": "Slack",
                "short": "SL",
                "operation": "Post bounded incident brief",
                "target": "#inc-data-platform",
                "status": "held",
                "detail": "Waiting for deterministic authorization.",
                "receipt": None,
            },
            {
                "provider": "PagerDuty",
                "short": "PD",
                "operation": "Append incident note",
                "target": "PD-INC-PAYMENTS-778",
                "status": "held",
                "detail": "Waiting for deterministic authorization.",
                "receipt": None,
            },
            {
                "provider": "Jira",
                "short": "JR",
                "operation": "Create recovery task",
                "target": "DATAOPS",
                "status": "held",
                "detail": "Waiting for deterministic authorization.",
                "receipt": None,
            },
        ],
        "writeback": {
            "status": "held",
            "entity": "analytics.payments_daily",
            "operation": "DataHub incident receipt UPSERT",
            "receipt": None,
            "detail": "No DataHub write-back has occurred.",
        },
        "memory": {
            "status": "draft",
            "memory_id": None,
            "next_agent": "Recovery verifier",
            "summary": "Fanout and write-back have not executed.",
            "known_facts": [
                "A fixture freshness assertion is outside its recorded threshold.",
                "The fixture graph contains eight downstream assets.",
            ],
            "unknowns": [
                "Root cause is not established.",
                "End-user impact is not established.",
            ],
            "completed": [],
            "next_actions": [
                "Obtain deterministic authorization for the bounded fanout.",
                "After execution, verify provider and DataHub receipts.",
            ],
        },
        "events": [
            {
                "time": "03:06:18",
                "label": "Trigger observed",
                "detail": "Freshness assertion crossed its recorded threshold.",
                "source": "source assertion",
            },
            {
                "time": "03:07:02",
                "label": "Context grounded",
                "detail": "Ownership, tier, and downstream lineage loaded from fixture metadata.",
                "source": "DataHub metadata",
            },
            {
                "time": "03:08:10",
                "label": "Plan proposed",
                "detail": "Reversible collaboration and write-back actions prepared.",
                "source": "deterministic policy",
            },
            {
                "time": "03:09:04",
                "label": "Verifier completed",
                "detail": "Advisory output passed with explicit causality bounds.",
                "source": "AI advisory",
            },
        ],
    }
    state["planner"]["plan_hash"] = plan_fingerprint(state)
    return state


class ReplayIncidentBackend:
    """Deterministic, stateful replay backend with no network operations."""

    mode = "fixture"

    def __init__(self, state: Mapping[str, Any] | None = None) -> None:
        self._initial = copy.deepcopy(dict(state)) if state is not None else _fixture_state()
        self._state = copy.deepcopy(self._initial)
        self._lock = threading.RLock()

    def snapshot(self) -> Mapping[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def trigger(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        del payload
        with self._lock:
            self._state = copy.deepcopy(self._initial)
            self._state["observed_at"] = "2026-07-31T03:14:00Z"
            return copy.deepcopy(self._state)

    def execute(self, authorization: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            incident = self._state.get("incident")
            if not isinstance(incident, dict):
                raise AuthorizationDenied("Fixture incident is unavailable.", authorization)
            if authorization.get("incident_id") != incident.get("id"):
                raise AuthorizationDenied(
                    "Authorization does not match the incident.", authorization
                )

            receipts = {
                "GitHub": "fixture://github/issues/481",
                "Slack": "fixture://slack/messages/1712.4401",
                "PagerDuty": "fixture://pagerduty/incidents/778/notes/4",
                "Jira": "fixture://jira/issues/DATAOPS-219",
            }
            for action in self._state["actions"]:
                action["status"] = "succeeded"
                action["detail"] = "Deterministic fixture action recorded."
                action["receipt"] = receipts[action["provider"]]

            self._state["incident"]["status"] = "coordinating"
            self._state["writeback"] = {
                "status": "recorded",
                "entity": "analytics.payments_daily",
                "operation": "DataHub incident receipt UPSERT",
                "receipt": "fixture://datahub/writeback/inc-2042/receipt-5f2d",
                "aspect": "datasetProperties.customProperties",
                "recorded_at": "2026-07-31T03:14:00Z",
                "detail": (
                    "Fixture receipt only. No DataHub request or external mutation occurred."
                ),
            }
            self._state["memory"] = {
                "status": "ready",
                "memory_id": "fixture://ledgerlens/memory/inc-2042/handoff-1",
                "next_agent": "Recovery verifier",
                "summary": (
                    "Bounded collaboration fanout completed in replay; production recovery "
                    "and root cause remain unverified."
                ),
                "known_facts": [
                    "All four fixture provider actions returned deterministic receipts.",
                    "A fixture DataHub write-back receipt was recorded.",
                    "No production rollback or incident resolution was authorized.",
                ],
                "unknowns": [
                    "Root cause is not established.",
                    "End-user impact is not established.",
                    "Freshness recovery has not been observed.",
                ],
                "completed": [
                    "GitHub incident issue created",
                    "Slack incident brief posted",
                    "PagerDuty note appended",
                    "Jira recovery task created",
                    "DataHub incident receipt written",
                ],
                "next_actions": [
                    "Observe a new freshness check before claiming recovery.",
                    "Compare deploy and query evidence before assigning cause.",
                    "Resolve the incident only through the host system's live policy.",
                ],
                "provenance": [
                    "fixture://datahub/assertions/payments-daily/obs-8831",
                    "fixture://datahub/writeback/inc-2042/receipt-5f2d",
                    *receipts.values(),
                ],
            }
            self._state["events"].extend(
                [
                    {
                        "time": "03:13:22",
                        "label": "Authorization granted",
                        "detail": f"Grant {authorization.get('grant_id')} matched the plan hash.",
                        "source": "deterministic gate",
                    },
                    {
                        "time": "03:14:00",
                        "label": "Fanout completed",
                        "detail": (
                            "Four fixture provider receipts and one write-back receipt recorded."
                        ),
                        "source": "fixture execution",
                    },
                ]
            )
            return copy.deepcopy(self._state)


class UnavailableIncidentBackend:
    """Honest live-mode placeholder used when no runtime is mounted."""

    mode = "live"

    def __init__(self, reason: str = "No live incident backend is mounted.") -> None:
        self.reason = _safe_text(reason)

    def snapshot(self) -> Mapping[str, Any]:
        return {
            "schemaVersion": "1.0",
            "mode": "live",
            "availability": "unconfigured",
            "observed_at": None,
            "capabilities": {
                "trigger": False,
                "authorize": False,
                "execute": False,
                "replay": False,
            },
            "incident": None,
            "context": None,
            "planner": None,
            "verifier": None,
            "actions": [],
            "writeback": None,
            "memory": None,
            "events": [],
            "diagnostic": self.reason,
        }

    def trigger(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        del payload
        raise LiveBackendUnavailable(self.reason)

    def execute(self, authorization: Mapping[str, Any]) -> Mapping[str, Any]:
        del authorization
        raise LiveBackendUnavailable(self.reason)


def _normalise_state(raw: Mapping[str, Any], *, mode: str) -> JsonObject:
    clean = _redact(raw)
    state = dict(clean) if isinstance(clean, Mapping) else {}
    state["mode"] = str(state.get("mode") or mode)
    state["claim_boundary"] = copy.deepcopy(CLAIM_BOUNDARY)
    state.setdefault("schemaVersion", "1.0")
    state.setdefault("availability", "unknown")
    state.setdefault("observed_at", None)
    state.setdefault("capabilities", {})
    state.setdefault("incident", None)
    state.setdefault("context", None)
    state.setdefault("planner", None)
    state.setdefault("verifier", None)
    state.setdefault("actions", [])
    state.setdefault("writeback", None)
    state.setdefault("memory", None)
    state.setdefault("events", [])
    state.setdefault("diagnostic", None)
    if state["mode"] != "fixture":
        state["fixture"] = None

    computed = plan_fingerprint(state)
    planner = state.get("planner")
    if isinstance(planner, dict):
        planner["computed_plan_hash"] = computed
        reported = planner.get("plan_hash")
        planner["integrity"] = (
            "verified" if computed is not None and reported in {None, computed} else "mismatch"
        )
        if state["mode"] == "fixture" and reported is None:
            planner["plan_hash"] = computed
    return state


def _condition(name: str, passed: bool, detail: str, *, pending: bool = False) -> JsonObject:
    return {
        "name": name,
        "status": "pending" if pending else ("pass" if passed else "fail"),
        "detail": detail,
    }


def evaluate_authorization(
    state: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> JsonObject:
    """Evaluate the fail-closed authorization policy without model judgment."""

    request = dict(payload or {})
    incident = state.get("incident")
    context = state.get("context")
    planner = state.get("planner")
    verifier = state.get("verifier")
    fingerprint = plan_fingerprint(state)
    incident_id = incident.get("id") if isinstance(incident, Mapping) else None
    expected = (
        f"AUTHORIZE {incident_id} {fingerprint}"
        if isinstance(incident_id, str) and fingerprint
        else None
    )

    grounded = isinstance(context, Mapping) and context.get("status") == "grounded"
    blast = context.get("blast_radius") if isinstance(context, Mapping) else None
    bounded = isinstance(blast, Mapping) and blast.get("authorization_boundary") == "bounded"
    steps = planner.get("steps") if isinstance(planner, Mapping) else None
    step_items = steps if isinstance(steps, list) else []
    safe_steps = bool(step_items) and all(
        isinstance(step, Mapping)
        and step.get("action") in ALLOWED_ACTIONS
        and step.get("reversible") is True
        for step in step_items
    )
    reported_hash = planner.get("plan_hash") if isinstance(planner, Mapping) else None
    integrity = bool(fingerprint) and reported_hash in {None, fingerprint}
    checks = verifier.get("policy_checks") if isinstance(verifier, Mapping) else None
    check_items = checks if isinstance(checks, list) else []
    policy_checks_pass = bool(check_items) and all(
        isinstance(check, Mapping) and check.get("status") == "pass" for check in check_items
    )

    has_request = payload is not None
    actor = str(request.get("actor", "")).strip()
    hash_matches = bool(fingerprint) and request.get("plan_hash") == fingerprint
    phrase_matches = bool(expected) and request.get("confirmation") == expected
    boundary_acknowledged = request.get("acknowledge_claim_boundary") is True

    conditions = [
        _condition(
            "DataHub context is grounded",
            grounded,
            "The backend must identify grounded context instead of inferred context.",
        ),
        _condition(
            "Blast radius is bounded",
            bounded,
            "Unknown or unbounded dependency scope closes the gate.",
        ),
        _condition(
            "Plan fingerprint is intact",
            integrity,
            "The reported and computed plan fingerprints must agree.",
        ),
        _condition(
            "Every action is allowlisted and reversible",
            safe_steps,
            "This dashboard only authorizes collaboration records and metadata write-back.",
        ),
        _condition(
            "Verifier policy checks are complete",
            policy_checks_pass,
            "Structured checks are required; AI prose is advisory and cannot authorize.",
        ),
        _condition(
            "Actor identity supplied",
            len(actor) >= 2,
            "A named operator must own the authorization receipt.",
            pending=not has_request,
        ),
        _condition(
            "Exact plan hash supplied",
            hash_matches,
            "The request must bind to the current computed plan fingerprint.",
            pending=not has_request,
        ),
        _condition(
            "Exact confirmation phrase supplied",
            phrase_matches,
            "The incident ID and plan fingerprint must be typed exactly.",
            pending=not has_request,
        ),
        _condition(
            "Claim boundary acknowledged",
            boundary_acknowledged,
            "Authorization does not validate causality, impact, recovery, or AGI.",
            pending=not has_request,
        ),
    ]
    allowed = has_request and all(item["status"] == "pass" for item in conditions)
    failures = [item["name"] for item in conditions if item["status"] == "fail"]
    return {
        "decision": "authorized" if allowed else "denied" if has_request else "pending",
        "allowed": allowed,
        "incident_id": incident_id,
        "plan_hash": fingerprint,
        "expected_confirmation": expected,
        "actor": actor or None,
        "conditions": conditions,
        "failures": failures,
        "authority": "deterministic-policy",
        "ai_can_authorize": False,
        "scope": "Provider collaboration fanout and DataHub metadata write-back only.",
        "candidateOnly": True,
        "canClaimAGI": False,
    }


async def _backend_call(backend: Any, method: str, *args: Any) -> Any:
    function = getattr(backend, method, None)
    if not callable(function):
        raise LiveBackendUnavailable(f"Incident backend does not implement '{method}'.")
    if inspect.iscoroutinefunction(function):
        result = await function(*args)
    else:
        result = await asyncio.to_thread(function, *args)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, Mapping):
        raise LiveBackendUnavailable(f"Incident backend '{method}' returned an invalid payload.")
    return result


class IncidentCommander:
    """Coordinates backend state with a deterministic, in-process authorization gate."""

    def __init__(
        self,
        backend: IncidentBackend,
        *,
        clock: Callable[[], datetime] | None = None,
        autonomous_execution: bool = False,
    ) -> None:
        self.backend = backend
        self.clock = clock or (lambda: datetime.now(UTC))
        self.autonomous_execution = autonomous_execution
        self._authorizations: dict[str, JsonObject] = {}
        self._lock = threading.RLock()

    async def snapshot(self) -> JsonObject:
        raw = await _backend_call(self.backend, "snapshot")
        state = _normalise_state(raw, mode=getattr(self.backend, "mode", "live"))
        preview = evaluate_authorization(state)
        incident_id = preview.get("incident_id")
        with self._lock:
            grant = (
                copy.deepcopy(self._authorizations.get(str(incident_id)))
                if incident_id is not None
                else None
            )
        state["authorization"] = grant or preview
        state["automation"] = {
            "enabled": self.autonomous_execution,
            "mode": (
                "ai-verifier-quorum-plus-deterministic-policy"
                if self.autonomous_execution
                else "operator-confirmed-deterministic-policy"
            ),
        }
        return state

    async def trigger(self, payload: Mapping[str, Any]) -> JsonObject:
        await _backend_call(self.backend, "trigger", payload)
        with self._lock:
            self._authorizations.clear()
        if self.autonomous_execution:
            state = await self.snapshot()
            authorization_payload = _autonomous_authorization_payload(state)
            await self.authorize(authorization_payload)
            return await self.execute()
        return await self.snapshot()

    async def authorize(self, payload: Mapping[str, Any]) -> JsonObject:
        state = await self.snapshot()
        result = evaluate_authorization(state, payload)
        if not result["allowed"]:
            raise AuthorizationDenied(
                "Deterministic authorization gate denied the request.",
                result,
            )
        actor = str(result["actor"])
        grant_material = (
            f"{result['incident_id']}|{result['plan_hash']}|{actor}|"
            f"{result['expected_confirmation']}"
        )
        result.update(
            {
                "grant_id": (
                    "grant-" + hashlib.sha256(grant_material.encode("utf-8")).hexdigest()[:12]
                ),
                "authorized_at": _isoformat(self.clock),
                "decision": "authorized",
            }
        )
        with self._lock:
            self._authorizations[str(result["incident_id"])] = copy.deepcopy(result)
        return await self.snapshot()

    async def execute(self) -> JsonObject:
        state = await self.snapshot()
        incident = state.get("incident")
        if not isinstance(incident, Mapping) or not isinstance(incident.get("id"), str):
            raise AuthorizationDenied(
                "No incident is available for execution.",
                evaluate_authorization(state),
            )
        incident_id = str(incident["id"])
        with self._lock:
            grant = copy.deepcopy(self._authorizations.get(incident_id))
        if not grant or grant.get("decision") != "authorized":
            raise AuthorizationDenied(
                "Authorize the current plan before executing fanout.",
                evaluate_authorization(state),
            )
        if grant.get("plan_hash") != plan_fingerprint(state):
            with self._lock:
                self._authorizations.pop(incident_id, None)
            raise AuthorizationDenied(
                "The plan changed after authorization; a new grant is required.",
                evaluate_authorization(state),
            )
        await _backend_call(self.backend, "execute", grant)
        return await self.snapshot()


def _autonomous_authorization_payload(state: Mapping[str, Any]) -> JsonObject:
    """Build an exact plan-bound request only after structured verifier approval."""

    verifier = state.get("verifier")
    if not isinstance(verifier, Mapping):
        raise AuthorizationDenied(
            "Autonomous execution requires a structured verifier result.",
            evaluate_authorization(state),
        )
    checks = verifier.get("policy_checks")
    checks_pass = (
        isinstance(checks, list)
        and bool(checks)
        and all(isinstance(check, Mapping) and check.get("status") == "pass" for check in checks)
    )
    verdict = str(verifier.get("verdict", "")).strip().casefold()
    approved = verifier.get("approved") is True or verdict in {
        "approved",
        "pass",
        "pass with bounds",
    }
    if not approved or not checks_pass:
        raise AuthorizationDenied(
            "AI verifier quorum did not satisfy the deterministic automation precondition.",
            evaluate_authorization(state),
        )
    preview = evaluate_authorization(state)
    if not preview.get("plan_hash") or not preview.get("expected_confirmation"):
        raise AuthorizationDenied(
            "Autonomous execution could not bind authorization to the current plan.",
            preview,
        )
    return {
        "actor": "autonomous-ai-verification-gate",
        "plan_hash": preview["plan_hash"],
        "confirmation": preview["expected_confirmation"],
        "acknowledge_claim_boundary": True,
    }


def plan_exact_authorization_demo(state: Mapping[str, Any]) -> JsonObject:
    """Prove authorization is bound to the EXACT reviewed plan, not catalog state.

    Runs the real deterministic gate twice on the SAME (unchanged) DataHub context:
    once against the reviewed plan (authorized), once after silently appending one
    action to the plan (denied on plan-fingerprint mismatch). This is what separates
    plan-exact authorization from tools that fingerprint context or a risk verdict.
    """

    reviewed = copy.deepcopy(dict(state))
    reviewed_fp = plan_fingerprint(reviewed)
    incident = reviewed.get("incident")
    incident_id = incident.get("id") if isinstance(incident, Mapping) else None
    payload = {
        "actor": "authorization-demo",
        "plan_hash": reviewed_fp,
        "confirmation": f"AUTHORIZE {incident_id} {reviewed_fp}",
        "acknowledge_claim_boundary": True,
    }
    approved = evaluate_authorization(reviewed, payload)

    tampered = copy.deepcopy(reviewed)
    steps = tampered.get("planner", {}).get("steps")
    if isinstance(steps, list):
        steps.append(
            {
                "order": len(steps) + 1,
                "action": "slack.message.post",
                "title": "Extra broadcast appended AFTER review (not reviewed)",
                "target": "#all-company",
                "reversible": True,
                "reason": "Injected post-review to demonstrate plan-exact authorization.",
            }
        )
    # The operator still presents the grant for the ORIGINAL reviewed plan hash.
    tampered["planner"]["plan_hash"] = reviewed_fp
    tampered_fp = plan_fingerprint(tampered)
    denied = evaluate_authorization(tampered, payload)

    return {
        "kind": "plan-exact-authorization",
        "dataHubContextChanged": False,
        "reviewedPlanFingerprint": reviewed_fp,
        "executedPlanFingerprint": tampered_fp,
        "tamper": "One Slack broadcast was appended to the plan after review.",
        "approved": {"decision": approved["decision"]},
        "denied": {
            "decision": denied["decision"],
            "failedConditions": denied["failures"],
            "authority": denied["authority"],
            "ai_can_authorize": denied["ai_can_authorize"],
        },
        "point": (
            "Same DataHub context, different plan -> the deterministic gate refuses on "
            "fingerprint mismatch. Authorization is bound to the exact reviewed plan."
        ),
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def verifier_quorum_demo(state: Mapping[str, Any]) -> JsonObject:
    """Prove the deterministic gate blocks on a split verifier quorum.

    Flips one of two independent AI verifiers to OBJECT and runs the real gate,
    which requires every structured verifier check to pass before it will act.
    """

    unanimous = copy.deepcopy(dict(state))
    reviewed_fp = plan_fingerprint(unanimous)
    incident = unanimous.get("incident")
    incident_id = incident.get("id") if isinstance(incident, Mapping) else None
    payload = {
        "actor": "quorum-demo",
        "plan_hash": reviewed_fp,
        "confirmation": f"AUTHORIZE {incident_id} {reviewed_fp}",
        "acknowledge_claim_boundary": True,
    }
    approved = evaluate_authorization(unanimous, payload)

    split = copy.deepcopy(unanimous)
    checks = split.get("verifier", {}).get("policy_checks")
    objected_name = "verifier objection"
    if isinstance(checks, list) and checks:
        objected_name = str(checks[-1].get("name", objected_name))
        checks[-1] = {
            **checks[-1],
            "status": "fail",
            "detail": "Verifier B objected: causality is not sufficiently bounded.",
        }
        split["verifier"]["verdict"] = "SPLIT — 1 of 2 objected"
    blocked = evaluate_authorization(split, payload)

    return {
        "kind": "verifier-quorum",
        "verifiers": [
            {"id": "verifier-A", "verdict": "pass"},
            {"id": "verifier-B", "verdict": "objected", "on": objected_name},
        ],
        "unanimous": {"decision": approved["decision"]},
        "split": {
            "decision": blocked["decision"],
            "failedConditions": blocked["failures"],
            "authority": blocked["authority"],
        },
        "point": (
            "One verifier objecting is enough: the deterministic gate does not act on a "
            "split quorum. AI review is advisory; unanimous structured approval is required."
        ),
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def allowlist_scope_demo() -> JsonObject:
    """Prove the REAL PolicyGate refuses an off-allowlist target.

    Unlike the plan-exact and quorum demos (which run the dashboard's JSON gate on the
    live snapshot), this exercises the *production* ``ledgerlens.verification.PolicyGate``
    — the same class the orchestrator calls for the real multi-provider fanout (E-16) — on
    a minimal, self-contained plan. One grounded Slack action is authorized against its
    allowlisted channel, then denied when only its target is changed to an off-allowlist
    channel. AI review passes in both runs; the allowlist is enforced by deterministic
    policy, not the model. This backs the README claim that AI "cannot expand target
    allowlists".
    """

    from datetime import UTC, datetime

    from ledgerlens.incident_models import (
        ActionPlan,
        ActionRisk,
        EvidenceKind,
        EvidencePointer,
        Incident,
        IncidentContext,
        IncidentFact,
        IncidentSeverity,
        IncidentTrigger,
        PlannedAction,
    )
    from ledgerlens.runtime_factory import build_policy_gate
    from ledgerlens.verification import VerifierAssessment, VerifierPanel

    clock = datetime(2026, 7, 31, 3, 14, tzinfo=UTC)
    allowlisted = "#inc-data-platform"
    off_allowlist = "#all-company"
    root_urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)"

    incident = Incident(
        incident_id="INC-ALLOWLIST-DEMO",
        title="Orders freshness threshold exceeded",
        severity=IncidentSeverity.HIGH,
        detected_at=clock,
        trigger=IncidentTrigger(
            trigger_id="allowlist-demo:trigger",
            source="datahub",
            kind="freshness_slo",
            occurred_at=clock,
            idempotency_key="allowlist-demo:trigger",
        ),
        affected_entities=(root_urn,),
    )
    context = IncidentContext(
        context_id="allowlist-demo:context",
        incident=incident,
        collected_at=clock,
        facts=(
            IncidentFact(
                fact_id="root-asset",
                statement="The triggering DataHub entity is analytics.orders.",
                evidence=(EvidencePointer(reference=root_urn, kind=EvidenceKind.DATAHUB_ENTITY),),
            ),
        ),
    )

    def _plan(target: str) -> ActionPlan:
        return ActionPlan(
            plan_id="allowlist-demo:plan",
            incident_id=incident.incident_id,
            planner_id="demo:planner",
            planner_family="demo-planner",
            created_at=clock,
            confidence=0.97,
            summary="Post one bounded status update to the incident channel.",
            actions=(
                PlannedAction(
                    action_id="post-status",
                    action_type="slack.message.post",
                    target=target,
                    parameters={
                        "text": "INC-ALLOWLIST-DEMO acknowledged; cause and recovery unverified.",
                    },
                    rationale="Communicate a bounded status update to the incident channel.",
                    evidence_fact_ids=("root-asset",),
                    idempotency_key="allowlist-demo:post-status",
                    risk=ActionRisk.LOW,
                ),
            ),
        )

    class _ApprovingVerifier:
        def __init__(self, verifier_id: str, family: str) -> None:
            self.verifier_id = verifier_id
            self.family = family

        def verify(self, context: IncidentContext, plan: ActionPlan) -> VerifierAssessment:
            del context, plan
            return VerifierAssessment(
                approved=True,
                confidence=0.96,
                reasons=("The action is reversible, allowlisted, and grounded.",),
            )

    panel = VerifierPanel(
        (
            _ApprovingVerifier("demo:verifier-a", "reviewer-a"),
            _ApprovingVerifier("demo:verifier-b", "reviewer-b"),
        )
    )
    gate = build_policy_gate(
        {"slack.message.post": (allowlisted,)},
        minimum_plan_confidence=0.8,
        minimum_verifier_confidence=0.85,
        quorum=2,
    )

    ok_plan = _plan(allowlisted)
    ok_decision = gate.authorize(context, ok_plan, panel.verify(context, ok_plan))
    bad_plan = _plan(off_allowlist)
    bad_decision = gate.authorize(context, bad_plan, panel.verify(context, bad_plan))

    return {
        "kind": "policy-allowlist-scope",
        "allowlistedTarget": allowlisted,
        "offAllowlistTarget": off_allowlist,
        "approved": {"decision": "authorized" if ok_decision.authorized else "denied"},
        "denied": {
            "decision": "authorized" if bad_decision.authorized else "denied",
            "failedConditions": list(bad_decision.reason_codes),
        },
        "point": (
            "Same grounded action, same passing AI review — only the destination changed. "
            "The production PolicyGate that authorizes the real fanout (E-16) refuses an "
            "off-allowlist target. The model cannot widen the allowlist."
        ),
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def _content_security_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def create_incident_router(
    *,
    backend: IncidentBackend | None = None,
    fixture_mode: bool = False,
    fixture_state: Mapping[str, Any] | None = None,
    prefix: str = "/incident",
    clock: Callable[[], datetime] | None = None,
    autonomous_execution: bool = False,
) -> Any:
    """Create a router that can be included in any FastAPI application.

    ``fixture_mode=True`` selects a deterministic replay backend and makes every
    fixture identifier visible. Live mode requires an injected backend; otherwise
    the UI renders an honest unconfigured state and rejects mutations.
    """

    try:
        from fastapi import APIRouter, Request
        from fastapi.responses import FileResponse, JSONResponse
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from starlette.templating import Jinja2Templates
    except ImportError as exc:
        raise RuntimeError("The web extra is required. Install LedgerLens with '[web]'.") from exc

    clean_prefix = "/" + prefix.strip("/") if prefix.strip("/") else ""
    resolved_backend: IncidentBackend
    if backend is not None:
        resolved_backend = backend
    elif fixture_mode:
        resolved_backend = ReplayIncidentBackend(fixture_state)
    else:
        resolved_backend = UnavailableIncidentBackend()

    resolved_clock = clock
    if resolved_clock is None and getattr(resolved_backend, "mode", "") == "fixture":
        resolved_clock = _fixture_clock
    commander = IncidentCommander(
        resolved_backend,
        clock=resolved_clock,
        autonomous_execution=autonomous_execution,
    )

    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
        enable_async=False,
    )
    templates = Jinja2Templates(env=environment)
    router = APIRouter(prefix=clean_prefix, tags=["incident-commander"])

    def error_response(exc: Exception) -> Any:
        status_code = getattr(exc, "status_code", 503)
        payload: JsonObject = {
            "ok": False,
            "detail": _safe_text(exc),
            "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
        }
        if isinstance(exc, AuthorizationDenied):
            payload["authorization"] = _redact(exc.authorization)
        return JSONResponse(payload, status_code=status_code, headers=_content_security_headers())

    @router.get("", name="incident_dashboard")
    async def dashboard(request: Request) -> Any:
        try:
            state = await commander.snapshot()
            status_code = 200
        except Exception as exc:
            state = _normalise_state(
                UnavailableIncidentBackend(_safe_text(exc)).snapshot(),
                mode="live",
            )
            state["authorization"] = evaluate_authorization(state)
            status_code = 503
        return templates.TemplateResponse(
            request=request,
            name="incident_dashboard.html",
            status_code=status_code,
            context={
                "request": request,
                "state": state,
                "base_path": clean_prefix,
            },
            headers=_content_security_headers(),
        )

    @router.get("/assets/incident.css", name="incident_styles")
    async def incident_styles() -> Any:
        return FileResponse(
            _STATIC_ROOT / "incident.css",
            media_type="text/css",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/assets/incident.js", name="incident_script")
    async def incident_script() -> Any:
        return FileResponse(
            _STATIC_ROOT / "incident.js",
            media_type="text/javascript",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/api/live-receipts", name="incident_live_receipts")
    async def api_live_receipts() -> Any:
        # Real per-incident run receipts, published by scripts/build_live_receipts_index.py.
        # Absent until a real run is committed; the demo falls back to simulated receipts.
        path = _STATIC_ROOT / "live-receipts.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (json.JSONDecodeError, OSError):
            payload = {}
        return JSONResponse(
            {"ok": True, "receipts": payload if isinstance(payload, Mapping) else {}},
            headers=_content_security_headers(),
        )

    @router.get("/api/state", name="incident_state")
    async def api_state() -> Any:
        try:
            state = await commander.snapshot()
            return JSONResponse(
                {"ok": True, "state": state},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.get("/api/gate-demo", name="incident_gate_demo")
    async def api_gate_demo() -> Any:
        try:
            state = await commander.snapshot()
            return JSONResponse(
                {"ok": True, "demo": plan_exact_authorization_demo(state)},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.get("/api/quorum-demo", name="incident_quorum_demo")
    async def api_quorum_demo() -> Any:
        try:
            state = await commander.snapshot()
            return JSONResponse(
                {"ok": True, "demo": verifier_quorum_demo(state)},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.get("/api/allowlist-demo", name="incident_allowlist_demo")
    async def api_allowlist_demo() -> Any:
        try:
            return JSONResponse(
                {"ok": True, "demo": allowlist_scope_demo()},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.post("/api/trigger", name="incident_trigger")
    async def api_trigger(request: Request) -> Any:
        try:
            payload = await request.json()
            if not isinstance(payload, Mapping):
                payload = {}
            state = await commander.trigger(payload)
            return JSONResponse(
                {"ok": True, "state": state},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.post("/api/authorize", name="incident_authorize")
    async def api_authorize(request: Request) -> Any:
        try:
            payload = await request.json()
            if not isinstance(payload, Mapping):
                payload = {}
            state = await commander.authorize(payload)
            return JSONResponse(
                {"ok": True, "state": state},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    @router.post("/api/execute", name="incident_execute")
    async def api_execute() -> Any:
        try:
            state = await commander.execute()
            return JSONResponse(
                {"ok": True, "state": state},
                headers=_content_security_headers(),
            )
        except Exception as exc:
            return error_response(exc)

    cast(Any, router).incident_commander = commander
    return router


def create_incident_app(
    *,
    backend: IncidentBackend | None = None,
    fixture_mode: bool = False,
    fixture_state: Mapping[str, Any] | None = None,
    prefix: str = "/incident",
    clock: Callable[[], datetime] | None = None,
    autonomous_execution: bool = False,
) -> Any:
    """Create a small standalone application for tests, demos, or reverse-proxy mounting."""

    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError("The web extra is required. Install LedgerLens with '[web]'.") from exc

    application = FastAPI(
        title="LedgerLens Incident Commander",
        description="Evidence-bounded incident coordination and action receipts.",
        version="0.2.0",
    )
    application.include_router(
        create_incident_router(
            backend=backend,
            fixture_mode=fixture_mode,
            fixture_state=fixture_state,
            prefix=prefix,
            clock=clock,
            autonomous_execution=autonomous_execution,
        )
    )
    return application


__all__ = [
    "ALLOWED_ACTIONS",
    "CLAIM_BOUNDARY",
    "IncidentBackend",
    "IncidentCommander",
    "ReplayIncidentBackend",
    "UnavailableIncidentBackend",
    "create_incident_app",
    "create_incident_router",
    "evaluate_authorization",
    "plan_fingerprint",
]
