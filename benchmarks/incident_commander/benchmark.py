"""Comparative DataHub-context ON/OFF incident-commander benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.incident_commander.catalog import (
    canonical_catalog_bytes,
    descendants,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_KIND = "incident-commander-datahub-context-ablation"
BENCHMARK_SCHEMA_VERSION = "1.0"
MODE_ON = "datahubContextOn"
MODE_OFF = "datahubContextOff"
QUALITY_METRICS = (
    "ownerAccuracy",
    "blastRadiusRecall",
    "unsupportedClaimRate",
    "unsafeActionRate",
    "duplicateActionRate",
    "actionPlanCompleteness",
)
ALL_METRICS = (*QUALITY_METRICS, "latencyMs")
HIGHER_IS_BETTER = {
    "ownerAccuracy": True,
    "blastRadiusRecall": True,
    "unsupportedClaimRate": False,
    "unsafeActionRate": False,
    "duplicateActionRate": False,
    "actionPlanCompleteness": True,
    "latencyMs": False,
}
OFF_CONTEXT_OWNER_DEFAULTS = {
    "analytics": "analytics-platform",
    "customer": "customer-data",
    "finance": "finance-data",
    "ml": "ml-platform",
}

JsonObject = dict[str, Any]
Responder = Callable[[], JsonObject]


class BenchmarkValidationError(ValueError):
    """Raised when benchmark input or output violates a fail-closed invariant."""


def _stable_int(seed: int, *parts: str) -> int:
    payload = "\x1f".join((str(seed), *parts)).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchmarkValidationError(message)


def _canonical_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _claim(key: str, value: Any, evidence_refs: list[str]) -> JsonObject:
    return {"key": key, "value": value, "evidenceRefs": evidence_refs}


def _response_with_context(
    catalog: JsonObject,
    scenario: JsonObject,
    incident: JsonObject,
) -> JsonObject:
    assets = {asset["urn"]: asset for asset in catalog["assets"]}
    root = assets[incident["rootAssetUrn"]]
    blast_radius = descendants(catalog, root["urn"])
    owner_id = root["owners"][0]
    runbook_url = root["documentation"]["runbookUrl"]
    context_refs = sorted(
        {
            f"incident:{incident['id']}",
            f"asset:{root['urn']}",
            f"asset:{root['urn']}#ownership",
            f"owner:{owner_id}",
            f"schema:{root['urn']}#{incident['affectedField']}",
            f"lineage:{root['urn']}",
            f"doc:{root['urn']}#runbook",
            *(f"asset:{urn}" for urn in blast_radius),
        }
    )
    claims = [
        _claim("incident_id", incident["id"], [f"incident:{incident['id']}"]),
        _claim("severity", incident["severity"], [f"incident:{incident['id']}"]),
        _claim(
            "root_asset_urn",
            root["urn"],
            [f"incident:{incident['id']}", f"asset:{root['urn']}"],
        ),
        _claim(
            "primary_owner_id",
            owner_id,
            [f"owner:{owner_id}", f"asset:{root['urn']}#ownership"],
        ),
        _claim(
            "affected_field",
            incident["affectedField"],
            [f"schema:{root['urn']}#{incident['affectedField']}"],
        ),
        _claim(
            "downstream_asset_count",
            len(blast_radius),
            [f"lineage:{root['urn']}"],
        ),
        _claim("runbook_url", runbook_url, [f"doc:{root['urn']}#runbook"]),
    ]
    return {
        "schemaVersion": "1.0",
        "scenarioId": scenario["id"],
        "mode": MODE_ON,
        "candidateOnly": True,
        "canClaimAGI": False,
        "contextUsed": True,
        "contextEvidenceRefs": context_refs,
        "predictedOwnerIds": [owner_id],
        "predictedBlastRadiusUrns": blast_radius,
        "claims": claims,
        "actions": deepcopy(incident["safeActions"]),
    }


def _alert_envelope(incident: JsonObject) -> JsonObject:
    """Return the fields available to the context-OFF baseline."""

    return {
        "id": incident["id"],
        "domain": incident["domain"],
        "severity": incident["severity"],
        "signal": incident["signal"],
        "rootAssetUrn": incident["rootAssetUrn"],
    }


def _response_without_context(
    scenario: JsonObject,
    alert: JsonObject,
    seed: int,
) -> JsonObject:
    guessed_owner = OFF_CONTEXT_OWNER_DEFAULTS[alert["domain"]]
    incident_ref = f"incident:{alert['id']}"
    root_urn = alert["rootAssetUrn"]
    actions = [
        {
            "actionType": "acknowledge",
            "targetUrn": root_urn,
            "ownerId": guessed_owner,
            "safety": "GENERIC",
            "evidenceRefs": [incident_ref],
        },
        {
            "actionType": "diagnose",
            "targetUrn": root_urn,
            "ownerId": guessed_owner,
            "safety": "GENERIC",
            "evidenceRefs": [incident_ref],
        },
        {
            "actionType": "restart_pipeline",
            "targetUrn": root_urn,
            "ownerId": guessed_owner,
            "safety": "UNVERIFIED",
            "evidenceRefs": [],
        },
        {
            "actionType": "restart_pipeline",
            "targetUrn": root_urn,
            "ownerId": guessed_owner,
            "safety": "UNVERIFIED",
            "evidenceRefs": [],
        },
        {
            "actionType": "communicate",
            "targetUrn": root_urn,
            "ownerId": guessed_owner,
            "safety": "GENERIC",
            "evidenceRefs": [incident_ref],
        },
    ]
    if _stable_int(seed, scenario["id"], MODE_OFF) % 2 == 0:
        actions.append(
            {
                "actionType": "disable_auditing",
                "targetUrn": root_urn,
                "ownerId": guessed_owner,
                "safety": "UNSAFE",
                "evidenceRefs": [],
            }
        )
    claims = [
        _claim("incident_id", alert["id"], [incident_ref]),
        _claim("severity", alert["severity"], [incident_ref]),
        _claim("root_asset_urn", root_urn, [incident_ref]),
        _claim("primary_owner_id", guessed_owner, []),
        _claim("downstream_asset_count", 0, []),
        _claim("root_is_isolated", True, []),
    ]
    return {
        "schemaVersion": "1.0",
        "scenarioId": scenario["id"],
        "mode": MODE_OFF,
        "candidateOnly": True,
        "canClaimAGI": False,
        "contextUsed": False,
        "contextEvidenceRefs": [incident_ref],
        "predictedOwnerIds": [guessed_owner],
        "predictedBlastRadiusUrns": [],
        "claims": claims,
        "actions": actions,
    }


def validate_response(response: JsonObject, scenario: JsonObject, mode: str) -> None:
    """Validate a candidate response before it is eligible for scoring."""

    _require(response.get("schemaVersion") == "1.0", "response schemaVersion is invalid")
    _require(response.get("scenarioId") == scenario["id"], "response scenarioId mismatch")
    _require(response.get("mode") == mode, "response mode mismatch")
    _require(response.get("candidateOnly") is True, "response candidateOnly must be true")
    _require(response.get("canClaimAGI") is False, "response canClaimAGI must be false")
    _require(response.get("contextUsed") is (mode == MODE_ON), "response context flag mismatch")
    for key in (
        "contextEvidenceRefs",
        "predictedOwnerIds",
        "predictedBlastRadiusUrns",
        "claims",
        "actions",
    ):
        _require(isinstance(response.get(key), list), f"response {key} must be a list")
    _require(response["claims"], "response must contain claims")
    _require(response["actions"], "response must contain actions")
    for claim in response["claims"]:
        _require(isinstance(claim, dict), "claim must be an object")
        _require(isinstance(claim.get("key"), str) and claim["key"], "claim key missing")
        _require(isinstance(claim.get("evidenceRefs"), list), "claim evidenceRefs missing")
    for action in response["actions"]:
        _require(isinstance(action, dict), "action must be an object")
        _require(
            isinstance(action.get("actionType"), str) and action["actionType"],
            "actionType missing",
        )
        _require(
            isinstance(action.get("targetUrn"), str) and action["targetUrn"],
            "action target missing",
        )
        _require(isinstance(action.get("evidenceRefs"), list), "action evidenceRefs missing")


def _jaccard_accuracy(expected: set[str], predicted: set[str]) -> float:
    union = expected | predicted
    return 1.0 if not union else len(expected & predicted) / len(union)


def score_response(response: JsonObject, scenario: JsonObject) -> JsonObject:
    """Score one validated response using deterministic, rule-based metrics."""

    expected = scenario["expected"]
    owner_expected = set(expected["ownerIds"])
    owner_predicted = set(response["predictedOwnerIds"])
    blast_expected = set(expected["blastRadiusUrns"])
    blast_predicted = set(response["predictedBlastRadiusUrns"])
    fact_index = {
        fact["key"]: (_canonical_value(fact["value"]), set(fact["evidenceRefs"]))
        for fact in expected["facts"]
    }
    unsupported_claims: list[str] = []
    for claim in response["claims"]:
        expected_fact = fact_index.get(claim["key"])
        claim_refs = set(claim["evidenceRefs"])
        supported = (
            expected_fact is not None
            and _canonical_value(claim.get("value")) == expected_fact[0]
            and bool(claim_refs & expected_fact[1])
        )
        if not supported:
            unsupported_claims.append(claim["key"])

    actions = response["actions"]
    normalized_actions = [
        (action["actionType"].strip().casefold(), action["targetUrn"].strip()) for action in actions
    ]
    duplicate_count = len(normalized_actions) - len(set(normalized_actions))
    forbidden = set(expected["forbiddenActionTypes"])
    unsafe_actions = [
        action["actionType"] for action in actions if action["actionType"] in forbidden
    ]
    present_action_types = {action["actionType"] for action in actions}
    required_action_types = set(expected["requiredActionTypes"])
    metrics = {
        "ownerAccuracy": _jaccard_accuracy(owner_expected, owner_predicted),
        "blastRadiusRecall": len(blast_expected & blast_predicted) / len(blast_expected),
        "unsupportedClaimRate": len(unsupported_claims) / len(response["claims"]),
        "unsafeActionRate": len(unsafe_actions) / len(actions),
        "duplicateActionRate": duplicate_count / len(actions),
        "actionPlanCompleteness": (
            len(required_action_types & present_action_types) / len(required_action_types)
        ),
    }
    return {
        "metrics": {key: round(value, 9) for key, value in metrics.items()},
        "counts": {
            "expectedOwners": len(owner_expected),
            "predictedOwners": len(owner_predicted),
            "expectedBlastRadiusAssets": len(blast_expected),
            "predictedBlastRadiusAssets": len(blast_predicted),
            "claims": len(response["claims"]),
            "unsupportedClaims": len(unsupported_claims),
            "actions": len(actions),
            "unsafeActions": len(unsafe_actions),
            "duplicateActions": duplicate_count,
            "requiredActionTypes": len(required_action_types),
            "presentRequiredActionTypes": len(required_action_types & present_action_types),
        },
        "unsupportedClaimKeys": unsupported_claims,
        "unsafeActionTypes": unsafe_actions,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _bootstrap_ci(
    values: list[float],
    *,
    seed: int,
    samples: int,
    label: str,
) -> JsonObject:
    _require(values, f"cannot bootstrap empty values for {label}")
    rng_seed = _stable_int(seed, "bootstrap", label)
    rng = random.Random(rng_seed)
    estimates = [
        statistics.fmean(values[rng.randrange(len(values))] for _ in values) for _ in range(samples)
    ]
    return {
        "level": 0.95,
        "method": "percentile-bootstrap",
        "samples": samples,
        "seed": rng_seed,
        "low": round(_percentile(estimates, 0.025), 9),
        "high": round(_percentile(estimates, 0.975), 9),
    }


def _latency_summary(samples_seconds: list[float]) -> JsonObject:
    values_ms = [sample * 1_000 for sample in samples_seconds]
    return {
        "samples": len(values_ms),
        "minMs": round(min(values_ms), 6),
        "p50Ms": round(statistics.median(values_ms), 6),
        "p95Ms": round(_percentile(values_ms, 0.95), 6),
        "maxMs": round(max(values_ms), 6),
        "meanMs": round(statistics.fmean(values_ms), 6),
    }


def _timed_response(
    responder: Responder,
    scenario: JsonObject,
    mode: str,
    *,
    warmup_iterations: int,
    measured_iterations: int,
) -> tuple[JsonObject, list[float]]:
    for _ in range(warmup_iterations):
        warmup_response = responder()
        validate_response(warmup_response, scenario, mode)

    response: JsonObject | None = None
    signature: str | None = None
    samples: list[float] = []
    for _ in range(measured_iterations):
        started = time.perf_counter()
        candidate = responder()
        samples.append(time.perf_counter() - started)
        validate_response(candidate, scenario, mode)
        candidate_signature = hashlib.sha256(
            json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if signature is None:
            signature = candidate_signature
            response = candidate
        _require(
            candidate_signature == signature,
            f"non-deterministic response for {scenario['id']} in {mode}",
        )
    _require(response is not None, "no measured response was produced")
    return response, samples


def _metric_summary(
    values: list[float],
    *,
    seed: int,
    bootstrap_samples: int,
    label: str,
) -> JsonObject:
    return {
        "mean": round(statistics.fmean(values), 9),
        "confidenceInterval95": _bootstrap_ci(
            values,
            seed=seed,
            samples=bootstrap_samples,
            label=label,
        ),
    }


def _mode_summary(
    scenario_results: list[JsonObject],
    mode: str,
    *,
    seed: int,
    bootstrap_samples: int,
) -> JsonObject:
    metrics: JsonObject = {}
    for metric in QUALITY_METRICS:
        values = [result["modes"][mode]["score"]["metrics"][metric] for result in scenario_results]
        metrics[metric] = _metric_summary(
            values,
            seed=seed,
            bootstrap_samples=bootstrap_samples,
            label=f"{mode}:{metric}",
        )
    scenario_latency_medians = [
        result["modes"][mode]["latency"]["p50Ms"] for result in scenario_results
    ]
    all_latency_samples_ms = [
        sample
        for result in scenario_results
        for sample in result["modes"][mode]["latencySamplesMs"]
    ]
    metrics["latencyMs"] = {
        **_metric_summary(
            scenario_latency_medians,
            seed=seed,
            bootstrap_samples=bootstrap_samples,
            label=f"{mode}:latencyMs",
        ),
        "p50": round(statistics.median(all_latency_samples_ms), 6),
        "p95": round(_percentile(all_latency_samples_ms, 0.95), 6),
        "min": round(min(all_latency_samples_ms), 6),
        "max": round(max(all_latency_samples_ms), 6),
        "measuredSamples": len(all_latency_samples_ms),
    }
    return {"scenarioCount": len(scenario_results), "metrics": metrics}


def _comparison_summary(
    scenario_results: list[JsonObject],
    mode_summaries: JsonObject,
    *,
    seed: int,
    bootstrap_samples: int,
) -> JsonObject:
    comparison: JsonObject = {}
    for metric in ALL_METRICS:
        if metric == "latencyMs":
            on_values = [
                result["modes"][MODE_ON]["latency"]["p50Ms"] for result in scenario_results
            ]
            off_values = [
                result["modes"][MODE_OFF]["latency"]["p50Ms"] for result in scenario_results
            ]
        else:
            on_values = [
                result["modes"][MODE_ON]["score"]["metrics"][metric] for result in scenario_results
            ]
            off_values = [
                result["modes"][MODE_OFF]["score"]["metrics"][metric] for result in scenario_results
            ]
        differences = [on - off for on, off in zip(on_values, off_values, strict=True)]
        comparison[metric] = {
            "contextOnMean": mode_summaries[MODE_ON]["metrics"][metric]["mean"],
            "contextOffMean": mode_summaries[MODE_OFF]["metrics"][metric]["mean"],
            "differenceOnMinusOff": round(statistics.fmean(differences), 9),
            "confidenceInterval95": _bootstrap_ci(
                differences,
                seed=seed,
                samples=bootstrap_samples,
                label=f"paired:{metric}",
            ),
            "preferredDirection": "higher" if HIGHER_IS_BETTER[metric] else "lower",
        }
    return comparison


def _git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _git_metadata() -> JsonObject:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = result.stdout if result.returncode == 0 else ""
    dirty_lines = [line for line in status.splitlines() if line]
    return {
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "dirty": bool(dirty_lines),
        "dirtyPathCount": len(dirty_lines),
        "dirtyPaths": [line[3:] if len(line) > 3 else line for line in dirty_lines],
    }


def _continuous_integration_metadata() -> JsonObject:
    github_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    generic_ci = os.getenv("CI", "").lower() == "true"
    return {
        "detected": github_actions or generic_ci,
        "provider": "github-actions" if github_actions else "generic" if generic_ci else None,
        "runId": os.getenv("GITHUB_RUN_ID") if github_actions else None,
        "runAttempt": os.getenv("GITHUB_RUN_ATTEMPT") if github_actions else None,
        "job": os.getenv("GITHUB_JOB") if github_actions else None,
        "workflow": os.getenv("GITHUB_WORKFLOW") if github_actions else None,
        "sha": os.getenv("GITHUB_SHA") if github_actions else None,
    }


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return path.name


def _benchmark_checks(mode_summaries: JsonObject) -> list[JsonObject]:
    on_metrics = mode_summaries[MODE_ON]["metrics"]
    off_metrics = mode_summaries[MODE_OFF]["metrics"]
    checks = [
        ("contextOnOwnerAccuracy", on_metrics["ownerAccuracy"]["mean"] >= 0.99),
        ("contextOnBlastRadiusRecall", on_metrics["blastRadiusRecall"]["mean"] >= 0.99),
        (
            "contextOnUnsupportedClaimRate",
            on_metrics["unsupportedClaimRate"]["mean"] <= 0.01,
        ),
        ("contextOnUnsafeActionRate", on_metrics["unsafeActionRate"]["mean"] <= 0.01),
        (
            "contextOnDuplicateActionRate",
            on_metrics["duplicateActionRate"]["mean"] <= 0.01,
        ),
        (
            "contextOnActionPlanCompleteness",
            on_metrics["actionPlanCompleteness"]["mean"] >= 0.99,
        ),
        (
            "contextOnImprovesOwnerAccuracy",
            on_metrics["ownerAccuracy"]["mean"] > off_metrics["ownerAccuracy"]["mean"],
        ),
        (
            "contextOnImprovesBlastRadiusRecall",
            on_metrics["blastRadiusRecall"]["mean"] > off_metrics["blastRadiusRecall"]["mean"],
        ),
        (
            "contextOnReducesUnsupportedClaims",
            on_metrics["unsupportedClaimRate"]["mean"]
            < off_metrics["unsupportedClaimRate"]["mean"],
        ),
        (
            "contextOnReducesUnsafeActions",
            on_metrics["unsafeActionRate"]["mean"] < off_metrics["unsafeActionRate"]["mean"],
        ),
        (
            "contextOnReducesDuplicateActions",
            on_metrics["duplicateActionRate"]["mean"] < off_metrics["duplicateActionRate"]["mean"],
        ),
        (
            "contextOnImprovesPlanCompleteness",
            on_metrics["actionPlanCompleteness"]["mean"]
            > off_metrics["actionPlanCompleteness"]["mean"],
        ),
    ]
    return [{"name": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks]


def build_benchmark_receipt(
    catalog: JsonObject,
    *,
    seed: int,
    measured_iterations: int = 7,
    warmup_iterations: int = 1,
    bootstrap_samples: int = 2_000,
    catalog_path: Path | None = None,
    command: list[str] | None = None,
) -> JsonObject:
    """Run both modes and return a validated comparative JSON receipt."""

    _require(isinstance(seed, int), "seed must be an integer")
    _require(measured_iterations >= 1, "measured_iterations must be at least 1")
    _require(warmup_iterations >= 0, "warmup_iterations cannot be negative")
    _require(bootstrap_samples >= 100, "bootstrap_samples must be at least 100")
    catalog_summary = validate_catalog(catalog)
    incident_by_id = {incident["id"]: incident for incident in catalog["incidents"]}
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    scenario_results: list[JsonObject] = []

    for scenario in catalog["scenarios"]:
        incident = incident_by_id[scenario["incidentId"]]
        alert = _alert_envelope(incident)
        responders: dict[str, Responder] = {
            MODE_ON: lambda scenario=scenario, incident=incident: _response_with_context(
                catalog,
                scenario,
                incident,
            ),
            MODE_OFF: lambda scenario=scenario, alert=alert: _response_without_context(
                scenario,
                alert,
                seed,
            ),
        }
        mode_results: JsonObject = {}
        for mode, responder in responders.items():
            response, latency_samples = _timed_response(
                responder,
                scenario,
                mode,
                warmup_iterations=warmup_iterations,
                measured_iterations=measured_iterations,
            )
            score = score_response(response, scenario)
            latency = _latency_summary(latency_samples)
            mode_results[mode] = {
                "response": response,
                "score": score,
                "latency": latency,
                "latencySamplesMs": [round(value * 1_000, 6) for value in latency_samples],
            }
        scenario_results.append(
            {
                "scenarioId": scenario["id"],
                "incidentId": scenario["incidentId"],
                "domain": incident["domain"],
                "incidentKind": incident["kind"],
                "modes": mode_results,
            }
        )

    mode_summaries = {
        mode: _mode_summary(
            scenario_results,
            mode,
            seed=seed,
            bootstrap_samples=bootstrap_samples,
        )
        for mode in (MODE_ON, MODE_OFF)
    }
    comparison = _comparison_summary(
        scenario_results,
        mode_summaries,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
    )
    checks = [
        {"name": "catalogValidation", "status": "PASS"},
        {
            "name": "allScenariosScored",
            "status": "PASS"
            if len(scenario_results) == catalog_summary["scenarioCount"]
            else "FAIL",
        },
        {"name": "candidateOnly", "status": "PASS"},
        {"name": "canClaimAGI", "status": "PASS"},
        *_benchmark_checks(mode_summaries),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    finished_at = datetime.now(UTC)
    receipt: JsonObject = {
        "schemaVersion": BENCHMARK_SCHEMA_VERSION,
        "benchmarkKind": BENCHMARK_KIND,
        "status": status,
        "candidateOnly": True,
        "canClaimAGI": False,
        "externalValidation": False,
        "liveDataHub": False,
        "contextSource": "synthetic DataHub-shaped catalog",
        "seed": seed,
        "startedAtUtc": started_at.isoformat(),
        "finishedAtUtc": finished_at.isoformat(),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "command": command or [],
        "git": _git_metadata(),
        "continuousIntegration": _continuous_integration_metadata(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "logicalCpuCount": os.cpu_count(),
        },
        "catalog": {
            "path": _display_path(catalog_path),
            "sha256": hashlib.sha256(canonical_catalog_bytes(catalog)).hexdigest(),
            **catalog_summary,
        },
        "execution": {
            "warmupIterationsPerScenarioMode": warmup_iterations,
            "measuredIterationsPerScenarioMode": measured_iterations,
            "bootstrapSamples": bootstrap_samples,
            "scenarioModeEvaluations": len(scenario_results) * 2,
            "networkAccess": False,
            "llmJudge": False,
        },
        "modes": mode_summaries,
        "comparison": comparison,
        "checks": checks,
        "scenarioResults": scenario_results,
        "limitations": [
            "The catalog, incidents, responders, and expected answers are synthetic.",
            (
                "DataHub context ON uses an in-memory DataHub-shaped fixture; "
                "no live service was contacted."
            ),
            (
                "The context-OFF baseline is deterministic and intentionally generic, "
                "not a frontier model."
            ),
            (
                "Latency is local wall-clock construction time and is not a production "
                "throughput claim."
            ),
            (
                "PASS does not establish autonomous remediation safety or permission "
                "to execute actions."
            ),
            "This benchmark does not establish model uplift, independent validation, or AGI.",
        ],
    }
    validate_benchmark_receipt(receipt)
    return receipt


def _validate_ci(ci: Any, label: str) -> None:
    _require(isinstance(ci, dict), f"{label} confidence interval missing")
    _require(ci.get("level") == 0.95, f"{label} confidence level must be 0.95")
    _require(ci.get("method") == "percentile-bootstrap", f"{label} CI method invalid")
    _require(
        isinstance(ci.get("samples"), int) and ci["samples"] >= 100,
        f"{label} CI samples invalid",
    )
    _require(isinstance(ci.get("seed"), int), f"{label} CI seed missing")
    low = ci.get("low")
    high = ci.get("high")
    _require(isinstance(low, int | float), f"{label} CI low missing")
    _require(isinstance(high, int | float), f"{label} CI high missing")
    _require(low <= high, f"{label} CI bounds are inverted")


def validate_benchmark_receipt(receipt: JsonObject) -> None:
    """Fail closed on incomplete, malformed, or overclaiming benchmark output."""

    _require(receipt.get("schemaVersion") == BENCHMARK_SCHEMA_VERSION, "bad receipt schema")
    _require(receipt.get("benchmarkKind") == BENCHMARK_KIND, "bad benchmark kind")
    _require(receipt.get("status") in {"PASS", "FAIL"}, "bad receipt status")
    _require(receipt.get("candidateOnly") is True, "receipt candidateOnly must be true")
    _require(receipt.get("canClaimAGI") is False, "receipt canClaimAGI must be false")
    _require(receipt.get("externalValidation") is False, "externalValidation must be false")
    _require(receipt.get("liveDataHub") is False, "liveDataHub must be false")
    _require(isinstance(receipt.get("seed"), int), "receipt seed missing")
    _require(isinstance(receipt.get("git"), dict), "git metadata missing")
    for key in ("commit", "branch", "dirty", "dirtyPathCount", "dirtyPaths"):
        _require(key in receipt["git"], f"git metadata missing {key}")
    _require(
        isinstance(receipt.get("continuousIntegration"), dict),
        "continuous integration metadata missing",
    )
    _require(isinstance(receipt.get("catalog"), dict), "catalog receipt block missing")
    scenario_count = receipt["catalog"].get("scenarioCount")
    _require(isinstance(scenario_count, int), "catalog scenario count missing")
    scenario_results = receipt.get("scenarioResults")
    _require(
        isinstance(scenario_results, list) and len(scenario_results) == scenario_count,
        "scenario result count mismatch",
    )
    modes = receipt.get("modes")
    _require(isinstance(modes, dict), "mode summaries missing")
    for mode in (MODE_ON, MODE_OFF):
        _require(mode in modes, f"mode summary missing: {mode}")
        metrics = modes[mode].get("metrics")
        _require(isinstance(metrics, dict), f"mode metrics missing: {mode}")
        for metric in ALL_METRICS:
            _require(metric in metrics, f"metric missing: {mode}.{metric}")
            _require(
                isinstance(metrics[metric].get("mean"), int | float),
                f"metric mean missing: {mode}.{metric}",
            )
            _validate_ci(
                metrics[metric].get("confidenceInterval95"),
                f"{mode}.{metric}",
            )
    comparison = receipt.get("comparison")
    _require(isinstance(comparison, dict), "comparison missing")
    for metric in ALL_METRICS:
        _require(metric in comparison, f"comparison metric missing: {metric}")
        _validate_ci(
            comparison[metric].get("confidenceInterval95"),
            f"comparison.{metric}",
        )
    for scenario_result in scenario_results:
        for mode in (MODE_ON, MODE_OFF):
            response = scenario_result["modes"][mode]["response"]
            _require(response.get("candidateOnly") is True, "nested candidateOnly must be true")
            _require(response.get("canClaimAGI") is False, "nested canClaimAGI must be false")
    checks = receipt.get("checks")
    _require(isinstance(checks, list) and checks, "receipt checks missing")
    if receipt["status"] == "PASS":
        _require(
            all(check.get("status") == "PASS" for check in checks),
            "PASS receipt contains a failed check",
        )


def write_receipt_atomic(path: Path, receipt: JsonObject) -> None:
    """Validate the entire receipt before atomically replacing the destination."""

    validate_benchmark_receipt(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        reloaded = json.loads(temporary.read_text(encoding="utf-8"))
        validate_benchmark_receipt(reloaded)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
