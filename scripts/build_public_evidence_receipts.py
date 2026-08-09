#!/usr/bin/env python3
"""Build presentation-safe derivatives of historical live evidence receipts.

The source receipts remain in git for auditability and are identified by SHA-256. Public
derivatives remove obsolete provider-brand labels and endpoint strings without changing the
underlying event, authorization, provider-action, DataHub-result, or claim-boundary facts.

These files are redacted views, not new runs.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "benchmarks/incident_commander"
SOURCES = {
    "ai-verification-receipt.json": "public-ai-verification-receipt.json",
    "live-incident-rehearsal-receipt.json": "public-live-incident-rehearsal-receipt.json",
    "datahub-live-writeback-receipt.json": "public-datahub-live-writeback-receipt.json",
}

LEGACY_ENDPOINT = re.compile(r"https?://api\.020s\.com(?:/v1)?", re.IGNORECASE)
LEGACY_PROVIDER_PREFIX = re.compile(r"(?i)\b020s:")
LEGACY_AUTONOMY = re.compile(r"(?i)\bautonomous\b")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sanitize_string(value: str) -> tuple[str, set[str]]:
    redactions: set[str] = set()
    updated = value
    if LEGACY_ENDPOINT.search(updated):
        updated = LEGACY_ENDPOINT.sub("[REDACTED-HISTORICAL-MODEL-ENDPOINT]", updated)
        redactions.add("obsolete model endpoint")
    if LEGACY_PROVIDER_PREFIX.search(updated):
        updated = LEGACY_PROVIDER_PREFIX.sub("", updated)
        redactions.add("obsolete model-provider prefix")
    if LEGACY_AUTONOMY.search(updated):
        updated = LEGACY_AUTONOMY.sub("policy-authorized", updated)
        redactions.add("obsolete autonomy label")
    return updated, redactions


def _sanitize(value: Any) -> tuple[Any, set[str]]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        redactions: set[str] = set()
        for key, item in value.items():
            sanitized, item_redactions = _sanitize(item)
            result[key] = sanitized
            redactions.update(item_redactions)
        return result, redactions
    if isinstance(value, list):
        result_list: list[Any] = []
        redactions = set()
        for item in value:
            sanitized, item_redactions = _sanitize(item)
            result_list.append(sanitized)
            redactions.update(item_redactions)
        return result_list, redactions
    if isinstance(value, str):
        return _sanitize_string(value)
    return deepcopy(value), set()


def build_public_derivative(source: dict[str, Any], *, source_path: Path) -> dict[str, Any]:
    sanitized, redactions = _sanitize(source)
    if not isinstance(sanitized, dict):
        raise ValueError("source receipt must be an object")

    # The historical DataHub call body contains presentation-era prose. Preserve its call
    # digest and result, but do not republish that prose as current copy.
    request_arguments = sanitized.get("requestArguments")
    if isinstance(request_arguments, dict) and "content" in request_arguments:
        request_arguments["content"] = (
            "[REDACTED: historical presentation copy; requestDigest and result preserved]"
        )
        redactions.add("historical write-back prose")

    sanitized["publicDerivative"] = True
    sanitized["sourceReceipt"] = str(source_path.relative_to(ROOT))
    sanitized["sourceReceiptDigest"] = _digest(source_path)
    sanitized["presentationRedactions"] = sorted(redactions)
    sanitized["integrityNote"] = (
        "Presentation-safe derivative of the committed source receipt. Redactions remove "
        "obsolete provider branding and presentation labels; this is not a new run. Use "
        "sourceReceiptDigest to bind this view to the archived source."
    )
    sanitized["candidateOnly"] = True
    sanitized["canClaimAGI"] = False
    return sanitized


def main() -> int:
    for source_name, output_name in SOURCES.items():
        source_path = DIRECTORY / source_name
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{source_name} must contain an object")
        output = DIRECTORY / output_name
        derivative = build_public_derivative(raw, source_path=source_path)
        output.write_text(
            json.dumps(derivative, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
