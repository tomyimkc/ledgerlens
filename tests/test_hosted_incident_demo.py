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
validate_context_cut = MODULE.validate_context_cut
validate_seal_lab = MODULE.validate_seal_lab
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


def _seal_lab() -> dict[str, Any]:
    return {
        "ok": True,
        "lab": {
            "scenario": "append-tool-call",
            "serverEvaluated": True,
            "externalMutations": False,
            "authority": "deterministic-policy",
            "ai_can_authorize": False,
            "candidateOnly": True,
            "canClaimAGI": False,
            "result": {
                "decision": "denied",
                "reviewedPlanFingerprint": "reviewed",
                "evaluatedPlanFingerprint": "changed",
                "failedConditions": ["Plan fingerprint is intact"],
            },
        },
    }


def _context_cut(*, scenario: str, authorized: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "lab": {
            "scenario": {"id": scenario},
            "evidenceClass": ("recorded-model-plan-plus-live-deterministic-policy-replay"),
            "recordedModel": {
                "plannerReRunForScenario": False,
                "verifiersReRunForScenario": False,
            },
            "livePolicyReplay": {
                "engine": "ledgerlens.verification.PolicyGate",
                "toolsExecuted": False,
                "matchesRecordedDecision": True,
                "authorization": {
                    "authorized": authorized,
                    "reason_codes": (
                        ["authorized"]
                        if authorized
                        else ["required_context_fact_missing:action-1:primary-owner"]
                    ),
                },
            },
            "externalMutations": False,
            "candidateOnly": True,
            "canClaimAGI": False,
        },
    }


def test_hosted_contract_accepts_bounded_fixture_replay() -> None:
    assert validate_health(_health()) == []
    assert validate_trigger(_trigger()) == []
    assert validate_seal_lab(_seal_lab()) == []
    assert (
        validate_context_cut(
            _context_cut(scenario="full-map", authorized=True),
            expected_scenario="full-map",
            expected_authorized=True,
        )
        == []
    )
    assert (
        validate_context_cut(
            _context_cut(scenario="owner-cut", authorized=False),
            expected_scenario="owner-cut",
            expected_authorized=False,
        )
        == []
    )


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


def test_hosted_contract_rejects_browser_only_or_authorized_plan_drift() -> None:
    seal_lab = _seal_lab()
    seal_lab["lab"]["serverEvaluated"] = False
    seal_lab["lab"]["result"]["decision"] = "authorized"
    errors = validate_seal_lab(seal_lab)
    assert "seal-lab must be evaluated by the server" in errors
    assert "seal-lab plan drift must be denied" in errors


def test_hosted_contract_rejects_context_cut_that_executes_tools_or_hides_missing_fact() -> None:
    context_cut = _context_cut(scenario="owner-cut", authorized=False)
    context_cut["lab"]["livePolicyReplay"]["toolsExecuted"] = True
    context_cut["lab"]["livePolicyReplay"]["authorization"]["reason_codes"] = [
        "verification_not_approved"
    ]

    errors = validate_context_cut(
        context_cut,
        expected_scenario="owner-cut",
        expected_authorized=False,
    )

    assert "context-cut toolsExecuted must be false" in errors
    assert "context-cut denial must report a missing required DataHub fact" in errors


def test_failed_receipt_does_not_assert_observed_safe_values() -> None:
    receipt = build_receipt("https://example.test", ["network failed"])
    assert receipt["status"] == "FAIL"
    assert receipt["checks"]["contractStatus"] == "FAIL"
    assert receipt["checks"]["externalMutations"] is None
    assert receipt["checks"]["aiCanAuthorize"] is None
