"""Hugging Face entrypoint for the LedgerLens fixture replay."""

from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from ledgerlens.incident_dashboard import create_incident_app

app = cast(
    FastAPI,
    create_incident_app(
        fixture_mode=True,
        prefix="/incident",
        autonomous_execution=True,
    ),
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send judges directly to the Incident Commander."""

    return RedirectResponse(url="/incident", status_code=307)


@app.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    """Return a fixture-mode health receipt without implying live integrations."""

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "fixture",
        "externalMutations": False,
        "candidateOnly": True,
        "canClaimAGI": False,
    }
    return JSONResponse(payload)
