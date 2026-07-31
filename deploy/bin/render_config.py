#!/usr/bin/env python3
"""Render secret-bearing judge config and harden the official DataHub compose."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import yaml

LONG_RUNNING_SERVICES = {
    "datahub-actions-quickstart",
    "datahub-gms-quickstart",
    "frontend-quickstart",
    "kafka-broker",
    "mysql",
    "opensearch",
}


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"required environment variable is unset: {name}")
    if "\n" in value or "\r" in value:
        raise SystemExit(f"{name} cannot contain newlines")
    return value


def render_caddy(template: Path, destination: Path) -> None:
    substitutions = {
        "ACME_EMAIL": (
            f"email {os.environ['CADDY_ACME_EMAIL']}" if os.environ.get("CADDY_ACME_EMAIL") else ""
        ),
        "GATEWAY_USERNAME": required("JUDGE_GATEWAY_USERNAME"),
        "GATEWAY_PASSWORD_HASH": required("JUDGE_GATEWAY_PASSWORD_HASH"),
        "LEDGERLENS_FQDN": required("LEDGERLENS_FQDN"),
        "DATAHUB_FQDN": required("DATAHUB_FQDN"),
    }
    text = template.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        text = text.replace("{{" + key + "}}", value)
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", text)
    if leftovers:
        raise SystemExit(f"unresolved Caddy placeholders: {leftovers}")
    destination.write_text(text, encoding="utf-8")


def render_users(datahub_home: Path) -> None:
    admin_username = required("DATAHUB_ADMIN_USERNAME")
    if admin_username != "datahub":
        raise SystemExit("DATAHUB_ADMIN_USERNAME must remain datahub")
    users = (
        (admin_username, required("DATAHUB_ADMIN_PASSWORD")),
        (required("DATAHUB_JUDGE_USERNAME"), required("DATAHUB_JUDGE_PASSWORD")),
        (required("DATAHUB_SERVICE_USERNAME"), required("DATAHUB_SERVICE_PASSWORD")),
    )
    usernames = [username for username, _ in users]
    if len(set(usernames)) != len(usernames):
        raise SystemExit("DataHub admin, judge, and service usernames must be distinct")
    for username, password in users:
        if not re.fullmatch(r"[A-Za-z0-9._@-]+", username):
            raise SystemExit(f"unsupported DataHub username: {username}")
        if ":" in password:
            raise SystemExit("DataHub passwords cannot contain ':'")

    user_file = datahub_home / ".datahub/plugins/frontend/auth/user.props"
    user_file.parent.mkdir(parents=True, exist_ok=True)
    user_file.write_text(
        "".join(f"{username}:{password}\n" for username, password in users),
        encoding="utf-8",
    )
    # The official frontend container runs as uid/gid 100, while the bind-mounted
    # file is created by the host operator (commonly uid/gid 1000). The enclosing
    # deployment state tree is mode 0700, so make only this bind-mounted file
    # world-readable for the non-root container instead of exposing the state tree.
    user_file.chmod(0o644)


def harden_datahub_compose(source: Path, destination: Path) -> None:
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("official DataHub compose was not a mapping")
    services = payload.get("services")
    if not isinstance(services, dict):
        raise SystemExit("official DataHub compose did not contain services")

    expected = {
        "datahub-gms-quickstart",
        "frontend-quickstart",
        "system-update-quickstart",
    }
    missing = expected.difference(services)
    if missing:
        raise SystemExit(f"official DataHub compose changed; missing services: {sorted(missing)}")

    payload["name"] = "ledgerlens-datahub"
    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        ports = service.get("ports") or []
        for port in ports:
            if not isinstance(port, dict):
                raise SystemExit(
                    f"unexpected short port syntax in official compose service {service_name}"
                )
            port["host_ip"] = "127.0.0.1"
        if service_name in LONG_RUNNING_SERVICES:
            service["restart"] = "unless-stopped"

    gms_environment = services["datahub-gms-quickstart"].setdefault("environment", {})
    if not isinstance(gms_environment, dict):
        raise SystemExit("DataHub GMS environment has an unexpected shape")
    gms_environment.update(
        {
            "AUTH_POLICIES_ENABLED": "true",
            # DataHub's documented static user.props mode requires either
            # pre-provisioned actors or disabled existence enforcement. We
            # still create the user aspects and verify Reader-only policy
            # grants, while this setting lets the exact JAAS allowlist log in.
            "METADATA_SERVICE_AUTH_ENFORCE_EXISTENCE_ENABLED": "false",
            "METADATA_SERVICE_AUTH_ENABLED": "true",
            "REST_API_AUTHORIZATION": "true",
        }
    )

    frontend_environment = services["frontend-quickstart"].setdefault("environment", {})
    if not isinstance(frontend_environment, dict):
        raise SystemExit("DataHub frontend environment has an unexpected shape")
    frontend_environment["AUTH_JAAS_ENABLED"] = "true"
    frontend_volumes = services["frontend-quickstart"].setdefault("volumes", [])
    if not isinstance(frontend_volumes, list):
        raise SystemExit("DataHub frontend volumes have an unexpected shape")
    default_user_file = (
        Path(required("DATAHUB_HOME")).resolve() / ".datahub/plugins/frontend/auth/user.props"
    )
    frontend_volumes.append(
        {
            "type": "bind",
            "source": str(default_user_file),
            "target": "/datahub-frontend/conf/user.props",
            "read_only": True,
        }
    )

    destination.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120),
        encoding="utf-8",
    )


def write_compose_env(state_dir: Path) -> None:
    values = {
        "CADDYFILE_PATH": str(state_dir / "Caddyfile"),
        "CADDY_IMAGE": os.environ.get("CADDY_IMAGE", "caddy:2.10.2-alpine"),
        "DATAHUB_FQDN": required("DATAHUB_FQDN"),
        "DATAHUB_NETWORK_NAME": os.environ.get(
            "DATAHUB_NETWORK_NAME", "ledgerlens-datahub_default"
        ),
        "LEDGERLENS_RUNTIME_ENV": str(state_dir / "runtime.env"),
        "PUBLIC_HTTP_PORT": os.environ.get("PUBLIC_HTTP_PORT", "80"),
        "PUBLIC_HTTPS_PORT": os.environ.get("PUBLIC_HTTPS_PORT", "443"),
    }
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            raise SystemExit(f"invalid newline in {key}")
    (state_dir / "compose.env").write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-compose", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    args = parser.parse_args()

    state_dir = args.state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    datahub_home = Path(required("DATAHUB_HOME")).resolve()
    datahub_home.mkdir(parents=True, exist_ok=True)

    harden_datahub_compose(args.source_compose, state_dir / "datahub-compose.judge.yml")
    render_users(datahub_home)
    render_caddy(args.template, state_dir / "Caddyfile")
    write_compose_env(state_dir)

    for path in (state_dir / "Caddyfile", state_dir / "compose.env"):
        path.chmod(0o600)


if __name__ == "__main__":
    main()
