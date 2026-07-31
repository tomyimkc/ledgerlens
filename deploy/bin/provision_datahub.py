#!/usr/bin/env python3
"""Provision and verify least-privilege DataHub judge identities."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

READER_ROLE = "urn:li:dataHubRole:Reader"
BASE_POLICY_URN = "urn:li:dataHubPolicy:7"
READ_PREFIXES = ("VIEW_", "GET_", "SEARCH_", "ES_EXPLAIN_")


class DataHubAPI:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:1000]
            raise SystemExit(f"DataHub HTTP {exc.code}: {detail}") from exc
        if not raw:
            return {}
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise SystemExit("DataHub returned a non-object JSON response")
        return decoded

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = self.request(
            "POST",
            "/api/graphql",
            {"query": query, "variables": variables},
        )
        errors = payload.get("errors")
        if errors:
            raise SystemExit(f"DataHub GraphQL error: {json.dumps(errors)[:1200]}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SystemExit("DataHub GraphQL response did not contain data")
        return data


def actor_urn(username: str) -> str:
    return f"urn:li:corpuser:{username}"


def enable_user(api: DataHubAPI, username: str) -> None:
    urn = actor_urn(username)
    api.request(
        "POST",
        (
            "/openapi/v3/entity/corpuser/"
            + quote(urn, safe="")
            + "/status?async=false&systemMetadata=false"
            + "&createIfEntityNotExists=false&createIfNotExists=true"
        ),
        {"value": {"removed": False}},
    )


def assign_reader(api: DataHubAPI, username: str) -> None:
    api.graphql(
        """
        mutation AssignReader($input: BatchAssignRoleInput!) {
          batchAssignRole(input: $input)
        }
        """,
        {
            "input": {
                "roleUrn": READER_ROLE,
                "actors": [actor_urn(username)],
            }
        },
    )


def set_base_policy(api: DataHubAPI, *, active: bool) -> None:
    privileges = ["VIEW_ANALYTICS", "GENERATE_PERSONAL_ACCESS_TOKENS"] if active else []
    api.graphql(
        """
        mutation SetBasePolicy($urn: String!, $input: PolicyUpdateInput!) {
          updatePolicy(urn: $urn, input: $input)
        }
        """,
        {
            "urn": BASE_POLICY_URN,
            "input": {
                "type": "PLATFORM",
                "name": "All Users - Base Platform Privileges",
                "state": "ACTIVE" if active else "INACTIVE",
                "description": (
                    "Temporarily active while the private judge deployment issues a service token."
                    if active
                    else "Disabled for the public LedgerLens judge environment."
                ),
                "privileges": privileges,
                "actors": {
                    "users": [],
                    "groups": [],
                    "allUsers": True,
                    "allGroups": False,
                    "resourceOwners": False,
                },
            },
        },
    )


def search_ledgerlens_urn(api: DataHubAPI) -> str:
    data = api.graphql(
        """
        query LedgerLensEntity {
          searchAcrossEntities(
            input: {
              query: "ledgerlens.failure_ledger"
              types: [DATASET]
              start: 0
              count: 1
            }
          ) {
            searchResults { entity { urn } }
          }
        }
        """,
        {},
    )
    page = data.get("searchAcrossEntities") or {}
    results = page.get("searchResults") or []
    if not results:
        raise SystemExit("No LedgerLens dataset was found after seeding")
    urn = ((results[0] or {}).get("entity") or {}).get("urn")
    if not isinstance(urn, str) or not urn:
        raise SystemExit("LedgerLens search result did not contain a URN")
    return urn


def granted_privileges(api: DataHubAPI, username: str, resource_urn: str) -> dict[str, list[str]]:
    data = api.graphql(
        """
        query JudgePrivileges($actor: String!, $resource: String!) {
          platform: getGrantedPrivileges(input: {actorUrn: $actor}) {
            privileges
          }
          metadata: getGrantedPrivileges(
            input: {
              actorUrn: $actor
              resourceSpec: {resourceType: DATASET, resourceUrn: $resource}
            }
          ) {
            privileges
          }
        }
        """,
        {"actor": actor_urn(username), "resource": resource_urn},
    )
    return {
        "platform": sorted((data.get("platform") or {}).get("privileges") or []),
        "metadata": sorted((data.get("metadata") or {}).get("privileges") or []),
    }


def verify_reader(api: DataHubAPI, username: str, resource_urn: str) -> dict[str, Any]:
    privileges = granted_privileges(api, username, resource_urn)
    if privileges["platform"]:
        raise SystemExit(
            f"{username} unexpectedly has platform privileges: {privileges['platform']}"
        )
    unsafe = [
        privilege for privilege in privileges["metadata"] if not privilege.startswith(READ_PREFIXES)
    ]
    if unsafe:
        raise SystemExit(f"{username} unexpectedly has write privileges: {unsafe}")
    if "VIEW_ENTITY_PAGE" not in privileges["metadata"]:
        raise SystemExit(f"{username} is missing VIEW_ENTITY_PAGE")
    return {
        "actor": actor_urn(username),
        "platformPrivileges": privileges["platform"],
        "metadataPrivileges": privileges["metadata"],
        "readOnlyVerified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("bootstrap", "lock-down", "verify"))
    parser.add_argument("--gms-url", required=True)
    parser.add_argument("--admin-token-file", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    token = args.admin_token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("admin token file was empty")
    api = DataHubAPI(args.gms_url, token)
    judge = os.environ["DATAHUB_JUDGE_USERNAME"]
    service = os.environ["DATAHUB_SERVICE_USERNAME"]

    result: dict[str, Any] = {"phase": args.phase}
    if args.phase == "bootstrap":
        set_base_policy(api, active=True)
        for username in (judge, service):
            enable_user(api, username)
            assign_reader(api, username)
        result["actors"] = [actor_urn(judge), actor_urn(service)]
        result["basePolicyTemporarilyActive"] = True
    else:
        resource_urn = search_ledgerlens_urn(api)
        if args.phase == "lock-down":
            set_base_policy(api, active=False)
        result["resourceUrn"] = resource_urn
        result["actors"] = [
            verify_reader(api, judge, resource_urn),
            verify_reader(api, service, resource_urn),
        ]
        result["basePolicyActive"] = False

    result.update(
        {
            "candidateOnly": True,
            "canClaimAGI": False,
            "note": (
                "Privileges describe DataHub access only; they do not validate the source findings."
            ),
        }
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
