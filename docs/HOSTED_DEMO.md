# Hosted LedgerLens + DataHub OSS Judge Environment

## Status

This package defines a temporary, single-tenant public judge environment for the LedgerLens
Incident Commander replay and DataHub OSS catalog. It is deliberately not described as a
production deployment.

The deterministic Incident Commander replay is currently public at
`https://tomyimkc-ledgerlens-incident-commander.hf.space/`. The Docker-VM package described below
is the optional path for a separate live DataHub OSS judge environment.

```yaml
candidateOnly: true
canClaimAGI: false
judgeAccess: read-only
llmEnabled: false
incidentCommanderMode: fixture-replay
externalActions: false
```

The deployment uses:

- the official DataHub OSS `v1.6.0` quickstart compose, downloaded and SHA-256 verified at deploy
  time;
- a generated hardened copy that binds every DataHub/backend port to `127.0.0.1`;
- the repository's non-root LedgerLens image;
- Caddy as the only public ingress on ports 80/443;
- Caddy basic authentication plus a native DataHub **Reader** account;
- a separate DataHub Reader identity and short-lived PAT for LedgerLens/MCP;
- deterministic catalog ingestion performed once by the private root operator;
- autonomous Incident Commander **fixture replay** with visibly synthetic receipts;
- baseline backup/restore for scenario resets;
- a host-side TTL watchdog that stops services without deleting state.

## What is and is not exposed

| Surface | Public | Authentication | Mutation authority |
|---|---:|---|---|
| LedgerLens Incident Commander | Yes, HTTPS | Caddy judge credential | Replayed fanout only; no live provider/DataHub mutation |
| DataHub frontend | Yes, HTTPS | Caddy + DataHub judge credential | DataHub Reader role |
| DataHub GMS `8080` | No | Loopback + token | Operator/service only |
| MySQL `3306` | No | Loopback only | Not shared |
| Kafka `9092` | No | Loopback only | Not shared |
| OpenSearch `9200` | No | Loopback only | Not shared |
| SSH | Operator only | SSH key + pinned host key | Host administration |

The generated DataHub compose enables metadata-service authentication, policy enforcement, and
REST API authorization. It rotates the immutable `datahub` root password through a private
`user.props`, creates separate judge/service users, assigns both the built-in Reader role, and
deactivates the editable all-users platform policy after the service PAT is issued. The health
gate asks DataHub for the effective privileges of both identities and rejects any non-read
metadata privilege or any platform privilege.

## Cloud assumptions

The repository currently has no confirmed VM-provider credential. Cloudflare Wrangler
authentication alone is not sufficient to create a VM, configure its firewall, or guarantee that
DNS records can be managed. Therefore:

1. VM creation and DNS are explicit owner operations.
2. The GitHub workflow stays `workflow_dispatch` only.
3. Remote operations run only when the `judge-demo` GitHub Environment contains a verified SSH
   key and `known_hosts` entry.
4. No workflow attempts to infer AWS, GCP, Azure, Fly.io, DigitalOcean, or Cloudflare Tunnel
   authority.

Cloudflare DNS or Access may be added later, but the base design needs only two public DNS names
pointing to a Docker-capable VM.

## VM baseline

The official DataHub quickstart documents a tested minimum of 2 CPUs, 8 GB RAM, 2 GB swap, and
13 GB disk. For a public judge window, use this safer starting point:

| Resource | Recommended |
|---|---:|
| CPU | 4 vCPU |
| RAM | 16 GB |
| Swap | 2-4 GB |
| Disk | 40 GB SSD |
| OS | Current Ubuntu LTS or comparable Linux |
| Inbound firewall | SSH from operator IPs, TCP 80, TCP/UDP 443 only |

Do **not** allow public access to ports 3306, 8080, 9002, 9092, 9200, or 4319. The generated
compose binds them to loopback as defense in depth, but the cloud security group/firewall remains
mandatory.

## Host prerequisites

Install:

- Docker Engine and Docker Compose v2;
- Git;
- `curl`;
- `uv`;
- Python 3.11 or 3.12;
- at least 20 GB free disk before deployment.

Create a dedicated deploy user that can run Docker and owns the release root:

```bash
sudo install -d -o ledgerlens -g ledgerlens /opt/ledgerlens-judge
```

