"""Public-package, disclosure, fixture, and demo-contract checks."""

from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from ledgerlens.models import LedgerParseError
from ledgerlens.parser import parse_ledger_file

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PACKAGE_SCRIPT = ROOT / "scripts" / "check_public_package.py"
PUBLIC_PACKAGE_SPEC = importlib.util.spec_from_file_location(
    "check_public_package", PUBLIC_PACKAGE_SCRIPT
)
assert PUBLIC_PACKAGE_SPEC is not None and PUBLIC_PACKAGE_SPEC.loader is not None
PUBLIC_PACKAGE_MODULE = importlib.util.module_from_spec(PUBLIC_PACKAGE_SPEC)
PUBLIC_PACKAGE_SPEC.loader.exec_module(PUBLIC_PACKAGE_MODULE)
public_package_main = PUBLIC_PACKAGE_MODULE.main

REQUIRED_PUBLIC_PATHS = (
    "README.md",
    "LICENSE",
    "ARCHITECTURE.md",
    "DISCLOSURE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "Makefile",
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/hosted-smoke.yml",
    "scripts/check_hosted_incident_demo.py",
    "scripts/check_non_video_readiness.py",
    "docs/EVIDENCE_INDEX.md",
    "docs/WINNER_READINESS.md",
    "docs/DEVPOST_CHECKLIST.md",
    "docs/DEVPOST_SUBMISSION.md",
    "docs/DEVPOST_WRITEUP.md",
    "docs/BENCHMARKS.md",
    "docs/DATAHUB_QUICKSTART.md",
    "docs/EXTERNAL_EVALUATION.md",
    "docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md",
    "docs/LIVE_DATAHUB_PUBLIC.md",
    "docs/demo/DEMO_SCRIPT.md",
    "docs/demo/STORYBOARD.md",
    "docs/demo/RECORDING.md",
    "docs/fixtures/failure-ledger-demo.md",
    "docs/fixtures/failure-ledger-malformed.md",
)


@pytest.mark.parametrize("relative", REQUIRED_PUBLIC_PATHS)
def test_required_public_path_exists(relative: str) -> None:
    assert (ROOT / relative).is_file(), relative


