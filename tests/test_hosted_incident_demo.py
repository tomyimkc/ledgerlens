"""Pure contract tests for the credential-free hosted smoke checker."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_hosted_incident_demo.py"
SPEC = importlib.util.spec_from_file_location("check_hosted_incident_demo", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_receipt = MODULE.build_receipt
validate_health = MODULE.validate_health
validate_trigger = MODULE.validate_trigger


def _health() -> dict[str, object]:
    return {
        "ok": True,
        "mode": "fixture",
        "externalMutations": False,
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def _trigger() -> dict[str, Any]:
    return {
        "ok": True,
        "state": {
            "mode": "fixture",
            "fixture": {"network_used": False, "external_mutations": False},
            "claim_boundary": {"candidateOnly": True, "canClaimAGI": False},
            "actions": [
                {
                    "provider": provider,
                    "status": "succeeded",
                    "receipt": f"fixture://{provider.casefold()}/receipt",
                }
                for provider in ("GitHub", "Slack", "PagerDuty", "Jira")
            ],
            "writeback": {
                "status": "recorded",
                "receipt": "fixture://datahub/writeback/receipt",
            },
            "memory": {
                "status": "ready",
                "memory_id": "fixture://ledgerlens/memory/handoff",
            },
            "authorization": {
                "decision": "authorized",
                "authority": "deterministic-policy",
                "ai_can_authorize": False,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            "automation": {
                "enabled": True,
                "mode": "ai-verifier-quorum-plus-deterministic-policy",
            },
        },
    }


def test_hosted_contract_accepts_bounded_fixture_replay() -> None:
    assert validate_health(_health()) == []
    assert validate_trigger(_trigger()) == []


def test_hosted_contract_rejects_claim_and_mutation_drift() -> None:
    health = _health()
    health["externalMutations"] = True
    health["canClaimAGI"] = True
    assert {
        "health.externalMutations must be false",
        "health.canClaimAGI must be false",
    }.issubset(validate_health(health))


def test_hosted_contract_rejects_live_or_missing_provider_receipts() -> None:
    trigger = _trigger()
    trigger["state"]["actions"] = trigger["state"]["actions"][:3]
    trigger["state"]["actions"][0]["receipt"] = "https://api.github.test/issues/1"
    errors = validate_trigger(trigger)
    assert "state.actions must contain exactly four actions" in errors
    assert "all four action receipts must use fixture://" in errors


def test_hosted_contract_rejects_ai_self_authorization() -> None:
    trigger = deepcopy(_trigger())
    trigger["state"]["authorization"]["authority"] = "ai-verifier"
    trigger["state"]["authorization"]["ai_can_authorize"] = True
    errors = validate_trigger(trigger)
    assert "authorization.authority must be deterministic-policy" in errors
    assert "authorization.ai_can_authorize must be false" in errors


def test_failed_receipt_does_not_assert_observed_safe_values() -> None:
    receipt = build_receipt("https://example.test", ["network failed"])
    assert receipt["status"] == "FAIL"
    assert receipt["checks"]["contractStatus"] == "FAIL"
    assert receipt["checks"]["externalMutations"] is None
    assert receipt["checks"]["aiCanAuthorize"] is None
