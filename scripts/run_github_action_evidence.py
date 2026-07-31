#!/usr/bin/env python3
"""Create and immediately close one real, clearly labeled GitHub rehearsal issue."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ledgerlens.actions import ActionAuthorizer, GitHubIssueAction, GitHubIssueAdapter

DEFAULT_OUTPUT = Path("benchmarks/incident_commander/github-live-action-receipt.json")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute one HMAC-authorized GitHub issue action, preserve its sanitized "
            "receipt, and close the rehearsal issue."
        )
    )
    parser.add_argument("--owner", default="tomyimkc")
    parser.add_argument("--repository", default="ledgerlens")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required acknowledgment that this creates and closes a real GitHub issue.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _close_issue(
    *,
    token: str,
    owner: str,
    repository: str,
    issue_number: int,
) -> dict[str, Any]:
    with httpx.Client(
        base_url="https://api.github.com",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ledgerlens-action-evidence/0.2",
        },
        timeout=httpx.Timeout(20, connect=5),
    ) as client:
        response = client.patch(
            f"/repos/{owner}/{repository}/issues/{issue_number}",
            json={"state": "closed", "state_reason": "completed"},
        )
        response.raise_for_status()
        payload = response.json()
    return {
        "httpStatus": response.status_code,
        "state": payload.get("state"),
        "stateReason": payload.get("state_reason"),
        "closedAt": payload.get("closed_at"),
    }


def main() -> int:
    args = _arguments()
    if not args.confirm_live:
        print("--confirm-live is required", file=sys.stderr)
        return 2
    if args.output.exists() and not args.force:
        print(f"refusing to overwrite existing receipt: {args.output}", file=sys.stderr)
        return 2
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    now = datetime.now(UTC).replace(microsecond=0)
    authorizer = ActionAuthorizer(
        secrets.token_bytes(32),
        issuer="ledgerlens-live-evidence",
    )
    adapter = GitHubIssueAdapter(token, authorizer=authorizer, timeout=20)
    action = GitHubIssueAction(
        owner=args.owner,
        repository=args.repository,
        title=f"[LedgerLens rehearsal] Autonomous incident receipt {now.isoformat()}",
        body=(
            "This temporary issue was created by the LedgerLens signed GitHub action "
            "adapter as bounded competition evidence and is closed automatically.\n\n"
            "- No production incident is asserted.\n"
            "- No root cause, user impact, or recovery is claimed.\n"
            "- `candidateOnly: true`\n"
            "- `canClaimAGI: false`\n"
        ),
        idempotency_key=f"github-live-evidence:{now.isoformat()}",
    )
    preview = adapter.preview(action)
    authorization = authorizer.issue(
        preview,
        subject="autonomous-ai-verification-plus-deterministic-policy",
        authorization_id=f"github-live-evidence:{now.isoformat()}",
    )
    try:
        provider_receipt = adapter.execute(action, authorization)
    finally:
        adapter.close()

    issue_number_raw = provider_receipt.details.get("number")
    if not isinstance(issue_number_raw, int):
        raise RuntimeError("GitHub receipt did not contain an issue number")

    cleanup_required = True
    closure: dict[str, Any]
    try:
        closure = _close_issue(
            token=token,
            owner=args.owner,
            repository=args.repository,
            issue_number=issue_number_raw,
        )
        cleanup_required = closure.get("state") != "closed"
    except Exception as exc:
        closure = {
            "error": f"{type(exc).__name__}: GitHub cleanup request failed",
        }

    receipt = {
        "schemaVersion": "1.0",
        "kind": "github-live-action-evidence",
        "executedAt": now.isoformat().replace("+00:00", "Z"),
        "externalMutation": True,
        "adapter": "GitHubIssueAdapter",
        "preview": preview.model_dump(mode="json"),
        "authorization": {
            "authorizationId": authorization.authorization_id,
            "issuer": authorization.issuer,
            "subject": authorization.subject,
            "adapter": authorization.adapter,
            "operation": authorization.operation,
            "actionDigest": authorization.action_digest,
            "idempotencyKey": authorization.idempotency_key,
            "issuedAt": authorization.issued_at.isoformat(),
            "expiresAt": authorization.expires_at.isoformat(),
            "algorithm": authorization.algorithm,
            "signatureRecorded": False,
        },
        "providerReceipt": provider_receipt.model_dump(mode="json"),
        "closure": closure,
        "cleanupRequired": cleanup_required,
        "limitations": [
            "This receipt proves issue creation and closure, not incident causality or recovery.",
            "Slack, PagerDuty, Jira, and DataHub live mutations are not represented here.",
        ],
        "candidateOnly": True,
        "canClaimAGI": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "issue": provider_receipt.remote_url,
                "closed": not cleanup_required,
                "candidateOnly": True,
                "canClaimAGI": False,
            },
            sort_keys=True,
        )
    )
    return 0 if not cleanup_required else 3


if __name__ == "__main__":
    raise SystemExit(main())
