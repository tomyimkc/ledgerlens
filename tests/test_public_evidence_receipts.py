"""Tests for presentation-safe evidence derivatives."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_public_evidence_receipts.py"
SPEC = importlib.util.spec_from_file_location("build_public_evidence_receipts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sanitize_removes_obsolete_provider_and_autonomy_labels() -> None:
    value, redactions = MODULE._sanitize(
        {
            "provider": "https://api.020s.com/v1",
            "planner": "020s:gpt-5.6-sol",
            "label": "autonomous authorization",
        }
    )

    rendered = str(value)
    assert "api.020s.com" not in rendered
    assert "020s:" not in rendered
    assert "autonomous" not in rendered.casefold()
    assert {
        "obsolete model endpoint",
        "obsolete model-provider prefix",
        "obsolete autonomy label",
    }.issubset(redactions)


def test_derivative_preserves_claim_flags_and_marks_itself_as_redacted() -> None:
    real_source = MODULE.DIRECTORY / "ai-verification-receipt.json"
    derivative = MODULE.build_public_derivative(
        {"candidateOnly": True, "canClaimAGI": False},
        source_path=real_source,
    )

    assert derivative["publicDerivative"] is True
    assert derivative["sourceReceiptDigest"].startswith("sha256:")
    assert derivative["candidateOnly"] is True
    assert derivative["canClaimAGI"] is False
    assert "not a new run" in derivative["integrityNote"]
