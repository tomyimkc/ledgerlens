# Pinned DataHub OSS Quickstart

LedgerLens uses the external DataHub OSS quickstart for development and live smoke testing. It does
not vendor or silently start DataHub during default tests.

Pinned default:

```text
DataHub OSS v1.6.0
```

The pin is an integration target, not a production recommendation.

## Requirements

- Docker installed and running
- at least 8 GB memory available to Docker
- at least 2 CPUs
- sufficient free disk for DataHub images
- Python 3.11 or 3.12 for LedgerLens
- DataHub CLI installed through the project `datahub` extra or separately

The official quickstart is intended for local development and testing, not production.

## Start

```bash
make setup
make datahub-up
make datahub-status
```

Equivalent helper command:

```bash
scripts/datahub_quickstart.sh up
```

Override the pin explicitly:

```bash
DATAHUB_VERSION=v1.6.0 make datahub-up
```

Do not change the version in a published receipt without recording it.

## Expected endpoints

| Service | Default URL |
|---|---|
| DataHub frontend | `http://localhost:9002` |
| DataHub GMS | `http://localhost:8080` |

The helper waits for the GMS config endpoint and writes no credentials.

## Smoke test

```bash
make live-smoke
```

The live smoke should:

1. confirm GMS health;
2. ingest the sanitized fixture;
3. retrieve at least one entity;
4. retrieve a supersession edge;
5. obtain and label audit metadata;
6. write a live-smoke receipt;
7. keep `candidateOnly: true` and `canClaimAGI: false`.

If the application integration is unavailable, the command must fail rather than substituting a
fixture-only result.

## Official MCP Server

The official DataHub MCP Server is a separate process. It is not a route under GMS. For local OSS,
configure the server to point at the frontend/base DataHub URL and keep mutation tools disabled.

Illustrative client configuration:

```json
{
  "mcpServers": {
    "datahub": {
      "command": "npx",
      "args": ["-y", "@datahub/mcp-server"],
      "env": {
        "DATAHUB_BASE_URL": "http://localhost:9002",
        "TOOLS_IS_MUTATION_ENABLED": "false"
      }
    }
  }
}
```

Use the exact package/configuration supported by the currently pinned project implementation and
record its version in the live receipt. Do not add a token to checked-in configuration.

## Stop and cleanup

```bash
make datahub-down
```

This invokes the official quickstart stop command. Destructive cleanup, volume deletion, or image
pruning is intentionally not automated.

## Troubleshooting

### Docker memory or health failures

Check:

```bash
docker info
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Increase Docker memory if containers repeatedly restart or fail health checks.

### Port collision

Inspect:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:9002 -sTCP:LISTEN
```

Do not stop unrelated processes automatically.

### GMS is not ready

```bash
curl --fail --silent http://localhost:8080/config
```

The helper uses a bounded wait and reports failure. It does not turn an unhealthy deployment into a
passing result.

### Datapack/sample-data issue

If a documented datapack resource is missing from an installed wheel, record the exact CLI version
and error. Do not patch the installed package silently. Use only the documented fallback supported
by the pinned DataHub release and keep that issue separate from the LedgerLens result.

## Receipt discipline

A live receipt must include:

- UTC timestamp;
- git commit;
- dirty-tree state;
- OS and architecture;
- Python version;
- DataHub CLI/version;
- DataHub OSS version;
- MCP package/version;
- exact command;
- passed/failed checks;
- output artifact hashes;
- `externalValidation: false`;
- `candidateOnly: true`;
- `canClaimAGI: false`.