The deployment scripts do not install packages, change firewall rules, add Docker users, or delete
volumes.

## DNS and TLS

Create two DNS records pointing at the VM:

```text
ledgerlens.example.org  -> VM public IP
datahub.example.org     -> VM public IP
```

Caddy obtains and renews public TLS certificates after DNS resolves and ports 80/443 reach the
VM. Use distinct names because DataHub's frontend is not deployed under a path prefix.

## Secrets

Copy the template only on the VM:

```bash
cp deploy/.env.example deploy/judge.env
chmod 600 deploy/judge.env
```

Generate independent random passwords. DataHub native passwords cannot contain `:` or newline
characters because they are rendered into `user.props`.

Generate the Caddy bcrypt hash without writing the plaintext password to the repository:

```bash
docker run --rm caddy:2.10.2-alpine \
  caddy hash-password --plaintext 'the-gateway-password'
```

Required secret groups:

| Secret | Shared with judges? | Purpose |
|---|---:|---|
| `JUDGE_GATEWAY_USERNAME/PASSWORD` | Yes | First HTTPS perimeter prompt |
| `DATAHUB_JUDGE_USERNAME/PASSWORD` | Yes | Native DataHub Reader login |
| `DATAHUB_ADMIN_PASSWORD` | No | Rotated root/bootstrap identity |
| `DATAHUB_SERVICE_PASSWORD` | No | Issues the Reader PAT used by LedgerLens |
| `JUDGE_VM_SSH_KEY` | No | GitHub-to-VM deployment |
| `JUDGE_VM_KNOWN_HOSTS` | No | Prevents SSH host-key bypass |

The generated service token, DataHub local signing keys, `user.props`, backups, and Caddy config
live under `deploy/state/` locally or the workflow's shared state directory remotely. The whole
state directory is ignored.

## Manual deployment

From a clean checkout on the VM:

```bash
export JUDGE_ENV_FILE="$PWD/deploy/judge.env"
export DEPLOY_STATE_DIR="$PWD/deploy/state"
bash deploy/bin/up.sh
```

`up.sh` performs these gates in order:

1. validates commands, secrets, FQDNs, TTL, RAM, and free disk;
2. installs the locked DataHub project dependencies with `uv`;
3. downloads the official `v1.6.0` quickstart compose and verifies its pinned SHA-256;
4. renders the loopback-only authenticated DataHub compose, `user.props`, Caddy config, and
   Compose environment;
5. validates Compose and Caddy configuration;
6. starts the DataHub quickstart and waits for GMS/frontend health;
7. creates judge and service users and assigns the Reader role;
8. ingests only `fixtures/sophia_failure_ledger_sanitized.md` with the private root token;
9. issues the service PAT, disables the all-users platform policy, and verifies effective
   privileges;
10. starts LedgerLens and Caddy;
11. records a baseline DataHub backup;
12. arms automatic shutdown and runs internal/public health checks.

The quickstart can take several minutes on a fresh VM because Docker image pulls dominate startup.

## Judge instructions

Share exactly four values:

1. LedgerLens URL;
2. DataHub URL;
3. gateway username/password;
4. DataHub judge username/password.

Do not share the root password, service password, service token, SSH details, state directory, or
GitHub Environment settings.

Suggested first pass:

1. Open LedgerLens and confirm the live status says DataHub and MCP are connected.
2. Open the remediation queue.
3. inspect a missing-owner/evidence case;
4. trace the parser finding's supersession chain;
5. download the JSON report;
6. open DataHub with the Reader credential and inspect the same dataset, ownership, tags, custom
   properties, and lineage.

## Resettable scenarios

All scenarios begin from the same immutable sanitized DataHub snapshot. They differ only in the
judge walkthrough, so comparisons do not depend on hidden or mutable data.

```bash
bash deploy/bin/reset-scenario.sh baseline
bash deploy/bin/reset-scenario.sh missing-metadata
bash deploy/bin/reset-scenario.sh supersession
```

Reset restores `deploy/state/scenarios/baseline.sql`, restarts LedgerLens, records the active
scenario, and reruns health/authorization checks. DataHub quickstart backups do not include all
timeseries data; these scenarios rely only on the metadata entities/aspects seeded by LedgerLens.

Scenario guides:

