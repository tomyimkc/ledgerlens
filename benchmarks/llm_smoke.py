#!/usr/bin/env python3
"""Run one bounded OpenAI (or Anthropic) API health check.

Does not claim model quality, uplift, or independence — transport + JSON only.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "anthropic"), default="openai")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/llm-smoke.json"))
    args = parser.parse_args()

    if args.provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LEDGERLENS_LLM_API_KEY")
        if not key:
            parser.error("ANTHROPIC_API_KEY is required")
        base = (args.base_url or "https://api.anthropic.com").rstrip("/")
        model = args.model or "claude-3-5-haiku-latest"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 64,
                    "messages": [{"role": "user", "content": 'Return JSON: {"ok": true}'}],
                },
            )
            response.raise_for_status()
            payload = response.json()
    else:
        key = os.getenv("OPENAI_API_KEY") or os.getenv("LEDGERLENS_LLM_API_KEY")
        if not key:
            parser.error("OPENAI_API_KEY is required")
        base = (args.base_url or "https://api.openai.com/v1").rstrip("/")
        model = args.model or "gpt-4o-mini"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base}/chat/completions",
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0,
                    "messages": [
                        {"role": "user", "content": 'Return JSON: {"ok": true}'},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()

    receipt = {
        "schemaVersion": "1.0",
        "kind": "llm-smoke",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "provider": args.provider,
        "baseUrl": base,
        "model": model,
        "httpStatus": response.status_code,
        "ok": True,
        "measurement": "LLM API transport health only",
        "candidateOnly": True,
        "canClaimAGI": False,
        "responseKeys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(args.output), "ok": True, "provider": args.provider},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
