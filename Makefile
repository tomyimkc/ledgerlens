SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PYTHON_VERSION ?= 3.12
DATAHUB_VERSION ?= v1.6.0
DATAHUB_GMS_URL ?= http://localhost:8080
DATAHUB_FRONTEND_URL ?= http://localhost:9002
PLAYWRIGHT_VERSION ?= 1.62.1
DEMO_URL ?= http://localhost:8000
DATAHUB_ENTITY_URL ?= http://localhost:9002/search?query=ledgerlens.failure_ledger
DATAHUB_DEMO_USERNAME ?= datahub
DATAHUB_DEMO_PASSWORD ?= datahub

.PHONY: help setup sync-ci lint format-check typecheck test build secret-scan public-check \
	check demo demo-ui benchmark benchmark-summary datahub-up datahub-down datahub-status \
	live-smoke docker-build docker-demo video-tools capture-demo grok-assets render-video \
	montage-demo verify-video clean-generated incident-demo incident-demo-headless \
	incident-demo-manual incident-benchmark incident-benchmark-real-pipeline \
	incident-catalog-bundle ai-rehearsal judge-check submission-consistency \
	hosted-smoke non-video-readiness

help: ## Show available targets.
	@awk 'BEGIN {FS = ":.*## "; printf "LedgerLens targets:\\n\\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-20s %s\\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install all developer, web, and DataHub extras with uv.
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 2; }
	uv python install $(PYTHON_VERSION)
	uv sync --all-extras
	@echo "Setup complete. Run 'make demo' for the deterministic workflow."

sync-ci: ## Install only dependencies required by default offline-first CI.
	uv python install $(PYTHON_VERSION)
	uv sync --extra dev --extra web --extra video --extra datahub

lint: ## Run Ruff over source, tests, and public automation.
	uv run ruff check src tests scripts

format-check: ## Check Ruff formatting without modifying files.
	uv run ruff format --check src tests scripts

typecheck: ## Run strict mypy checks.
	uv run mypy src/ledgerlens

test: ## Run deterministic tests; live DataHub tests are excluded.
	uv run pytest -m "not live_datahub"

build: ## Build source and wheel distributions.
	uv build

secret-scan: ## Run an offline high-confidence secret safety scan.
	uv run python scripts/check_secrets.py

public-check: ## Validate public files, claims, fixtures, shell syntax, and result templates.
	uv run python scripts/check_public_package.py
	uv run pytest -q tests/test_public_package.py

check: lint format-check typecheck test build secret-scan public-check ## Run the default contest-quality gate.

demo: ## Generate deterministic validation, ingestion, triage, and supersession artifacts.
	uv run bash scripts/deterministic_demo.sh

demo-ui: ## Serve the visibly labeled deterministic demo UI at localhost:8000.
	uv run ledgerlens demo --host 127.0.0.1 --port 8000

incident-demo: ## Launch the autonomous, visibly labeled Incident Commander fixture replay.
	uv run bash scripts/demo_incident_commander.sh

incident-demo-headless: ## Launch autonomous Incident Commander without opening a browser.
	LEDGERLENS_OPEN_BROWSER=false uv run bash scripts/demo_incident_commander.sh

incident-demo-manual: ## Launch Incident Commander with exact operator authorization.
	LEDGERLENS_AUTONOMOUS=false uv run bash scripts/demo_incident_commander.sh

incident-benchmark: ## Run the deterministic DataHub-context ON versus OFF benchmark.
	uv run python scripts/run_incident_commander_benchmark.py \
		--output benchmarks/incident_commander/context-ablation-receipt.json

incident-benchmark-real-pipeline: ## Run the DataHub ON/OFF ablation through the real PolicyGate.
	uv run python scripts/run_real_pipeline_ablation.py \
		--output benchmarks/incident_commander/real-pipeline-ablation-receipt.json

incident-catalog-bundle: ## Build the 120-asset DataHub proposal bundle without mutation.
	uv run python scripts/ingest_incident_catalog.py \
		--output artifacts/incident-commander/datahub-catalog-bundle.json

ai-rehearsal: ## Run the live 020s planner + verifier panel without external mutations.
	uv run python scripts/run_incident_ai_rehearsal.py --force

