#!/usr/bin/env python3
"""Build a deterministic, claim-bounded index across LedgerLens evidence layers.

The contest evidence is intentionally split:

* E-16 is one plan -> verify -> authorize -> four-provider execution.
* E-07 is a separate DataHub document write and MCP read-back.
* The hosted continuity workflow repeatedly checks the public fixture and policy labs
  without credentials or external mutations.

This builder does not pretend those records were one integrated production run. It makes
the separation machine-readable, verifies their shared incident identity and claim
boundaries, and emits one compact artifact for judges.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
E16 = ROOT / "benchmarks/incident_commander/live-incident-rehearsal-receipt.json"
E07 = ROOT / "benchmarks/incident_commander/datahub-live-writeback-receipt.json"
OUTPUTS = (
    ROOT / "benchmarks/incident_commander/live-evidence-ladder.json",
    ROOT / "src/ledgerlens/static/live-evidence-ladder.json",
)

EXPECTED_PROVIDERS = ("GitHub", "Slack", "PagerDuty", "Jira")


class EvidenceLadderError(ValueError):
    """Raised when a source receipt violates the bounded evidence contract."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceLadderError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceLadderError(f"{path} must contain a JSON object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceLadderError(message)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_ladder(e16: dict[str, Any], e07: dict[str, Any]) -> dict[str, Any]:
    """Validate the two live receipts and build a compact evidence ladder."""

    _require(e16.get("status") == "executed", "E-16 must be an executed rehearsal")
    _require(e16.get("externalMutations") is True, "E-16 must record external mutations")
    _require(e16.get("candidateOnly") is True, "E-16 candidateOnly must remain true")
    _require(e16.get("canClaimAGI") is False, "E-16 canClaimAGI must remain false")
    authorization = e16.get("authorization")
    _require(isinstance(authorization, dict), "E-16 authorization must be an object")
    _require(authorization.get("authorized") is True, "E-16 must be policy-authorized")

    dashboard = e16.get("dashboardState")
    _require(isinstance(dashboard, dict), "E-16 dashboardState must be an object")
    raw_actions = dashboard.get("actions")
    _require(isinstance(raw_actions, list), "E-16 actions must be a list")
    providers = tuple(
        str(action.get("provider"))
        for action in raw_actions
        if isinstance(action, dict) and action.get("status") == "succeeded"
    )
    _require(
        set(providers) == set(EXPECTED_PROVIDERS),
        "E-16 must contain succeeded GitHub, Slack, PagerDuty, and Jira actions",
    )

    _require(e07.get("status") == "applied", "E-07 must be an applied DataHub write")
    _require(e07.get("externalMutation") is True, "E-07 must record an external mutation")
    _require(e07.get("candidateOnly") is True, "E-07 candidateOnly must remain true")
    _require(e07.get("canClaimAGI") is False, "E-07 canClaimAGI must remain false")
    retrieval = e07.get("nextAgentRetrieval")
    _require(isinstance(retrieval, dict), "E-07 nextAgentRetrieval must be an object")
    _require(retrieval.get("retrieved") is True, "E-07 must record MCP read-back")

    incident = e16.get("incident")
    _require(isinstance(incident, dict), "E-16 incident must be an object")
    incident_id = incident.get("incident_id") or incident.get("id")
    writeback_authorization = e07.get("authorization")
    _require(
        isinstance(writeback_authorization, dict),
        "E-07 authorization must be an object",
    )
    writeback_context = writeback_authorization.get("incidentContext")
    _require(
        isinstance(writeback_context, dict),
        "E-07 authorization.incidentContext must be an object",
    )
    writeback_incident_id = writeback_context.get("incidentId")
    _require(
        bool(incident_id) and incident_id == writeback_incident_id,
        "E-16 and E-07 must reference the same incident id",
    )

    layers: list[dict[str, Any]] = [
        {
            "id": "policy-sealed-provider-run",
            "evidenceId": "E-16",
            "evidenceClass": "bounded-live-provider-rehearsal",
            "label": "Policy-sealed provider run",
            "observedAt": authorization.get("evaluated_at"),
            "networkUsed": e16.get("networkUsed") is True,
            "externalMutations": True,
            "plannerAndVerifiersExecuted": True,
            "deterministicPolicyAuthorized": True,
            "providers": sorted(providers),
            "providerActionCount": len(providers),
            "proves": (
                "One supervised invocation planned, verified, authorized, and executed "
                "one bounded action against four providers."
            ),
            "doesNotProve": (
                "Sustained operation, incident recovery, production reliability, or "
                "provider-family independence."
            ),
        },
        {
            "id": "datahub-write-read",
            "evidenceId": "E-07",
            "evidenceClass": "bounded-live-datahub-write-read",
            "label": "DataHub write-back and next-agent read",
            "observedAt": e07.get("completedAt"),
            "networkUsed": True,
            "externalMutations": True,
            "tool": e07.get("tool"),
            "retrieved": True,
            "retrievalVia": retrieval.get("via"),
            "resultUrn": (e07.get("result") or {}).get("urn"),
            "proves": (
                "One controlled DataHub document was written and retrieved through the "
                "official MCP read surface."
            ),
            "doesNotProve": (
                "That the DataHub write occurred in the E-16 process, or that the incident "
                "was causal, impactful, or recovered."
            ),
        },
        {
            "id": "hosted-continuity",
            "evidenceId": "E-21",
            "evidenceClass": "repeated-public-contract-sample",
            "label": "Repeated public contract sample",
            "networkUsed": True,
            "externalMutations": False,
            "providerToolsExecuted": False,
            "workflowUrl": (
                "https://github.com/tomyimkc/ledgerlens/actions/workflows/hosted-continuity.yml"
            ),
            "proves": (
                "A credential-free workflow can repeatedly sample the deployed fixture, "
                "Seal Lab refusal, and DataHub Context Cut contract."
            ),
            "doesNotProve": (
                "Provider reliability, an uptime SLO, production readiness, or external validation."
            ),
        },
    ]
    digest_basis = {
        "incidentId": incident_id,
        "e16Authorization": {
            "planId": authorization.get("plan_id"),
            "policyVersion": authorization.get("policy_version"),
            "authorized": authorization.get("authorized"),
            "providers": sorted(providers),
        },
        "e07Writeback": {
            "receiptId": e07.get("receiptId"),
            "requestDigest": e07.get("requestDigest"),
            "resultUrn": (e07.get("result") or {}).get("urn"),
            "retrieved": retrieval.get("retrieved"),
        },
    }
    return {
        "schemaVersion": "ledgerlens.live-evidence-ladder.v1",
        "incidentId": incident_id,
        "layers": layers,
        "crossReceiptChecks": {
            "sameIncidentId": True,
            "claimBoundaryPreserved": True,
            "integratedSameProcessRun": False,
            "e16SourceDigest": None,
            "e07SourceDigest": None,
            "evidenceChainDigest": _canonical_digest(digest_basis),
        },
        "openGap": {
            "label": "Not yet proven",
            "integratedLiveDataHubReadActWriteSameRun": False,
            "sustainedProviderOperation": False,
            "incidentRecovery": False,
            "productionReliability": False,
            "independentValidation": False,
            "nextSafeTest": (
                "On an owner-controlled DataHub instance, execute one supervised "
                "read -> sealed provider action -> DataHub write-back -> MCP read-back "
                "sequence and preserve it as one receipt."
            ),
        },
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def build_from_paths(e16_path: Path = E16, e07_path: Path = E07) -> dict[str, Any]:
    ladder = build_ladder(_load(e16_path), _load(e07_path))
    checks = ladder["crossReceiptChecks"]
    checks["e16SourceDigest"] = _sha256(e16_path)
    checks["e07SourceDigest"] = _sha256(e07_path)
    return ladder


def main() -> int:
    ladder = build_from_paths()
    rendered = json.dumps(ladder, indent=2, sort_keys=True) + "\n"
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
