"""FastAPI demo tests that skip cleanly when the optional web extra is absent."""

from __future__ import annotations

import copy
import importlib
import json
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from ledgerlens.web import DEMO_FINDINGS, DemoDataAdapter, UnavailableDataAdapter, create_app

TestClient = importlib.import_module("fastapi.testclient").TestClient


def test_dashboard_visibly_labels_fixture_and_shows_required_context() -> None:
    client = TestClient(create_app(demo_mode=True))

    response = client.get("/")

    assert response.status_code == 200
    assert "DEMO FIXTURE" in response.text
    assert "DataHub was not contacted" in response.text
    assert ">4</strong>" in response.text
    assert "findings indexed" in response.text
    assert "Findings at a glance" in response.text
    assert "Next actions" in response.text
    assert 'href="http://testserver/incident"' in response.text
    assert "candidateOnly: true" in response.text
    assert "canClaimAGI: false" in response.text


def test_demo_app_mounts_autonomous_incident_commander_by_default() -> None:
    client = TestClient(create_app(demo_mode=True))

    page = client.get("/incident")
    triggered = client.post("/incident/api/trigger", json={"replay": True})

    assert page.status_code == 200
    assert "Incident Commander" in page.text
    state = triggered.json()["state"]
    assert state["automation"]["enabled"] is True
    assert state["authorization"]["decision"] == "authorized"
    assert all(action["status"] == "succeeded" for action in state["actions"])
    assert state["writeback"]["status"] == "recorded"


def test_incident_commander_defaults_can_be_overridden_for_manual_fixture() -> None:
    client = TestClient(
        create_app(
            demo_mode=True,
            incident_fixture_mode=True,
            incident_autonomous_execution=False,
        )
    )

    triggered = client.post("/incident/api/trigger", json={"replay": True})

    assert triggered.status_code == 200
    state = triggered.json()["state"]
    assert state["automation"]["enabled"] is False
    assert state["authorization"]["decision"] == "pending"
    assert all(action["status"] == "held" for action in state["actions"])


def test_finding_page_shows_ownership_evidence_audit_and_supersession() -> None:
    client = TestClient(create_app(demo_mode=True))
    finding_id = "ledger-validator-blind-spots-2026-07-26"

    response = client.get(f"/findings/{finding_id}")

    assert response.status_code == 200
    for expected in (
        "Ownership &amp; response",
        "Provenance Engineering",
        "Evidence receipts",
        "DataHub URN",
        "Supersession chain",
        "strict-parser-fixture-suite-2026-07-31",
        "not independently validate",
    ):
        assert expected in response.text or expected.replace("&amp;", "&") in response.text


def test_queue_and_safe_downloads_are_deterministic() -> None:
    client = TestClient(create_app(demo_mode=True))

    page = client.get("/queue")
    json_report = client.get("/reports/triage.json")
    markdown_report = client.get("/reports/triage.md")

    assert page.status_code == 200
    assert "Remediation queue" in page.text
    assert "Assign an owner and attach a reviewable evidence receipt." in page.text

    assert json_report.status_code == 200
    assert json_report.headers["content-disposition"] == (
        'attachment; filename="ledgerlens-triage.json"'
    )
    assert json_report.headers["x-content-type-options"] == "nosniff"
    json_payload = json_report.json()
    assert json_payload["mode"] == "demo"
    assert json_payload["queue"][0]["finding_id"] == ("unowned-evidence-receipt-2026-07-31")

    assert markdown_report.status_code == 200
    assert markdown_report.headers["content-disposition"] == (
        'attachment; filename="ledgerlens-triage.md"'
    )
    assert markdown_report.headers["x-content-type-options"] == "nosniff"
    assert "independently validate" in markdown_report.text
    assert "canClaimAGI: false" in markdown_report.text


def test_untrusted_ledger_text_is_html_escaped() -> None:
    finding = copy.deepcopy(DEMO_FINDINGS[0])
    finding["title"] = '<script>alert("title")</script>'
    finding["summary"] = '<img src=x onerror="alert(1)">'
    adapter = DemoDataAdapter(findings=[finding])
    client = TestClient(create_app(adapter=adapter, demo_mode=True))

    dashboard = client.get("/")
    detail = client.get(f"/findings/{finding['id']}")

    assert dashboard.status_code == 200
    assert "<script>" not in dashboard.text
    assert "&lt;script&gt;" in dashboard.text
    assert '<img src=x onerror="alert(1)">' not in detail.text
    assert "&lt;img src=x onerror=" in detail.text


def test_diagnostics_and_reports_redact_secret_like_fields() -> None:
    class SecretAdapter(DemoDataAdapter):
        mode = "live"

        def connection_status(self) -> dict[str, Any]:
            status = super().connection_status()
            status.update(
                {
                    "mode": "live",
                    "api_token": "dashboard-secret",
                    "diagnostic": "Authorization: Bearer header-secret",
                }
            )
            return status

        def triage(self) -> dict[str, Any]:
            report = super().triage()
            report["password"] = "report-secret"
            return report

    client = TestClient(create_app(adapter=SecretAdapter(), demo_mode=False))

    dashboard = client.get("/")
    report = client.get("/reports/triage.json")

    assert dashboard.status_code == 200
    assert "dashboard-secret" not in dashboard.text
    assert "header-secret" not in dashboard.text
    assert "report-secret" not in report.text
    assert json.loads(report.text)["password"] == "[REDACTED]"


def test_empty_and_missing_finding_states_are_clear() -> None:
    client = TestClient(create_app(adapter=DemoDataAdapter(findings=[]), demo_mode=True))

    dashboard = client.get("/")
    missing = client.get("/findings/not-present")
    api_missing = client.get("/api/findings/not-present")

    assert dashboard.status_code == 200
    assert "No findings available" in dashboard.text
    assert missing.status_code == 404
    assert "Finding not found" in missing.text
    assert api_missing.status_code == 404
    assert api_missing.json()["detail"] == "Finding not found"


def test_health_endpoint_preserves_claim_ceiling() -> None:
    client = TestClient(create_app(demo_mode=True))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "mode": "demo",
        "candidateOnly": True,
        "canClaimAGI": False,
    }


def test_live_health_fails_closed_when_dependencies_are_unavailable() -> None:
    client = TestClient(
        create_app(
            adapter=UnavailableDataAdapter("DataHub is unavailable"),
            demo_mode=False,
        )
    )

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "mode": "unavailable",
        "candidateOnly": True,
        "canClaimAGI": False,
    }
