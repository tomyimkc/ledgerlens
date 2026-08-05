"""Deterministic tests for the mountable Incident Commander dashboard."""

import copy
import importlib
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from ledgerlens.incident_dashboard import (
    ReplayIncidentBackend,
    create_incident_app,
    create_incident_router,
)

FastAPI = importlib.import_module("fastapi").FastAPI
TestClient = importlib.import_module("fastapi.testclient").TestClient


def _fixture_client(*, prefix: str = "/incident") -> Any:
    return TestClient(create_incident_app(fixture_mode=True, prefix=prefix))


def test_fixture_dashboard_has_full_command_surface_and_explicit_claim_boundary() -> None:
    client = _fixture_client()

    response = client.get("/incident")

    assert response.status_code == 200
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    for expected in (
        "FIXTURE / REPLAY",
        "No DataHub request or external mutation occurred",
        "INC-2042",
        "Grounded entity &amp; blast radius",
        "Bounded response plan",
        "AI verifier — advisory only",
        "AI cannot open this gate",
        "GitHub",
        "Slack",
        "PagerDuty",
        "Jira",
        "DataHub write-back",
        "What the next agent receives",
        "candidateOnly: true",
        "canClaimAGI: false",
    ):
        assert expected in response.text or expected.replace("&amp;", "&") in response.text


def test_fixture_state_is_deterministic_and_distinguishes_evidence_classes() -> None:
    client = _fixture_client()

    first = client.get("/incident/api/state")
    second = client.get("/incident/api/state")

    assert first.status_code == 200
    assert first.json() == second.json()
    state = first.json()["state"]
    assert state["mode"] == "fixture"
    assert state["fixture"] == {
        "label": "FIXTURE / REPLAY",
        "replay_id": "fixture-inc-2042-v1",
        "network_used": False,
        "external_mutations": False,
        "note": (
            "Deterministic contest replay. No DataHub request or external mutation occurred. "
            "Provider receipts use fixture:// identifiers and do not describe live state."
        ),
    }
    assert state["incident"]["trigger"]["classification"] == "source assertion"
    assert state["context"]["status"] == "grounded"
    assert state["context"]["blast_radius"]["confidence"] == "metadata-derived, not causal proof"
    assert state["verifier"]["authority_note"].startswith("AI output cannot grant")
    assert state["authorization"]["decision"] == "pending"


def test_live_mode_never_substitutes_fixture_or_provider_success_state() -> None:
    client = TestClient(create_incident_app(fixture_mode=False))

    page = client.get("/incident")
    state_response = client.get("/incident/api/state")
    trigger = client.post("/incident/api/trigger", json={"alert": "real"})

    assert page.status_code == 200
    assert "LIVE BACKEND UNCONFIGURED" in page.text
    assert "No fixture state has been substituted" in page.text
    assert "INC-2042" not in page.text
    assert "fixture://" not in page.text
    state = state_response.json()["state"]
    assert state["mode"] == "live"
    assert state["fixture"] is None
    assert state["incident"] is None
    assert state["actions"] == []
    assert state["writeback"] is None
    assert trigger.status_code == 503
    assert trigger.json()["ok"] is False


def test_deterministic_gate_denies_wrong_phrase_and_does_not_execute_actions() -> None:
    client = _fixture_client()
    state = client.get("/incident/api/state").json()["state"]

    response = client.post(
        "/incident/api/authorize",
        json={
            "actor": "incident-commander@example.com",
            "plan_hash": state["authorization"]["plan_hash"],
            "confirmation": "AUTHORIZE SOMETHING ELSE",
            "acknowledge_claim_boundary": True,
        },
    )
    execute = client.post("/incident/api/execute")
    current = client.get("/incident/api/state").json()["state"]

    assert response.status_code == 409
    authorization = response.json()["authorization"]
    assert authorization["decision"] == "denied"
    assert "Exact confirmation phrase supplied" in authorization["failures"]
    assert execute.status_code == 409
    assert all(action["status"] == "held" for action in current["actions"])
    assert current["writeback"]["receipt"] is None
    assert current["memory"]["status"] == "draft"


