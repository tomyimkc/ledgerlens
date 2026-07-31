"""Focused tests for the hardened temporary DataHub proof package."""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
RENDER_CONFIG = ROOT / "deploy/bin/render_config.py"
PROVISION_DATAHUB = ROOT / "deploy/bin/provision_datahub.py"


def _load_render_config() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live_proof_render_config", RENDER_CONFIG)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_provision_datahub() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live_proof_provision_datahub", PROVISION_DATAHUB)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_user_props_is_readable_by_non_root_container_inside_private_tree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_render_config()
    state_dir = tmp_path / "private-state"
    state_dir.mkdir(mode=0o700)
    datahub_home = state_dir / "datahub-home"
    values = {
        "DATAHUB_ADMIN_USERNAME": "datahub",
        "DATAHUB_ADMIN_PASSWORD": "admin-password-1234",
        "DATAHUB_JUDGE_USERNAME": "ledgerlens-judge",
        "DATAHUB_JUDGE_PASSWORD": "judge-password-1234",
        "DATAHUB_SERVICE_USERNAME": "ledgerlens-service",
        "DATAHUB_SERVICE_PASSWORD": "service-password-1234",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    module.render_users(datahub_home)

    user_file = datahub_home / ".datahub/plugins/frontend/auth/user.props"
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(user_file.stat().st_mode) == 0o644
    assert user_file.read_text(encoding="utf-8").splitlines() == [
        "datahub:admin-password-1234",
        "ledgerlens-judge:judge-password-1234",
        "ledgerlens-service:service-password-1234",
    ]


def test_live_proof_cleanup_is_armed_before_quickstart() -> None:
    script = (ROOT / "deploy/live-proof/stack.sh").read_text(encoding="utf-8")
    armed = script.index("started_datahub=1")
    quickstart = script.index(
        "datahub_cli docker quickstart \\\n"
        '    --version "$DATAHUB_VERSION" \\\n'
        '    --quickstart-compose-file "$DATAHUB_COMPOSE_FILE"'
    )

    assert armed < quickstart
    assert "local started_datahub=0" not in script
    assert "local completed=0" not in script
    assert "--no-open-browser" not in script


def test_user_enablement_is_idempotent_and_auth_convergence_is_retried() -> None:
    provision_api = (ROOT / "deploy/bin/provision_datahub.py").read_text(encoding="utf-8")
    provision_shell = (ROOT / "deploy/bin/provision.sh").read_text(encoding="utf-8")

    assert "createIfEntityNotExists=false&createIfNotExists=false" in provision_api
    assert "createIfEntityNotExists=false&createIfNotExists=true" not in provision_api
    assert "createIfEntityNotExists=true&createIfNotExists=true" not in provision_api
    assert "init_datahub_token()" in provision_shell
    assert "Timed out waiting for DataHub %s authentication" in provision_shell


def test_user_enablement_upserts_active_corp_user_status(monkeypatch) -> None:
    module = _load_provision_datahub()
    requests: list[tuple[str, str, dict[str, object]]] = []

    class RecordingAPI:
        def request(self, method: str, path: str, payload: dict[str, object]) -> dict[str, object]:
            requests.append((method, path, payload))
            return {}

    monkeypatch.setattr(module.time, "time", lambda: 123.456)
    module.enable_user(RecordingAPI(), "ledgerlens-service")

    assert len(requests) == 2
    assert requests[0][1].endswith(
        "/status?async=false&systemMetadata=false"
        "&createIfEntityNotExists=false&createIfNotExists=false"
    )
    assert requests[1][1].endswith(
        "/corpUserStatus?async=false&systemMetadata=false"
        "&createIfEntityNotExists=false&createIfNotExists=false"
    )
    assert requests[1][2] == {
        "value": {
            "status": "ACTIVE",
            "lastModified": {
                "time": 123456,
                "actor": "urn:li:corpuser:datahub",
            },
        }
    }


def test_reader_verifier_allows_bounded_platform_reads_but_rejects_mutation(
    monkeypatch,
) -> None:
    module = _load_provision_datahub()
    allowed = {
        "platform": [
            "GENERATE_PERSONAL_ACCESS_TOKENS",
            "GET_ENTITY_PRIVILEGE",
            "SEARCH_PRIVILEGE",
            "VIEW_ENTITY_PAGE",
        ],
        "metadata": ["GET_ENTITY_PRIVILEGE", "VIEW_ENTITY_PAGE"],
    }
    monkeypatch.setattr(module, "granted_privileges", lambda *_: allowed)

    result = module.verify_reader(object(), "ledgerlens-judge", "urn:li:dataset:test")

    assert result["readOnlyVerified"] is True

    denied = {**allowed, "metadata": [*allowed["metadata"], "EDIT_ENTITY"]}
    monkeypatch.setattr(module, "granted_privileges", lambda *_: denied)
    with pytest.raises(SystemExit, match="metadata write privileges"):
        module.verify_reader(object(), "ledgerlens-judge", "urn:li:dataset:test")


def test_static_users_keep_policy_enforcement_with_documented_existence_mode() -> None:
    render_config = (ROOT / "deploy/bin/render_config.py").read_text(encoding="utf-8")

    assert '"METADATA_SERVICE_AUTH_ENFORCE_EXISTENCE_ENABLED": "false"' in render_config
    assert '"METADATA_SERVICE_AUTH_ENABLED": "true"' in render_config
    assert '"AUTH_POLICIES_ENABLED": "true"' in render_config
    assert '"REST_API_AUTHORIZATION": "true"' in render_config


def test_live_proof_seeds_parser_valid_public_fixture() -> None:
    provision_shell = (ROOT / "deploy/bin/provision.sh").read_text(encoding="utf-8")

    assert "uv run ledgerlens ingest docs/fixtures/failure-ledger-demo.md" in provision_shell
    assert "fixtures/sophia_failure_ledger_sanitized.md" not in provision_shell
    assert 'payload.get("dataset_urns")' in provision_shell
    assert '--resource-urn "$resource_urn"' in provision_shell
