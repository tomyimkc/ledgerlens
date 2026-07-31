# Minimal Upstream DataHub MCP Provenance Contribution Plan

## Research snapshot

Researched on **July 31, 2026** against the official public repository:

- repository: `acryldata/mcp-server-datahub`
- default branch: `main`
- inspected HEAD: `9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`
- package: `mcp-server-datahub`
- local LedgerLens integration pin: `0.6.0`
- license: Apache-2.0

No upstream checkout was edited.

Relevant current structure:

```text
src/mcp_server_datahub/
  mcp_server.py
  graphql_helpers.py
  gql/entity_details.gql
  tools/entities.py
tests/
  conftest.py
  test_mcp/test_get_entities.py
  test_mcp/test_read_only.py
README.md
DEVELOPING.md
```

Current behavior:

- `get_entities` is decorated read-only and returns cleaned GraphQL entity details.
- the GraphQL entity fragment includes business/entity fields, ownership, tags, structured
  properties, lineage-related context, and selected entity-specific created/modified fields;
- it does not expose the per-aspect envelope `systemMetadata` needed to distinguish DataHub
  ingestion/observation metadata from domain-event or source-validation time;
- the installed DataHub graph client already exposes `get_entity_raw(urn, aspects)`, whose aspect
  envelopes can include system metadata;
- `mcp_server.py` states that it is synchronized across two repositories, so the smallest first PR
  should avoid a new tool registration unless maintainers request it.

The repository search performed for `provenance`, `audit`, `systemMetadata`, and `lastIngested`
found no open public issue in the official MCP repository at the time of research.

## User problem

Agents inspecting a DataHub entity may need to answer:

- when did DataHub last observe or ingest this aspect?
- which ingestion run wrote it?
- which registry/version emitted it?
- is that timestamp metadata-system provenance or a business/source event?

Today a client must bypass the MCP tool and call a separate API/SDK surface. That creates a
provenance gap and encourages agents to flatten unrelated timestamp semantics.

The proposal must **not** label DataHub ingestion time as validation, certification, source-event
time, or evidence review.

## Recommended issue

Title:

```text
Expose optional read-only aspect system metadata from get_entities
```

Suggested issue body:

> `get_entities` provides rich cleaned entity metadata but not per-aspect envelope provenance such
> as `systemMetadata.lastObserved` and `systemMetadata.runId`. The DataHub graph client already
> exposes `get_entity_raw(urn, aspects)`, so clients currently need a second non-MCP API path to
> retrieve these fields.
>
> Would maintainers accept an opt-in `provenance_aspects` parameter on `get_entities`? When supplied,
> the tool would fetch only the named aspects and attach a compact `aspectProvenance` object
> containing an allowlisted subset of envelope audit/system metadata. Default behavior and response
> size would remain unchanged.
>
> Proposed semantics: these fields describe DataHub metadata ingestion/observation and must not be
> presented as business-event or source-validation timestamps.
>
> Proposed scope: `tools/entities.py`, mocked `test_get_entities.py` coverage, and README
> documentation. No mutation, no raw aspect values, no token/header exposure, no new tool
> registration.

Questions for maintainers:

1. Prefer an optional `get_entities` parameter or a separate `get_entity_provenance` tool?
2. Which `systemMetadata` fields are considered stable for public MCP output?
3. Should audit stamps be included when present in the raw aspect envelope?
4. Does the mirrored internal repository require a maintainer-side sync step?

## Recommended minimal PR

Proposed title:

```text
feat: add opt-in aspect provenance to get_entities
```

### File 1: `src/mcp_server_datahub/tools/entities.py`

Extend the existing signature:

```python
def get_entities(
    urns: List[str] | str,
    provenance_aspects: Optional[List[str]] = None,
) -> List[dict] | dict:
```

Contract:

- `None` keeps current behavior byte-for-byte compatible.
- A non-empty list requests provenance for only those aspect names.
- Reject more than 20 aspects.
- Reject blank, duplicate, or non-identifier-like aspect names.
- Reuse the existing authenticated client:

```python
raw = client._graph.get_entity_raw(urn, aspects=provenance_aspects)
```

- Read only `raw["aspects"][aspect_name]`.
- Do **not** return `value` or the raw envelope.
- Attach a compact field to each successful entity:

```json
{
  "aspectProvenance": {
    "datasetProperties": {
      "found": true,
      "auditStamp": {
        "time": 1700000000000,
        "actor": "urn:li:corpuser:ingestor"
      },
      "systemMetadata": {
        "lastObserved": 1700000000100,
        "runId": "ledgerlens-run",
        "registryName": "datahub",
        "registryVersion": "1.6.0"
      },
      "timestampSemantic": "datahub_metadata_ingestion_or_observation"
    }
  }
}
```

Allowlist only:

