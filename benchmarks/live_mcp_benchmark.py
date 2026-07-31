#!/usr/bin/env python3
"""Measure the live DataHub + MCP path without making capability claims.

This benchmark measures infrastructure latency only. It does not validate the
source findings, the agent's scientific conclusions, or any model capability.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import subprocess
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    percentile_index = round(0.95 * (len(ordered) - 1))
    return {
        "n": len(ordered),
        "minMs": round(ordered[0] * 1_000, 3),
        "p50Ms": round(statistics.median(ordered) * 1_000, 3),
        "p95Ms": round(ordered[percentile_index] * 1_000, 3),
        "maxMs": round(ordered[-1] * 1_000, 3),
        "meanMs": round(statistics.fmean(ordered) * 1_000, 3),
    }


async def _timed(
    operation: Callable[[], Awaitable[Any]],
    iterations: int,
) -> tuple[list[float], Any]:
    samples: list[float] = []
    last_result: Any = None
    for _ in range(iterations):
        started = time.perf_counter()
        last_result = await operation()
        samples.append(time.perf_counter() - started)
    return samples, last_result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=args.timeout) as http:
        gms_samples, gms_response = await _timed(
            lambda: http.get(f"{args.gms_url.rstrip('/')}/health"),
            args.iterations,
        )
        gms_response.raise_for_status()

    async with Client(args.mcp_url) as client:
        list_samples, tools = await _timed(client.list_tools, args.iterations)
        search_samples, search_result = await _timed(
            lambda: client.call_tool(
                "search",
                {"query": args.query, "num_results": args.num_results},
            ),
            args.iterations,
        )

    tool_names = sorted(tool.name for tool in tools)
    return {
        "schemaVersion": 1,
        "measuredAt": datetime.now(UTC).isoformat(),
        "gitCommit": git_value("rev-parse", "HEAD"),
        "gitDirty": bool(git_value("status", "--porcelain")),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "gmsUrl": args.gms_url,
            "mcpUrl": args.mcp_url,
        },
        "scope": {
            "measurement": "live DataHub and MCP infrastructure latency",
            "notProven": [
                "scientific validity of ingested findings",
                "independent validation",
                "agent capability uplift",
                "AGI",
            ],
            "candidateOnly": True,
            "canClaimAGI": False,
        },
        "results": {
            "gmsHealth": _summary(gms_samples),
            "mcpListTools": {
                **_summary(list_samples),
                "toolCount": len(tool_names),
                "tools": tool_names,
            },
            "mcpSearch": {
                **_summary(search_samples),
                "query": args.query,
                "responseType": type(search_result).__name__,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gms-url", default="http://localhost:8080")
    parser.add_argument("--mcp-url", default="http://127.0.0.1:8765/mcp")
    parser.add_argument("--query", default="*")
    parser.add_argument("--num-results", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    result = asyncio.run(run(args))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
