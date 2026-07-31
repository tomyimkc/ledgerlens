"""Focused tests for the lazy, deterministic LedgerLens CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from ledgerlens import cli

runner = CliRunner()


def test_help_lists_required_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "validate",
        "ingest",
        "explain",
        "supersession",
        "triage",
        "demo",
        "serve",
    ):
        assert command in result.stdout


def test_validate_demo_is_explicit_and_deterministic() -> None:
    result = runner.invoke(cli.app, ["validate", "--demo", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "demo"
    assert payload["valid"] is True
    assert payload["finding_count"] == 4
    assert payload["candidateOnly"] is True
    assert payload["canClaimAGI"] is False


def test_explain_and_supersession_demo() -> None:
    finding_id = "ledger-validator-blind-spots-2026-07-26"

    explanation = runner.invoke(
        cli.app,
        ["explain", finding_id, "--demo", "--format", "json"],
    )
    chain = runner.invoke(
        cli.app,
        ["supersession", finding_id, "--demo", "--format", "json"],
    )

    assert explanation.exit_code == 0
    explanation_payload = json.loads(explanation.stdout)
    assert explanation_payload["finding"]["id"] == finding_id
    assert "independently validate" in explanation_payload["explanation"]

    assert chain.exit_code == 0
    chain_payload = json.loads(chain.stdout)
    assert chain_payload["requested_id"] == finding_id
    assert chain_payload["current_id"] == "strict-parser-fixture-suite-2026-07-31"
    assert [item["id"] for item in chain_payload["chain"]] == [
        "ledger-validator-blind-spots-2026-07-26",
        "strict-parser-fixture-suite-2026-07-31",
    ]


def test_missing_demo_finding_has_clear_error() -> None:
    result = runner.invoke(cli.app, ["explain", "does-not-exist", "--demo"])

    assert result.exit_code == 2
    assert "Finding not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_live_command_requires_source_before_adapter_resolution() -> None:
    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 2
    assert "source path is required" in result.stderr
    assert "--demo" in result.stderr


def test_injected_adapter_is_lazy_and_secrets_are_redacted(tmp_path: Path) -> None:
    source = tmp_path / "ledger.md"
    source.write_text("# fixture\n", encoding="utf-8")
    calls: list[tuple[bool, Path | None]] = []

    class Adapter:
        def validate(self, received: Path | None) -> dict[str, Any]:
            calls.append((False, received))
            return {
                "valid": True,
                "api_token": "must-not-leak",
                "diagnostic": "Authorization: Bearer super-secret-value",
            }

    def factory(demo: bool) -> Adapter:
        calls.append((demo, None))
        return Adapter()

    cli.set_adapter_factory(factory)
    try:
        result = runner.invoke(
            cli.app,
            ["validate", str(source), "--format", "json"],
        )
    finally:
        cli.set_adapter_factory(None)

    assert result.exit_code == 0
    assert calls == [(False, None), (False, source)]
    assert "must-not-leak" not in result.stdout
    assert "super-secret-value" not in result.stdout
    assert result.stdout.count("[REDACTED]") == 2


def test_triage_report_refuses_to_overwrite(tmp_path: Path) -> None:
    report = tmp_path / "triage.json"
    report.write_text("keep me", encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["triage", "--demo", "--format", "json", "--output", str(report)],
    )

    assert result.exit_code == 2
    assert "Refusing to overwrite" in result.stderr
    assert report.read_text(encoding="utf-8") == "keep me"


def test_triage_markdown_contains_claim_boundary() -> None:
    result = runner.invoke(cli.app, ["triage", "--demo", "--format", "markdown"])

    assert result.exit_code == 0
    assert "# LedgerLens remediation queue" in result.stdout
    assert "Remediation queue" in result.stdout
    assert "candidateOnly: true" in result.stdout
    assert "canClaimAGI: false" in result.stdout


def test_demo_command_injects_fixture_mode_without_starting_server(monkeypatch: Any) -> None:
    received: dict[str, Any] = {}

    def fake_server(**kwargs: Any) -> None:
        received.update(kwargs)

    monkeypatch.setattr(cli, "_run_server", fake_server)
    result = runner.invoke(cli.app, ["demo", "--no-open-browser", "--port", "8123"])

    assert result.exit_code == 0
    assert "DEMO FIXTURE mode" in result.stdout
    assert received == {
        "host": "127.0.0.1",
        "port": 8123,
        "demo_mode": True,
        "open_browser": False,
    }