def test_deterministic_gate_denies_tampered_plan_hash_despite_correct_phrase() -> None:
    """A correct confirmation phrase must not authorize a plan that was not reviewed.

    This is the plan-fingerprint binding claim: authorization is bound to the exact
    reviewed plan, independently of whether the operator typed the right phrase.
    """
    client = _fixture_client()
    state = client.get("/incident/api/state").json()["state"]

    response = client.post(
        "/incident/api/authorize",
        json={
            "actor": "incident-commander@example.com",
            "plan_hash": "deadbeefdeadbeef",
            "confirmation": state["authorization"]["expected_confirmation"],
            "acknowledge_claim_boundary": True,
        },
    )
    execute = client.post("/incident/api/execute")
    current = client.get("/incident/api/state").json()["state"]

    assert response.status_code == 409
    authorization = response.json()["authorization"]
    assert authorization["decision"] == "denied"
    assert "Exact plan hash supplied" in authorization["failures"]
    assert execute.status_code == 409
    assert all(action["status"] == "held" for action in current["actions"])
    assert current["writeback"]["receipt"] is None
    assert current["memory"]["status"] == "draft"


def test_exact_authorization_executes_fanout_writeback_and_inherited_memory() -> None:
    client = _fixture_client()
    state = client.get("/incident/api/state").json()["state"]
    authorization = state["authorization"]

    granted = client.post(
        "/incident/api/authorize",
        json={
            "actor": "incident-commander@example.com",
            "plan_hash": authorization["plan_hash"],
            "confirmation": authorization["expected_confirmation"],
            "acknowledge_claim_boundary": True,
        },
    )

    assert granted.status_code == 200
    granted_state = granted.json()["state"]
    assert granted_state["authorization"]["decision"] == "authorized"
    assert granted_state["authorization"]["grant_id"].startswith("grant-")
    assert granted_state["authorization"]["authorized_at"] == "2026-07-31T03:14:00Z"

    executed = client.post("/incident/api/execute")

    assert executed.status_code == 200
    result = executed.json()["state"]
    assert {action["provider"] for action in result["actions"]} == {
        "GitHub",
        "Slack",
        "PagerDuty",
        "Jira",
    }
    assert all(action["status"] == "succeeded" for action in result["actions"])
    assert all(str(action["receipt"]).startswith("fixture://") for action in result["actions"])
    assert result["writeback"]["status"] == "recorded"
    assert result["writeback"]["receipt"].startswith("fixture://datahub/writeback/")
    assert result["memory"]["status"] == "ready"
    assert result["memory"]["next_agent"] == "Recovery verifier"
    assert "Root cause is not established." in result["memory"]["unknowns"]
    assert result["claim_boundary"]["candidateOnly"] is True
    assert result["claim_boundary"]["canClaimAGI"] is False


def test_replay_trigger_invalidates_authorization_and_resets_receipts() -> None:
    client = _fixture_client()
    state = client.get("/incident/api/state").json()["state"]
    authorization = state["authorization"]
    payload = {
        "actor": "incident-commander@example.com",
        "plan_hash": authorization["plan_hash"],
        "confirmation": authorization["expected_confirmation"],
        "acknowledge_claim_boundary": True,
    }
    assert client.post("/incident/api/authorize", json=payload).status_code == 200
    assert client.post("/incident/api/execute").status_code == 200

    replayed = client.post("/incident/api/trigger", json={"replay": True})

    assert replayed.status_code == 200
    replayed_state = replayed.json()["state"]
    assert replayed_state["authorization"]["decision"] == "pending"
    assert all(action["status"] == "held" for action in replayed_state["actions"])
    assert replayed_state["writeback"]["status"] == "held"
    assert replayed_state["memory"]["status"] == "draft"


def test_autonomous_mode_runs_verification_gate_and_fanout_without_operator_form() -> None:
    client = TestClient(
        create_incident_app(
            fixture_mode=True,
            autonomous_execution=True,
        )
    )

    result = client.post("/incident/api/trigger", json={"replay": True})

    assert result.status_code == 200
    state = result.json()["state"]
    assert state["automation"] == {
        "enabled": True,
        "mode": "ai-verifier-quorum-plus-deterministic-policy",
    }
    assert state["authorization"]["decision"] == "authorized"
    assert state["authorization"]["actor"] == "autonomous-ai-verification-gate"
    assert all(action["status"] == "succeeded" for action in state["actions"])
    assert state["writeback"]["status"] == "recorded"
    assert state["memory"]["status"] == "ready"


