"""Tests for the deterministic DataHub-context incident benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.incident_commander.benchmark import (  # noqa: E402
    MODE_OFF,
    MODE_ON,
    BenchmarkValidationError,
    build_benchmark_receipt,
    validate_benchmark_receipt,
    write_receipt_atomic,
)
from benchmarks.incident_commander.catalog import load_catalog  # noqa: E402

CATALOG_PATH = ROOT / "fixtures/incident_commander/catalog.json"


@pytest.fixture(scope="module")
def receipt() -> dict[str, object]:
    catalog = load_catalog(CATALOG_PATH)
    return build_benchmark_receipt(
        catalog,
        seed=catalog["generator"]["seed"],
        measured_iterations=2,
        warmup_iterations=0,
        bootstrap_samples=100,
        catalog_path=CATALOG_PATH,
        command=["pytest", "incident-commander"],
    )


def test_context_on_outperforms_off_with_safe_complete_plans(
    receipt: dict[str, object],
) -> None:
    validate_benchmark_receipt(receipt)
    assert receipt["status"] == "PASS"
    assert receipt["candidateOnly"] is True
    assert receipt["canClaimAGI"] is False
    modes = receipt["modes"]
    on_metrics = modes[MODE_ON]["metrics"]
    off_metrics = modes[MODE_OFF]["metrics"]

    assert on_metrics["ownerAccuracy"]["mean"] == 1.0
    assert on_metrics["blastRadiusRecall"]["mean"] == 1.0
    assert on_metrics["unsupportedClaimRate"]["mean"] == 0.0
    assert on_metrics["unsafeActionRate"]["mean"] == 0.0
    assert on_metrics["duplicateActionRate"]["mean"] == 0.0
    assert on_metrics["actionPlanCompleteness"]["mean"] == 1.0

    assert on_metrics["ownerAccuracy"]["mean"] > off_metrics["ownerAccuracy"]["mean"]
    assert on_metrics["blastRadiusRecall"]["mean"] > off_metrics["blastRadiusRecall"]["mean"]
    assert on_metrics["unsupportedClaimRate"]["mean"] < off_metrics["unsupportedClaimRate"]["mean"]
    assert on_metrics["unsafeActionRate"]["mean"] < off_metrics["unsafeActionRate"]["mean"]
    assert on_metrics["duplicateActionRate"]["mean"] < off_metrics["duplicateActionRate"]["mean"]
    assert (
        on_metrics["actionPlanCompleteness"]["mean"] > off_metrics["actionPlanCompleteness"]["mean"]
    )


def test_receipt_has_seed_confidence_intervals_and_execution_metadata(
    receipt: dict[str, object],
) -> None:
    assert receipt["seed"] == 20260731
    assert receipt["catalog"]["assetCount"] == 120
    assert receipt["catalog"]["scenarioCount"] == 24
    assert receipt["catalog"]["sha256"]
    assert receipt["git"]["commit"]
    assert "branch" in receipt["git"]
    assert isinstance(receipt["git"]["dirty"], bool)
    assert isinstance(receipt["git"]["dirtyPaths"], list)
    assert "detected" in receipt["continuousIntegration"]

    for metric, comparison in receipt["comparison"].items():
        ci = comparison["confidenceInterval95"]
        assert ci["level"] == 0.95, metric
        assert ci["method"] == "percentile-bootstrap", metric
        assert ci["samples"] == 100, metric
        assert isinstance(ci["seed"], int), metric
        assert ci["low"] <= ci["high"], metric


def test_each_scenario_contains_auditable_outputs(receipt: dict[str, object]) -> None:
    scenario_results = receipt["scenarioResults"]
    assert len(scenario_results) == 24
    for result in scenario_results:
        for mode in (MODE_ON, MODE_OFF):
            mode_result = result["modes"][mode]
            response = mode_result["response"]
            assert response["candidateOnly"] is True
            assert response["canClaimAGI"] is False
            assert response["claims"]
            assert response["actions"]
            assert len(mode_result["latencySamplesMs"]) == 2
            assert mode_result["latency"]["samples"] == 2
            assert set(mode_result["score"]["metrics"]) == {
                "ownerAccuracy",
                "blastRadiusRecall",
                "unsupportedClaimRate",
                "unsafeActionRate",
                "duplicateActionRate",
                "actionPlanCompleteness",
            }


def test_receipt_validator_rejects_overclaim_and_atomic_writer_preserves_file(
    receipt: dict[str, object],
    tmp_path: Path,
) -> None:
    output = tmp_path / "receipt.json"
    output.write_text('{"sentinel": true}\n', encoding="utf-8")
    invalid = deepcopy(receipt)
    invalid["canClaimAGI"] = True

    with pytest.raises(BenchmarkValidationError, match="canClaimAGI"):
        write_receipt_atomic(output, invalid)

    assert json.loads(output.read_text(encoding="utf-8")) == {"sentinel": True}


def test_cli_fails_closed_on_invalid_catalog(tmp_path: Path) -> None:
    catalog = load_catalog(CATALOG_PATH)
    catalog["candidateOnly"] = False
    invalid_catalog = tmp_path / "invalid-catalog.json"
    invalid_catalog.write_text(json.dumps(catalog), encoding="utf-8")
    output = tmp_path / "must-not-exist.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_incident_commander_benchmark.py"),
            "--catalog",
            str(invalid_catalog),
            "--output",
            str(output),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--bootstrap-samples",
            "100",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "candidateOnly must be true" in result.stderr
    assert not output.exists()
