"""Tests for the public Hugging Face Docker Space package."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

TestClient = importlib.import_module("fastapi.testclient").TestClient
ROOT = Path(__file__).parents[1]
SPACE = ROOT / "deploy" / "hf-space"


def _space_app() -> Any:
    spec = importlib.util.spec_from_file_location("ledgerlens_hf_space", SPACE / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_space_routes_to_autonomous_incident_commander() -> None:
    client = TestClient(_space_app())

    root = client.get("/", follow_redirects=False)
    health = client.get("/healthz")
    incident = client.get("/incident")
    triggered = client.post("/incident/api/trigger", json={"replay": True})

    assert root.status_code == 307
    assert root.headers["location"] == "/incident"
    assert health.json() == {
        "ok": True,
        "mode": "fixture",
        "externalMutations": False,
        "candidateOnly": True,
        "canClaimAGI": False,
    }
    assert incident.status_code == 200
    assert "FIXTURE / REPLAY" in incident.text
    state = triggered.json()["state"]
    assert state["automation"]["enabled"] is True
    assert state["authorization"]["decision"] == "authorized"
    assert all(action["receipt"].startswith("fixture://") for action in state["actions"])
    assert state["writeback"]["status"] == "recorded"
    assert state["memory"]["status"] == "ready"


def test_space_metadata_and_workflow_preserve_secret_boundaries() -> None:
    readme = (SPACE / "README.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "deploy-hf-space.yml").read_text(encoding="utf-8")
    dockerfile = (SPACE / "Dockerfile").read_text(encoding="utf-8")

    assert "sdk: docker" in readme
    assert "app_port: 7860" in readme
    assert "candidateOnly: true" in readme
    assert "canClaimAGI: false" in readme
    assert "environment: hf-space" in workflow
    assert "secrets.HF_TOKEN" in workflow
    assert "vars.HF_SPACE_REPO_ID" in workflow
    assert "branches: [main]" in workflow
    assert "USER ledgerlens" in dockerfile
    assert ".[web]" in dockerfile
