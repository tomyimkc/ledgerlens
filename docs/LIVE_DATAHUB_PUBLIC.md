# Live DataHub Public Proof

## Decision

The strongest feasible no-new-paid-resource proof is:

1. keep the existing Hugging Face Incident Commander as the stable public replay;
2. run the hardened live DataHub OSS stack on the already-running `pro6000-cf` physical
   workstation;
3. expose only loopback-bound, basic-authenticated LedgerLens/DataHub gateways through temporary
   Cloudflare Quick Tunnels;
4. stop the tunnels and stack immediately after recording or judging.

This is a temporary working-prototype proof, not a production deployment. It does not establish
independent validation, source truth, incident recovery, validated uplift, or AGI.

```yaml
candidateOnly: true
canClaimAGI: false
externalValidation: false
publicMode: temporary-authenticated-quick-tunnel
paidResourceProvisioned: false
```

## Audit scope and result

Audit performed July 31, 2026. Only credential/configuration names, authentication status, public
HTTP status, and non-secret resource capacity were inspected. No credential value was printed or
recorded, no paid resource was provisioned, and no remote configuration was changed.

### Currently available capability

| Surface | Read-only finding | Consequence |
|---|---|---|
| GitHub | `gh` is authenticated with repository/workflow access | Existing manual workflows can be inspected or dispatched after owner review |
| GitHub `hf-space` Environment | Secret name `HF_TOKEN`; variable name `HF_SPACE_REPO_ID` | The existing free Space deployment path is configured |
| GitHub `judge-demo` Environment | Absent; no `JUDGE_VM_*`, DNS, or application secret names are configured | The SSH VM workflow cannot safely deploy today |
| Hugging Face | The configured Space redirects `/` to `/incident` with HTTP 307; `/healthz` and `/incident` return HTTP 200 | Keep it as the stable replay surface |
| Local Cloudflare | `cloudflared` 2026.7.2 is installed; Wrangler authentication succeeds | Account-backed Cloudflare operations may be possible, but are unnecessary for a Quick Tunnel |
| Local Cloudflare named-tunnel auth | No default `cert.pem`/named-tunnel management context; Cloudflare Access SSH artifacts are present | Local Quick Tunnels work without reusing named-tunnel credentials |
| `pro6000-cf` | Existing SSH credential works through Cloudflare Access | The workstation can be used without creating a VM |
| `pro6000-cf` capacity | Physical ASUS host, Docker reachable, 32 CPUs, about 123.5 GiB RAM, about 42.8 GiB free disk | It clears the repository's 8 GiB RAM/20 GiB free-disk gates, but disk headroom must be watched |
| `pro6000-cf` Cloudflare | A running named tunnel, `cert.pem`, and named-tunnel listing authority exist; six tunnel names are visible | Stable DNS routing is technically possible, but the existing tunnel is shared and must not be edited casually |
| RunPod | No `RUNPOD_API_KEY` environment/file name and no RunPod CLI were found; the workstation has no RunPod marker | Do not use RunPod for this proof |
| Tailscale | Client installed but backend stopped; Serve/Funnel not configured | Enabling Funnel would change external state and is not the shortest path |
| ngrok | Not installed/configured | Not available |
| Local Mac | Docker reachable, 48 GiB RAM, about 200 GiB free disk; DataHub ports 8080/9002 free | Good fallback, but depends on the recording laptop remaining awake and online |

Credential values were intentionally not inspected. The remote Cloudflare credential JSON and
certificate contents were not opened.

### Reversible tunnel validation

The DataHub-only Quick Tunnel path was exercised end to end against a disposable loopback HTTP
origin:

- the Caddy configuration validated;
- the loopback gateway returned HTTP 401 without credentials;
- a random `trycloudflare.com` URL was created;
- the public URL returned HTTP 401 without credentials;
- `status` reported the owned gateway and tunnel as running;
- `stop` removed the owned gateway and terminated the recorded tunnel process;
- the test ports were free afterward.