def test_plan_change_after_authorization_fails_closed() -> None:
    class MutableReplayBackend(ReplayIncidentBackend):
        def mutate_plan(self) -> None:
            with self._lock:
                self._state["planner"]["steps"][0]["target"] = "changed/target"

    backend = MutableReplayBackend()
    client = TestClient(create_incident_app(backend=backend))
    state = client.get("/incident/api/state").json()["state"]
    authorization = state["authorization"]
    payload = {
        "actor": "incident-commander@example.com",
        "plan_hash": authorization["plan_hash"],
        "confirmation": authorization["expected_confirmation"],
        "acknowledge_claim_boundary": True,
    }
    assert client.post("/incident/api/authorize", json=payload).status_code == 200

    backend.mutate_plan()
    response = client.post("/incident/api/execute")

    assert response.status_code == 409
    assert "plan changed after authorization" in response.json()["detail"].lower()


def test_router_mounts_under_custom_prefix_with_its_own_assets() -> None:
    app = FastAPI()
    app.include_router(create_incident_router(fixture_mode=True, prefix="/ops/commander"))
    client = TestClient(app)

    page = client.get("/ops/commander")
    css = client.get("/ops/commander/assets/incident.css")
    script = client.get("/ops/commander/assets/incident.js")

    assert page.status_code == 200
    assert 'href="/ops/commander/assets/incident.css"' in page.text
    assert 'data-api-base="/ops/commander/api"' in page.text
    assert css.status_code == 200
    assert "--signal: #0f766e" in css.text
    assert script.status_code == 200
    assert "Evaluating deterministic gate" in script.text


def test_untrusted_backend_text_is_escaped_and_secret_fields_are_redacted() -> None:
    fixture = copy.deepcopy(ReplayIncidentBackend().snapshot())
    fixture["incident"]["title"] = '<script>alert("incident")</script>'
    fixture["context"]["api_token"] = "do-not-render"
    fixture["context"]["blast_radius"]["unknowns"] = ["Authorization: Bearer sensitive-value"]
    client = TestClient(create_incident_app(backend=ReplayIncidentBackend(fixture)))

    page = client.get("/incident")
    state = client.get("/incident/api/state").json()["state"]

    assert page.status_code == 200
    assert "<script>" not in page.text
    assert "&lt;script&gt;" in page.text
    assert "do-not-render" not in page.text
    assert "sensitive-value" not in page.text
    assert state["context"]["api_token"] == "[REDACTED]"
    assert state["context"]["blast_radius"]["unknowns"] == ["Authorization: Bearer [REDACTED]"]


def test_plan_exact_and_quorum_demos_reject_via_the_real_gate() -> None:
    client = _fixture_client()

    gate = client.get("/incident/api/gate-demo").json()["demo"]
    assert gate["dataHubContextChanged"] is False
    assert gate["reviewedPlanFingerprint"] != gate["executedPlanFingerprint"]
    assert gate["approved"]["decision"] == "authorized"
    assert gate["denied"]["decision"] == "denied"
    assert "Plan fingerprint is intact" in gate["denied"]["failedConditions"]

    quorum = client.get("/incident/api/quorum-demo").json()["demo"]
    verdicts = {v["id"]: v["verdict"] for v in quorum["verifiers"]}
    assert verdicts.get("verifier-B") == "objected"
    assert quorum["unanimous"]["decision"] == "authorized"
    assert quorum["split"]["decision"] == "denied"
    assert "Verifier policy checks are complete" in quorum["split"]["failedConditions"]


def test_allowlist_scope_demo_rejects_off_allowlist_target_via_the_real_gate() -> None:
    client = _fixture_client()

    demo = client.get("/incident/api/allowlist-demo").json()["demo"]

    # Only the target differs between the two runs; AI review passes in both.
    assert demo["allowlistedTarget"] != demo["offAllowlistTarget"]
    assert demo["approved"]["decision"] == "authorized"
    assert demo["denied"]["decision"] == "denied"
    assert any("target_not_allowlisted" in code for code in demo["denied"]["failedConditions"])