- audit: `time`, `actor`, `lastModifiedBy`;
- system metadata: `lastObserved`, `runId`, `registryName`, `registryVersion`;
- fixed semantic label owned by the MCP server.

Do not include:

- aspect values;
- headers, cookies, access tokens, server URLs, or request details;
- arbitrary unknown system-metadata fields;
- a field named `validatedAt`, `verifiedAt`, or equivalent.

Batch behavior:

- successful entities receive their own `aspectProvenance`;
- one raw-aspect failure follows existing batch semantics and returns an error for that URN without
  failing unrelated URNs;
- single-URN behavior continues to raise on failure, matching current `get_entities`.

Why this file-only implementation is preferred initially:

- no new tool registration;
- no change to `mcp_server.py`, which is mirrored across repositories;
- no GraphQL fragment expansion;
- no default token-cost increase;
- no dependency change.

### File 2: `tests/test_mcp/test_get_entities.py`

Add mocked tests:

1. `provenance_aspects=None` never calls `get_entity_raw` and preserves current output.
2. One aspect returns only the allowlisted audit/system fields.
3. Raw aspect `value` is absent from the MCP output.
4. Unknown system metadata is discarded.
5. Missing requested aspect returns `{"found": false}`.
6. Multiple URNs receive separate provenance.
7. A single-URN raw fetch error raises.
8. A batch raw fetch error becomes an error result only for that URN.
9. Empty/blank/duplicate/over-limit aspect lists fail validation.
10. The returned timestamp semantic explicitly says DataHub metadata
    ingestion/observation—not validation.

Use the existing test compatibility imports (`datahub_integrations.mcp...`) so the same tests
continue to work in both repository layouts.

### File 3: `README.md`

Under `get_entities`, document:

- the optional parameter;
- one compact example;
- read-only/default-off behavior;
- the semantic warning;
- the 20-aspect bound.

### Optional file: `CHANGELOG.md`

Add a one-line unreleased entry only if requested by maintainers. Do not expand the PR solely to
reformat or reorganize the changelog.

## Tests and gates

Run:

```bash
uv sync --dev
uv run pytest -q tests/test_mcp/test_get_entities.py
make lint-check
```

If the upstream `make test` target still requires a live DataHub instance, run it only after the
mocked unit scope is green and record the exact DataHub version/configuration:

```bash
make test
```

Additional manual MCP Inspector check:

1. call `get_entities` without `provenance_aspects` and compare with current output;
2. call with `["datasetProperties", "ownership"]`;
3. confirm only compact envelope metadata appears;
4. confirm the tool annotation remains `readOnlyHint: true`;
5. confirm mutation tools remain disabled.

## Non-goals

Keep out of the first PR:

- any LedgerLens-specific field names or claim ceilings;
- evidence validation or trust scoring;
- a generic raw-aspect dump;
- aspect values already returned by `get_entities`;
- mutation tools;
- audit history/timeline pagination;
- OpenAPI-v3 fallback code;
- DataHub Cloud-only fields;
- telemetry changes;
- refactors of GraphQL cleaning/token-budget code;
- changes to the separate DataHub repository;
- changes to the mirrored internal repository without maintainer direction.

## Alternative if maintainers prefer a new tool

If the issue response rejects a parameter on `get_entities`, propose:

```text
get_entity_provenance(urn: str, aspects: List[str]) -> dict
```

Then the minimal files become:

- new `src/mcp_server_datahub/tools/provenance.py`;
- `src/mcp_server_datahub/mcp_server.py` import and registration with search/read-only tags;
- `src/mcp_server_datahub/tools/__init__.py` export if required by convention;
- new `tests/test_mcp/tools/test_provenance.py`;
- `README.md`;
- mirrored-repository sync coordinated by maintainers.

This alternative is semantically cleaner but operationally larger. The issue should settle the
tool-shape decision before code is written.

## Contribution sequence

1. Open the issue with the exact default-off proposal and semantic boundary.
2. Wait for maintainer preference on parameter versus separate tool.
3. Fork the official repository only after scope agreement.
4. Implement the smallest accepted shape.
5. Add mocked tests before any live integration run.
6. Run lint and targeted tests.
7. Run the live suite only if required and record the DataHub version.
8. Open one PR that references the issue.
9. Respond to review without adding LedgerLens-specific behavior.
10. Keep LedgerLens's audit bridge until an upstream release containing the feature is published
    and verified; do not switch to an unreleased commit in the contest deployment.

## Acceptance criteria

The contribution is ready when:

- current clients see no default response change;
- requested provenance is read-only, bounded, and allowlisted;
- timestamp semantics cannot reasonably be read as source validation;
- raw aspect values and credentials cannot leak;
- single/batch error behavior matches existing `get_entities`;
- tests run in the standalone repository compatibility layout;
- maintainers confirm the mirrored-source workflow;
- the change ships in an official release before LedgerLens removes its separate audit bridge.