The disposable origin contained no repository or DataHub data. The URL was stopped immediately.
The full DataHub stack was not launched during this audit, and no paid resource was created.

## Options evaluated

### 1. Existing physical workstation + Cloudflare Quick Tunnels — recommended

**Why it wins**

- no VM needs to be created;
- the workstation is already powered on and reachable;
- no GPU is required and LedgerLens LLM calls remain disabled;
- DataHub and LedgerLens stay on loopback;
- Quick Tunnels create random temporary HTTPS URLs without DNS or a Cloudflare account token;
- the new scripts add a Caddy basic-auth boundary before any public tunnel;
- shutdown is reversible and preserves DataHub state/receipts.

Cloudflare describes Quick Tunnels as a development/testing feature with no SLA or uptime
guarantee. They are therefore suitable for a supervised recording/judge window, not a durable
submission URL. Quick Tunnels also do not work when a default
`~/.cloudflared/config.yml`/`config.yaml` is present; the preflight refuses that case.

### 2. Existing named Cloudflare tunnel — technically stronger, not automatically safe

A dedicated named tunnel and DNS hostnames would provide stable URLs and better judge ergonomics.
The available remote `cert.pem` appears sufficient to list/manage account tunnels. However:

- the current `pro6000-ssh` tunnel is shared with SSH and two existing HTTP routes;
- editing/restarting it risks unrelated services;
- adding hostnames changes Cloudflare/DNS state;
- the repository has no approved hostname, Access policy, or teardown receipt for this proof.

Do not modify the shared tunnel. If stable URLs become mandatory, create a **separate** named
tunnel and separate config only after the owner approves the exact hostnames and confirms the
Cloudflare zone/account boundary. That work is deliberately not automated here.

### 3. Local Mac + Cloudflare Quick Tunnels — fallback

The Mac has sufficient memory/disk and the same Quick Tunnel binary. This is the fastest rehearsal
path, but it is less reliable for a final recording because sleep, Wi-Fi changes, Docker Desktop,
or a terminal logout can end the proof. Port 8000 was already occupied during the audit, so the
new scripts default LedgerLens to loopback port 18000.

### 4. GitHub SSH deployment workflow — blocked

`.github/workflows/deploy-incident-demo.yml` is well bounded, but its protected `judge-demo`
Environment and required secret names are absent. The workflow also requires a pre-created VM,
DNS, firewall, and pinned SSH host key. It must not be used to infer or provision infrastructure.

### 5. RunPod — rejected for this proof

No local RunPod credential name or CLI is available. A new pod would introduce paid compute and
storage lifecycle risk without helping the CPU-only DataHub proof. RunPod documentation also
distinguishes stopped-pod storage charges from running compute; stopping is not equivalent to
deleting all billable state.

### 6. Hugging Face Space — keep replay, not full DataHub

The configured Space is currently healthy and is the stable public Incident Commander replay.
It should not be stretched into a full DataHub host: the DataHub quickstart is a multi-container
Docker deployment, while a Docker Space is already a container and is not the repository's
supported nested-Docker deployment target.

## Reversible implementation

New scripts:

- `deploy/live-proof/stack.sh`: starts/stops the hardened loopback DataHub stack and live
  LedgerLens web surface;
- `deploy/live-proof/quick_tunnels.sh`: adds a local Caddy basic-auth gateway and one or two
  Cloudflare Quick Tunnels.

Neither script provisions a VM, DNS record, named tunnel, Cloudflare Access application, RunPod
pod, or paid model call. Both refuse takeover of occupied ports/processes. Process shutdown checks
the command line before signaling a recorded PID and never sends `SIGKILL`. DataHub volumes and
private state are preserved.

