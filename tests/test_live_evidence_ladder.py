"""Tests for the deterministic live-evidence ladder."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_live_evidence_ladder.py"
SPEC = importlib.util.spec_from_file_location("build_live_evidence_ladder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _e16() -> dict[str, Any]:
    return {
        "status": "executed",
        "externalMutations": True,
        "networkUsed": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "authorization": {
            "authorized": True,
            "evaluated_at": "2026-08-03T16:35:59Z",
            "plan_id": "plan-1",
            "policy_version": "incident-commander/v2",
        },
        "incident": {"incident_id": "inc-1"},
        "dashboardState": {
            "actions": [
                {"provider": provider, "status": "succeeded"}
                for provider in ("GitHub", "Slack", "PagerDuty", "Jira")
            ]
        },
    }


def _e07() -> dict[str, Any]:
    return {
        "status": "applied",
        "externalMutation": True,
        "candidateOnly": True,
        "canClaimAGI": False,
        "completedAt": "2026-07-31T08:40:54Z",
        "tool": "save_document",
        "receiptId": "receipt-1",
        "requestDigest": "digest-1",
        "authorization": {"incidentContext": {"incidentId": "inc-1"}},
        "nextAgentRetrieval": {
            "retrieved": True,
            "via": "official-datahub-mcp:get_entities",
        },
        "result": {"urn": "urn:li:document:1"},
    }


def test_ladder_preserves_split_evidence_and_open_gap() -> None:
    ladder = MODULE.build_ladder(_e16(), _e07())

    assert ladder["incidentId"] == "inc-1"
    assert [layer["evidenceId"] for layer in ladder["layers"]] == ["E-16", "E-07", "E-21"]
    assert ladder["layers"][0]["providerActionCount"] == 4
    assert ladder["layers"][1]["retrieved"] is True
    assert ladder["crossReceiptChecks"]["integratedSameProcessRun"] is False
    assert ladder["openGap"]["integratedLiveDataHubReadActWriteSameRun"] is False
    assert ladder["candidateOnly"] is True
    assert ladder["canClaimAGI"] is False


def test_ladder_fails_closed_on_mismatched_incident_or_claim_drift() -> None:
    e07 = _e07()
    e07["authorization"]["incidentContext"]["incidentId"] = "other"
    with pytest.raises(MODULE.EvidenceLadderError, match="same incident"):
        MODULE.build_ladder(_e16(), e07)

    e16 = deepcopy(_e16())
    e16["canClaimAGI"] = True
    with pytest.raises(MODULE.EvidenceLadderError, match="canClaimAGI"):
        MODULE.build_ladder(e16, _e07())
