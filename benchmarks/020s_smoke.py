#!/usr/bin/env python3
"""Run one bounded 020s API health check.

The check verifies transport availability only. It does not evaluate reasoning
quality and is excluded from the deterministic default test suite.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://api.020s.com/v1")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    key = os.getenv("SOPHIA_020S_KEY")
    if not key:
        parser.error("SOPHIA_020S_KEY is required")

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": "Reply with exactly LEDGERLENS_OK and nothing else.",
            },
            {"role": "user", "content": "Health check."},
        ],
        "max_completion_tokens": 32,
        "temperature": 0,
    }
    started = time.perf_counter()
    response = httpx.post(
        f"{args.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=args.timeout,
    )
    latency_ms = round((time.perf_counter() - started) * 1_000, 3)
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    content = body.get("choices", [{}])[0].get("message", {}).get("content")

    result = {
        "schemaVersion": 1,
        "measuredAt": datetime.now(UTC).isoformat(),
        "scope": {
            "measurement": "020s API transport health only",
            "candidateOnly": True,
            "canClaimAGI": False,
            "notProven": ["reasoning quality", "capability uplift", "independent validation"],
        },
        "result": {
            "httpStatus": response.status_code,
            "model": body.get("model", args.model),
            "latencyMs": latency_ms,
            "expectedExactResponse": "LEDGERLENS_OK",
            "receivedExactResponse": content,
            "exactMatch": content == "LEDGERLENS_OK",
            "usage": body.get("usage"),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