Runtime state defaults to `~/.cache/ledgerlens-live-proof-stack` and
`~/.cache/ledgerlens-live-proof-tunnels`, both outside the repository. Home-directory state also
keeps bind mounts compatible with the currently selected Colima Docker context; `/tmp` is not
necessarily shared into that Docker VM.

### Secret file prerequisites

Create a private environment file outside the repository, mode `0600`, using the names from
`deploy/.env.example`. Required names:

```text
JUDGE_GATEWAY_USERNAME
JUDGE_GATEWAY_PASSWORD
JUDGE_GATEWAY_PASSWORD_HASH
DATAHUB_ADMIN_PASSWORD
DATAHUB_JUDGE_PASSWORD
DATAHUB_SERVICE_PASSWORD
```

Optional/defaulted names:

```text
DATAHUB_ADMIN_USERNAME
DATAHUB_JUDGE_USERNAME
DATAHUB_SERVICE_USERNAME
DATAHUB_VERSION
DATAHUB_CLI_VERSION
DATAHUB_QUICKSTART_COMPOSE_SHA256
CADDY_IMAGE
JUDGE_TTL_HOURS
```

For this Quick Tunnel path, use distinct non-resolving placeholders:

```text
LEDGERLENS_FQDN=ledgerlens.invalid
DATAHUB_FQDN=datahub.invalid
```

The generated public Caddy configuration is validated but not started. The new temporary gateway
uses the same username/hash on loopback.

Generate the Caddy bcrypt hash interactively so the plaintext password does not enter shell
history:

```bash
docker run --rm -it caddy:2.10.2-alpine caddy hash-password
```

Put the resulting hash in the private environment file. Do not commit that file.

### Start the private stack

Run on `pro6000-cf` after copying a clean checkout there, or run locally for rehearsal:

```bash
export LIVE_PROOF_ENV_FILE=/absolute/private/path/judge.env
export LIVE_PROOF_ALLOW_DOWNLOADS=1
bash deploy/live-proof/stack.sh check
bash deploy/live-proof/stack.sh start
bash deploy/live-proof/stack.sh status
```

`LIVE_PROOF_ALLOW_DOWNLOADS=1` is intentionally explicit because first startup downloads Python
packages and pinned Docker images and can consume substantial disk/network. It does not authorize
paid infrastructure.

The stack:

1. runs the existing deployment preflight;
2. downloads and SHA-256 verifies the pinned official DataHub compose;
3. rewrites every published DataHub port to `127.0.0.1`;
4. enables metadata authentication, policy enforcement, and REST authorization;
5. rotates the root password and creates separate judge/service Reader users;
6. seeds only the sanitized fixture;
7. disables mutation/document/user tools for the LedgerLens web process;
8. starts LedgerLens on `127.0.0.1:18000`.

Before public exposure, independently confirm the host firewall does not expose 8080, 9002, or
18000. The loopback compose binding is defense in depth, not a cloud/firewall audit.

### Start temporary authenticated public URLs

Load only the gateway username/hash into the shell; do not put the plaintext password in an
argument:

```bash
export LIVE_PROOF_GATEWAY_USERNAME=ledgerlens-judge
export LIVE_PROOF_GATEWAY_PASSWORD_HASH='REDACTED_BCRYPT_HASH'
export LIVE_PROOF_PUBLIC_ACK=temporary-public-proof
export LIVE_PROOF_ALLOW_IMAGE_PULL=1
bash deploy/live-proof/quick_tunnels.sh check
bash deploy/live-proof/quick_tunnels.sh start
bash deploy/live-proof/quick_tunnels.sh status
```

The explicit acknowledgement prevents an accidental public URL. `LIVE_PROOF_ALLOW_IMAGE_PULL=1`
only permits pulling the pinned Caddy image if absent.

The gateway automatically uses `host.lima.internal` for the Colima Docker context and
`host.docker.internal` elsewhere. Override only when the Docker host has a different documented
host alias:

```bash
export LIVE_PROOF_DOCKER_HOST_ALIAS=host.example.internal
```