@pytest.mark.parametrize(
    "relative",
    (
        "README.md",
        "ARCHITECTURE.md",
        "DISCLOSURE.md",
        "docs/DEVPOST_WRITEUP.md",
        "docs/BENCHMARKS.md",
    ),
)
def test_claim_boundary_is_explicit(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8").casefold()
    assert "working prototype" in text
    assert "independent validation" in text
    assert "candidateonly" in text
    assert "canclaimagi" in text


def test_disclosure_separates_preexisting_and_new_work() -> None:
    text = (ROOT / "DISCLOSURE.md").read_text(encoding="utf-8").casefold()
    assert "pre-existing material" in text
    assert "sophia-agi" in text
    assert "newly created in ledgerlens" in text
    assert "no prior datahub ledger adapter implementation is imported" in text


def test_public_fixture_parses_strictly() -> None:
    result = parse_ledger_file(
        ROOT / "docs/fixtures/failure-ledger-demo.md",
        strict=True,
    )
    assert result.is_valid
    assert len(result.findings) == 4
    assert all(finding.candidate_only for finding in result.findings)
    assert not any(finding.can_claim_agi for finding in result.findings)


def test_malformed_fixture_fails_closed() -> None:
    with pytest.raises(LedgerParseError) as captured:
        parse_ledger_file(
            ROOT / "docs/fixtures/failure-ledger-malformed.md",
            strict=True,
        )
    codes = {diagnostic.code for diagnostic in captured.value.result.errors}
    assert "duplicate_id" in codes
    assert "unsafe_unescaped_pipe" in codes
    assert "unbalanced_backticks" in codes


@pytest.mark.parametrize(
    ("name", "kind", "live"),
    (
        ("deterministic-fixture-template.json", "deterministic-fixture", False),
        ("live-datahub-smoke-template.json", "live-datahub-smoke", True),
    ),
)
def test_result_templates_are_not_claimed_runs(name: str, kind: str, live: bool) -> None:
    payload = json.loads((ROOT / "docs/results" / name).read_text(encoding="utf-8"))
    assert payload["benchmarkKind"] == kind
    assert payload["status"] == "NOT_RUN"
    assert payload["liveDataHub"] is live
    assert payload["externalValidation"] is False
    assert payload["candidateOnly"] is True
    assert payload["canClaimAGI"] is False


def test_public_package_reports_missing_documents_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "ledgerlens"
    shutil.copytree(
        ROOT,
        repository,
        ignore=shutil.ignore_patterns(".git", ".venv", "artifacts", "build", "dist"),
    )
    (repository / "docs" / "DEVPOST_SUBMISSION.md").unlink()
    (repository / "docs" / "EXTERNAL_EVALUATION.md").unlink()
    monkeypatch.setattr(PUBLIC_PACKAGE_MODULE, "ROOT", repository)

    assert public_package_main() == 1

    output = capsys.readouterr().out
    assert "missing required file: docs/DEVPOST_SUBMISSION.md" in output
    assert "missing required file: docs/EXTERNAL_EVALUATION.md" in output


def test_canonical_non_video_navigation_is_linked() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    submission = (ROOT / "docs/DEVPOST_SUBMISSION.md").read_text(encoding="utf-8")
    evidence = (ROOT / "docs/EVIDENCE_INDEX.md").read_text(encoding="utf-8")

    assert "docs/EVIDENCE_INDEX.md" in readme
    assert "docs/WINNER_READINESS.md" in readme
    assert "EVIDENCE_INDEX.md" in submission
    assert "docs/WINNER_READINESS.md" in submission
    assert "WINNER_READINESS.md" in evidence


def test_rubric_drift_detection_allows_unrelated_slash_24() -> None:
    assert not PUBLIC_PACKAGE_MODULE._has_six_core_rubric_drift("Demo network: 10.0.0.0/24.")
    assert PUBLIC_PACKAGE_MODULE._has_six_core_rubric_drift("Core total: 24 / 24")


def test_public_rubric_uses_five_core_plus_separate_bonus() -> None:
    for relative in (
        "README.md",
        "docs/DEVPOST_SUBMISSION.md",
        "docs/EXTERNAL_EVALUATION.md",
        "docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md",
        "docs/WINNER_READINESS.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        folded = text.casefold()
        assert "five core" in folded or "five-core" in folded, relative
        assert "bonus" in folded, relative
        assert "six equally weighted" not in folded, relative
        assert not PUBLIC_PACKAGE_MODULE._has_six_core_rubric_drift(text), relative


def test_ci_is_offline_first_and_has_both_python_versions() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert '"3.11"' in workflow
    assert '"3.12"' in workflow
    assert "ruff check" in workflow
    assert "uv run mypy src/ledgerlens" in workflow
    assert "pytest" in workflow
    assert "uv build" in workflow
    assert "check_secrets.py" in workflow
    assert "--extra video" in workflow
    assert "--extra datahub" in workflow
    assert "check_non_video_readiness.py" in workflow
    assert "datahub-up" not in workflow
    assert "SOPHIA_020S_KEY" not in workflow


def test_makefile_bootstraps_typecheck_and_demo_ui_contracts() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "uv sync --extra dev --extra web --extra video --extra datahub" in makefile
    assert "check: lint format-check typecheck test build secret-scan public-check" in makefile
    assert "--no-open-browser" not in makefile
    assert "non-video-readiness:" in makefile


def test_hosted_smoke_is_scheduled_and_credential_free() -> None:
    workflow = (ROOT / ".github/workflows/hosted-smoke.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "python3 scripts/check_hosted_incident_demo.py" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "secrets." not in workflow


def test_workflows_use_node24_action_majors() -> None:
    workflow_root = ROOT / ".github/workflows"
    workflow_paths = sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])
    assert workflow_paths
    expected_versions = {
        "actions/checkout@": "actions/checkout@v6",
        "actions/setup-python@": "actions/setup-python@v6",
        "actions/upload-artifact@": "actions/upload-artifact@v7",
        "astral-sh/setup-uv@": "astral-sh/setup-uv@v9.0.0",
    }
    for path in workflow_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- uses:"):
                stripped = stripped.removeprefix("- ").strip()
            if not stripped.startswith("uses:"):
                continue
            action_ref = stripped.removeprefix("uses:").strip()
            for action_prefix, expected in expected_versions.items():
                if action_ref.startswith(action_prefix):
                    assert action_ref == expected, f"{path}: {action_ref}"


def test_demo_script_is_under_three_minutes_and_requires_real_capture() -> None:
    script = (ROOT / "docs/demo/DEMO_SCRIPT.md").read_text(encoding="utf-8")
    storyboard = (ROOT / "docs/demo/STORYBOARD.md").read_text(encoding="utf-8")
    assert "approximately 41 seconds" in script
    assert "Hard maximum:** under 3 minutes" in script
    assert "real capture" in script.casefold()
    assert "synthetic" in storyboard.casefold()
    assert "must never contain fake" in storyboard.casefold()
    assert "below 15%" in storyboard
    assert "Burn English captions" in storyboard


def test_grok_prompts_are_concept_only() -> None:
    prompts = sorted((ROOT / "docs/demo/grok").glob("*.prompt.md"))
    assert len(prompts) >= 3
    for prompt in prompts:
        text = prompt.read_text(encoding="utf-8").casefold()
        assert "/imagine-video" in text
        assert "no fake" in text
        assert "no audio" in text


def test_shell_scripts_parse_and_are_executable() -> None:
    for script in sorted((ROOT / "scripts").rglob("*.sh")):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script}: {result.stderr}"
        assert script.stat().st_mode & stat.S_IXUSR, f"{script} is not executable"


def test_docker_defaults_are_read_only_and_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "USER ledgerlens" in dockerfile
    assert '".[web,datahub]"' in dockerfile
    assert "LEDGERLENS_MUTATIONS_ENABLED=false" in dockerfile
    assert ".env" in dockerignore.splitlines()
    assert "artifacts" in dockerignore.splitlines()
    assert ".git" in dockerignore.splitlines()
    assert ".claude" in dockerignore.splitlines()
    assert "read_only: true" in compose
    assert 'LEDGERLENS_MUTATIONS_ENABLED: "false"' in compose
    assert "DATAHUB_GMS_TOKEN:" in compose
    assert "DATAHUB_TOKEN:" not in compose
    assert "LEDGERLENS_ADAPTER_FACTORY:" not in compose
    assert "SOPHIA_020S_KEY:" not in compose
    assert 'DATAHUB_MCP_COMMAND: "${DATAHUB_MCP_COMMAND:-mcp-server-datahub}"' in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:8001:8000"' in compose