- `deploy/scenarios/baseline.md`
- `deploy/scenarios/missing-metadata.md`
- `deploy/scenarios/supersession.md`

## Health and operations

```bash
# Internal containers, public HTTPS, DataHub users, and effective privileges
bash deploy/bin/healthcheck.sh

# Stop without deleting volumes/backups
bash deploy/bin/down.sh
```

Health passes only when:

- GMS and the DataHub login page are reachable on loopback;
- the LedgerLens container reports Docker health `healthy`;
- the judge and service identities have no platform privileges;
- every effective metadata privilege is read-only;
- the LedgerLens public `/healthz` endpoint succeeds through Caddy auth/TLS;
- the DataHub login page succeeds through Caddy auth/TLS.

For diagnostics:

```bash
docker compose \
  --env-file deploy/state/compose.env \
  -f deploy/docker-compose.judge.yml ps

HOME="$PWD/deploy/state/datahub-home" \
  uv run datahub docker quickstart \
    --quickstart-compose-file deploy/state/datahub-compose.judge.yml \
    --dump-logs-on-failure
```

Do not paste logs publicly until authorization headers, cookies, tokens, domains, and personal
paths have been reviewed.

## Cost controls

- Default TTL is 24 hours; accepted range is 1-168 hours.
- The host watchdog records an absolute deadline and stops both stacks without deleting state.
- Re-deploying writes a new deadline; stale watchdogs read the current deadline rather than
  stopping a newer deployment early.
- The workflow uses one concurrency group and does not cancel an in-progress deploy.
- DataHub is pinned instead of following latest images.
- LedgerLens LLM narration is disabled, so no paid model key or inference spend is required.
- Release directories are immutable; cleanup is an explicit owner action.
- Provider billing alerts and provider-native auto-stop should still be configured manually.

Stopping containers does not necessarily stop VM billing. After judging, the owner must stop or
delete the VM through the provider console.

## GitHub Environment setup

Create a protected GitHub Environment named `judge-demo`. Require approval and restrict deployment
to `main`.

SSH secrets:

- `JUDGE_VM_HOST`
- `JUDGE_VM_PORT` (optional; defaults to 22)
- `JUDGE_VM_USER`
- `JUDGE_VM_SSH_KEY`
- `JUDGE_VM_KNOWN_HOSTS`

Application secrets:

- `LEDGERLENS_FQDN`
- `DATAHUB_FQDN`
- `CADDY_ACME_EMAIL`
- `JUDGE_GATEWAY_USERNAME`
- `JUDGE_GATEWAY_PASSWORD`
- `JUDGE_GATEWAY_PASSWORD_HASH`
- `DATAHUB_ADMIN_PASSWORD`
- `DATAHUB_JUDGE_USERNAME` (optional; default `ledgerlens-judge`)
- `DATAHUB_JUDGE_PASSWORD`
- `DATAHUB_SERVICE_USERNAME` (optional; default `ledgerlens-service`)
- `DATAHUB_SERVICE_PASSWORD`

Run **Deploy LedgerLens judge demo** manually and choose `validate`, `deploy`, `health`, `reset`, or
`stop`. Remote operations:

- accept only `workflow_dispatch`;
- refuse non-`main` refs;
- require a pinned SSH host key;
- fail if required secrets are absent;
- upload an immutable release directory;
- preserve shared state across releases;
- never use `StrictHostKeyChecking=no`;
- never provision a cloud resource or DNS record.

## Teardown and destructive cleanup

Normal stop is reversible:

```bash
bash deploy/bin/down.sh
```

Deleting DataHub volumes, Caddy state, backups, or release directories is intentionally not
automated. If the owner chooses to destroy them, first save any required receipts and then use the
official DataHub cleanup guidance plus provider controls. Do not run broad Docker prune commands on
a shared host.

## Security limitations

- This is a temporary contest/judge environment, not a hardened multi-tenant service.
- The DataHub Reader role can read all metadata in this dedicated instance. Seed only sanitized
  public fixture data.
- Caddy basic authentication is an additional perimeter, not a replacement for DataHub
  authorization.
- Anyone with the shared judge credentials can download the public demo reports.
- The deployment does not fetch evidence URLs or send ledger text to an LLM.
- A successful health gate proves configured connectivity and effective privileges at that time,
  not production security certification.
