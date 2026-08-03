# Contributing to LedgerLens

Thank you for helping build an honest, reproducible DataHub agent.

## Project status

LedgerLens is a contest-period working prototype. Contributions should improve the demonstrable
vertical slice without expanding claims beyond the evidence.

```yaml
candidateOnly: true
canClaimAGI: false
```

## Development setup

```bash
git clone https://github.com/tomyimkc/ledgerlens.git
cd ledgerlens
make setup
make check
```

Python 3.11 and 3.12 are supported. Default CI does not call paid APIs or start live DataHub.

**Reviewing the contest evidence?** Run `make judge-check` instead of `make check`. The two gates
overlap but are not the same: `judge-check` additionally runs `incident-benchmark` (the DataHub
context ON/OFF benchmark behind the submission's reported figures) and `non-video-readiness` (the
fail-closed evidence and submission-contract check), while it skips `build`. Use `make check` for
ordinary development and `make judge-check` to reproduce what the submission claims.

Useful targets:

```bash
make help
make test
make lint
make typecheck
make build
make secret-scan
make public-check
make demo
make benchmark
make judge-check        # full evidence gate — use this to verify submission claims
make incident-benchmark # DataHub context ON/OFF benchmark
```

## Contribution rules

1. Preserve source text and provenance.
2. Treat ledger content as untrusted input.
3. Reject duplicate IDs and structurally ambiguous rows.
4. Keep LLM and MCP mutations disabled by default.
5. Do not add credentials, private ledger rows, or unpublished holdouts.
6. Add deterministic tests for behavior changes.
7. Separate deterministic fixture results from live DataHub smoke results.
8. Do not describe this project as independent validation.
9. Never claim AGI, validated uplift, promotion, or production readiness from this prototype.
10. Disclose any pre-existing code or data incorporated into the project.

## Branch and pull-request workflow

- Create a focused branch from the latest `main`.
- Keep unrelated changes out of the branch.
- Run `make check` before opening a pull request.
- Include the commands and results actually run.
- Mark live-service tests as such; do not imply they ran if only fixture tests ran.
- Keep generated benchmark receipts small, sanitized, and reviewable.

## Tests

### Default deterministic checks

```bash
make check
```

This includes lint, unit tests, package build, secret scanning, and public-package checks. It must
remain network-free after dependencies are installed.

### Live DataHub smoke

```bash
make datahub-up
make live-smoke
make datahub-down
```

Live smoke results belong in a separate receipt and must include the exact DataHub version,
environment, command, commit, timestamp, and limitations.

## Benchmark reporting

Do not publish a bare pass rate. Every result must state:

- deterministic fixture or live DataHub;
- exact commit and command;
- test count and failures;
- wall-clock duration;
- environment and DataHub version where applicable;
- whether an LLM was enabled;
- whether external validation occurred;
- claim ceilings.

See [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Documentation style

- Write in clear English.
- Prefer concrete commands and bounded claims.
- Define “provenance,” “audit,” “supersession,” and “validation” precisely.
- Label screenshots and concept art accurately.
- Link to official DataHub documentation for external behavior.
- Avoid promotional language that outruns the recorded result.

## Security review

Before submitting code that handles source text, URLs, browser capture, or credentials, review
[SECURITY.md](SECURITY.md). Include tests for prompt injection, path traversal, malformed rows, or
redaction as appropriate.

## License

By contributing, you agree that your contribution may be distributed under Apache-2.0 and that you
have the right to submit any included code or data.
