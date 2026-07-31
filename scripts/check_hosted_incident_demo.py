#!/usr/bin/env python3
"""Fail-closed smoke check for the public LedgerLens fixture replay."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

DEFAULT_BASE_URL = "https://tomyimkc-ledgerlens-incident-commander.hf.space"
EXPECTED_PROVIDERS = {"GitHub", "Slack", "PagerDuty", "Jira"}


def _expect(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _as_mapping(value: object, label: str, errors: list[str]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    errors.append(f"{label} must be an object")
    return {}


def validate_health(payload: object) -> list[str]:
    """Validate the stable, secret-free health contract."""

    errors: list[str] = []
    health = _as_mapping(payload, "health response", errors)
    _expect(errors, health.get("ok") is True, "health.ok must be true")
    _expect(errors, health.get("mode") == "fixture", "health.mode must be fixture")
    _expect(
        errors,
        health.get("externalMutations") is False,
        "health.externalMutations must be false",
    )
    _expect(
        errors,
        health.get("candidateOnly") is True,
        "health.candidateOnly must be true",
    )
    _expect(
        errors,
        health.get("canClaimAGI") is False,
        "health.canClaimAGI must be false",
    )
    return errors


def validate_trigger(payload: object) -> list[str]:
    """Validate the fixture trigger, receipts, and authority boundary."""

    errors: list[str] = []
    response = _as_mapping(payload, "trigger response", errors)
    _expect(errors, response.get("ok") is True, "trigger.ok must be true")
    state = _as_mapping(response.get("state"), "trigger.state", errors)

    _expect(errors, state.get("mode") == "fixture", "state.mode must be fixture")
    fixture = _as_mapping(state.get("fixture"), "state.fixture", errors)
    _expect(
        errors,
        fixture.get("network_used") is False,
        "fixture.network_used must be false",
    )
    _expect(
        errors,
        fixture.get("external_mutations") is False,
        "fixture.external_mutations must be false",
    )

    claim_boundary = _as_mapping(state.get("claim_boundary"), "state.claim_boundary", errors)
    _expect(
        errors,
        claim_boundary.get("candidateOnly") is True,
        "claim_boundary.candidateOnly must be true",
    )
    _expect(
        errors,
        claim_boundary.get("canClaimAGI") is False,
        "claim_boundary.canClaimAGI must be false",
    )

    raw_actions = state.get("actions")
    if not isinstance(raw_actions, list):
        errors.append("state.actions must be a list")
        actions: list[object] = []
    else:
        actions = raw_actions
    _expect(errors, len(actions) == 4, "state.actions must contain exactly four actions")

    providers: set[str] = set()
    receipts: list[str] = []
    for index, raw_action in enumerate(actions):
        action = _as_mapping(raw_action, f"state.actions[{index}]", errors)
        provider = action.get("provider")
        if isinstance(provider, str):
            providers.add(provider)
        else:
            errors.append(f"state.actions[{index}].provider must be a string")
        receipt = action.get("receipt")
        if isinstance(receipt, str):
            receipts.append(receipt)
        else:
            errors.append(f"state.actions[{index}].receipt must be a string")
        _expect(
            errors,
            action.get("status") == "succeeded",
            f"state.actions[{index}].status must be succeeded",
        )
    _expect(
        errors,
        providers == EXPECTED_PROVIDERS,
        "state.actions providers must be GitHub, Slack, PagerDuty, and Jira",
    )
    _expect(
        errors,
        len(receipts) == 4 and all(receipt.startswith("fixture://") for receipt in receipts),
        "all four action receipts must use fixture://",
    )

    writeback = _as_mapping(state.get("writeback"), "state.writeback", errors)
    _expect(
        errors,
        writeback.get("status") == "recorded",
        "state.writeback.status must be recorded",
    )
    _expect(
        errors,
        isinstance(writeback.get("receipt"), str)
        and str(writeback["receipt"]).startswith("fixture://"),
        "state.writeback.receipt must use fixture://",
    )

    memory = _as_mapping(state.get("memory"), "state.memory", errors)
    _expect(errors, memory.get("status") == "ready", "state.memory.status must be ready")
    _expect(
        errors,
        isinstance(memory.get("memory_id"), str)
        and str(memory["memory_id"]).startswith("fixture://"),
        "state.memory.memory_id must use fixture://",
    )

    authorization = _as_mapping(state.get("authorization"), "state.authorization", errors)
    _expect(
        errors,
        authorization.get("decision") == "authorized",
        "authorization.decision must be authorized",
    )
    _expect(
        errors,
        authorization.get("authority") == "deterministic-policy",
        "authorization.authority must be deterministic-policy",
    )
    _expect(
        errors,
        authorization.get("ai_can_authorize") is False,
        "authorization.ai_can_authorize must be false",
    )
    _expect(
        errors,
        authorization.get("candidateOnly") is True,
        "authorization.candidateOnly must be true",
    )
    _expect(
        errors,
        authorization.get("canClaimAGI") is False,
        "authorization.canClaimAGI must be false",
    )

    automation = _as_mapping(state.get("automation"), "state.automation", errors)
    _expect(errors, automation.get("enabled") is True, "automation.enabled must be true")
    _expect(
        errors,
        automation.get("mode") == "ai-verifier-quorum-plus-deterministic-policy",
        "automation.mode must preserve AI advisory verification plus deterministic policy",
    )
    return errors


def normalize_base_url(value: str) -> str:
    """Return a credential-free HTTP(S) origin."""

    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query or fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def request_json(
    base_url: str,
    path: str,
    *,
    method: str,
    payload: Mapping[str, Any] | None,
    timeout: float,
) -> object:
    """Request one public JSON endpoint without cookies or credentials."""

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "LedgerLens-hosted-smoke/1.0",
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{method} {path} returned HTTP {response.status}")
        return json.load(response)


def request_with_retries(
    base_url: str,
    path: str,
    *,
    method: str,
    payload: Mapping[str, Any] | None,
    timeout: float,
    attempts: int,
    delay: float,
) -> object:
    """Retry bounded transient failures, including a sleeping hosted Space."""

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_json(
                base_url,
                path,
                method=method,
                payload=payload,
                timeout=timeout,
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(delay)
    assert last_error is not None
    raise last_error


def build_receipt(base_url: str, errors: list[str]) -> dict[str, Any]:
    """Build a sanitized receipt containing no response bodies or credentials."""

    passed = not errors
    return {
        "schemaVersion": "ledgerlens.hosted-smoke.v1",
        "status": "PASS" if passed else "FAIL",
        "observedAtUtc": datetime.now(UTC).isoformat(),
        "baseUrl": base_url,
        "checks": {
            "contractStatus": "PASS" if passed else "FAIL",
            "fixtureMode": True if passed else None,
            "externalMutations": False if passed else None,
            "providerReceiptCount": 4 if passed else None,
            "providerReceiptScheme": "fixture://" if passed else None,
            "writebackStatus": "recorded" if passed else None,
            "memoryStatus": "ready" if passed else None,
            "authorizationAuthority": "deterministic-policy" if passed else None,
            "aiCanAuthorize": False if passed else None,
        },
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "errors": errors,
        "limitations": [
            "This checks the public deterministic fixture replay, not live provider execution.",
            "A passing smoke does not establish production readiness or independent validation.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    try:
        base_url = normalize_base_url(args.base_url)
    except ValueError as error:
        base_url = "<invalid>"
        errors.append(str(error))

    if args.attempts < 1:
        errors.append("--attempts must be at least 1")
    if args.timeout <= 0:
        errors.append("--timeout must be positive")
    if args.retry_delay < 0:
        errors.append("--retry-delay cannot be negative")

    if not errors:
        try:
            health = request_with_retries(
                base_url,
                "/healthz",
                method="GET",
                payload=None,
                timeout=args.timeout,
                attempts=args.attempts,
                delay=args.retry_delay,
            )
            errors.extend(validate_health(health))
            trigger = request_with_retries(
                base_url,
                "/incident/api/trigger",
                method="POST",
                payload={"replay": True},
                timeout=args.timeout,
                attempts=args.attempts,
                delay=args.retry_delay,
            )
            errors.extend(validate_trigger(trigger))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"hosted request failed: {type(error).__name__}: {error}")

    receipt = build_receipt(base_url, errors)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if errors:
        print("Hosted Incident Commander smoke failed:")
        print("\n".join(f"  - {error}" for error in errors))
        return 1
    print("Hosted Incident Commander smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