hosted-smoke: ## Verify the public fixture replay and write a sanitized receipt.
	uv run python scripts/check_hosted_incident_demo.py \
		--output artifacts/hosted-smoke/receipt.json

non-video-readiness: ## Fail closed on missing non-video evidence, CI, or submission contracts.
	uv run python scripts/check_non_video_readiness.py

submission-consistency: ## Fail closed when judge-facing values drift from the artifacts.
	uv run python scripts/check_submission_consistency.py

reproduce-upstream-mcp-pr: ## Reproduce upstream DataHub MCP PR #160's own checks (clones an external repo; not in CI).
	uv run python scripts/reproduce_upstream_mcp_pr.py \
		--output benchmarks/upstream_mcp_contribution/pr-160-reproduction-receipt.json

judge-check: lint format-check typecheck test secret-scan public-check incident-benchmark \
	incident-benchmark-real-pipeline non-video-readiness submission-consistency ## Run judge-facing quality and evidence gates.

benchmark: ## Record a deterministic fixture benchmark receipt.
	uv run python scripts/run_benchmark.py \
		--kind deterministic-fixture \
		--output artifacts/benchmarks/deterministic-fixture.json \
		-- uv run bash scripts/deterministic_benchmark.sh

benchmark-summary: ## Render available benchmark receipts as Markdown.
	uv run python scripts/render_benchmark_summary.py \
		--input artifacts/benchmarks \
		--output artifacts/benchmarks/SUMMARY.md

datahub-up: ## Start the pinned external DataHub OSS quickstart.
	DATAHUB_VERSION=$(DATAHUB_VERSION) uv run bash scripts/datahub_quickstart.sh up

datahub-down: ## Stop the DataHub OSS quickstart without deleting volumes or images.
	DATAHUB_VERSION=$(DATAHUB_VERSION) uv run bash scripts/datahub_quickstart.sh down

datahub-status: ## Check DataHub GMS and frontend reachability.
	DATAHUB_GMS_URL=$(DATAHUB_GMS_URL) DATAHUB_FRONTEND_URL=$(DATAHUB_FRONTEND_URL) \
		uv run bash scripts/datahub_quickstart.sh status

live-smoke: ## Run and record an explicit live DataHub integration smoke.
	DATAHUB_GMS_URL=$(DATAHUB_GMS_URL) DATAHUB_FRONTEND_URL=$(DATAHUB_FRONTEND_URL) \
		DATAHUB_VERSION=$(DATAHUB_VERSION) uv run bash scripts/live_datahub_smoke.sh

docker-build: ## Build the non-root LedgerLens container.
	docker build --tag ledgerlens:local .

docker-demo: ## Run the deterministic demo container through Compose.
	docker compose up --build ledgerlens-demo

video-tools: ## Install isolated Playwright capture tooling under ignored artifacts/.
	PLAYWRIGHT_VERSION=$(PLAYWRIGHT_VERSION) bash scripts/video/install_capture_tools.sh

capture-demo: ## Capture real LedgerLens/DataHub browser footage using the configured plan.
	LEDGERLENS_DEMO_URL=$(DEMO_URL) DATAHUB_FRONTEND_URL=$(DATAHUB_FRONTEND_URL) \
		DATAHUB_ENTITY_URL='$(DATAHUB_ENTITY_URL)' \
		DATAHUB_DEMO_USERNAME='$(DATAHUB_DEMO_USERNAME)' \
		DATAHUB_DEMO_PASSWORD='$(DATAHUB_DEMO_PASSWORD)' \
		bash scripts/video/capture_real_ui.sh

montage-demo: ## Build a clean motion montage from the verified real UI screenshots.
	bash scripts/video/build_real_ui_montage.sh

grok-assets: ## Launch reviewed Grok CLI prompts for optional labeled concept clips.
	bash scripts/video/generate_grok_assets.sh

render-video: ## Render the real UI proof video, narration, captions, and optional labeled concepts.
	bash scripts/video/render_demo.sh

verify-video: ## Verify final video duration, dimensions, codecs, and receipt.
	uv run python scripts/video/verify_video.py artifacts/video/ledgerlens-demo.mp4

clean-generated: ## Remove only ignored LedgerLens-generated artifacts and build outputs.
	@echo "Removing generated artifacts/, dist/, and build/ only."
	uv run python -c 'import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ("artifacts", "dist", "build")]'