To expose only DataHub while using the stable Hugging Face replay:

```bash
export LIVE_PROOF_SKIP_LEDGERLENS=1
bash deploy/live-proof/quick_tunnels.sh start
```

The script prints random `trycloudflare.com` URLs and the non-secret username. It does not print
the password or hash. It verifies that unauthenticated public requests receive HTTP 401 before
reporting success.

### Stop and preserve evidence

Stop public ingress first:

```bash
bash deploy/live-proof/quick_tunnels.sh stop
bash deploy/live-proof/stack.sh stop
```

Stopping preserves:

- DataHub Docker volumes;
- the private state directory;
- provisioning/health receipts;
- tunnel logs and last ephemeral URLs.

No cleanup script deletes volumes, images, credentials, or release directories. Review and archive
sanitized receipts before any manual cleanup.

## Final video recommendation

Use a supervised two-surface recording:

1. Open the verified Hugging Face Incident Commander and show the fixture/replay label.
2. Open the temporary authenticated DataHub URL in a separate clean browser profile.
3. Log in with the DataHub **judge Reader** identity, not root/service.
4. Show the matching dataset, owner/tag/custom properties, lineage, and the persisted incident
   document created by the published write-back flow.
5. Show the tracked live receipt
   `benchmarks/incident_commander/datahub-live-writeback-receipt.json`, including:
   `status: applied`, `externalMutation: true`, the persisted document URN, fresh MCP retrieval,
   and its limitations.
6. Show `benchmarks/results/live-datahub-smoke-2026-07-31.json` and
   `benchmarks/results/live-mcp-2026-07-31.json` for pinned versions and live-mode provenance.
7. Keep `candidateOnly: true`, `canClaimAGI: false`, and the difference between fixture replay,
   live DataHub, live MCP, and unexecuted providers visible.
8. Stop both tunnels immediately after the take and retain a sanitized stop/status screenshot.

For an under-three-minute video, prefer **HF replay + DataHub-only tunnel**. It avoids spending
time explaining two ephemeral URLs while still giving judges a live catalog surface and a stable
Incident Commander surface.

## Go/no-go checklist

**GO only if all are true**

- clean intended checkout;
- private secret file is outside Git and mode `0600`;
- at least 20 GiB free disk remains before image pulls;
- DataHub GMS/frontend and LedgerLens health pass on loopback;
- DataHub judge/service users verify read-only;
- 8080, 9002, and 18000 are not reachable externally;
- Caddy gateway returns HTTP 401 without credentials;
- each Quick Tunnel returns HTTP 401 without credentials;
- only sanitized fixture/catalog data is present;
- an operator is present to stop the proof.

**NO-GO if any are true**

- a required port belongs to another process;
- the shared named Cloudflare tunnel would need editing;
- default DataHub credentials remain active for a shared link;
- the public URL bypasses Caddy basic auth;
- disk headroom falls below the deployment preflight floor;
- a paid VM/pod would need to be created;
- the operator cannot supervise teardown.

## Limitations

- Quick Tunnel URLs are random, temporary, and unsupported by an SLA.
- The existing workstation is shared infrastructure; avoid long-lived public exposure.
- The workstation's approximately 42.8 GiB free disk is adequate for the checked gate but not a
  generous margin for repeated image pulls or unrelated workloads.
- A successful public health check proves reachability and configured authorization at that time,
  not production security.
- The live write-back receipt proves a DataHub document mutation and retrieval, not incident
  causality or recovery.
- Slack, PagerDuty, and Jira have not been executed live.
- The recommended public proof should be supervised and removed after the video/judge window.

## Official service references

- Cloudflare Quick Tunnels:
  `https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/`
- Tailscale Funnel:
  `https://tailscale.com/kb/1223/funnel`
- RunPod pod lifecycle and billing:
  `https://docs.runpod.io/pods/manage-pods`
