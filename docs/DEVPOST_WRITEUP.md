# Devpost Submission Draft

## Project name

**LedgerLens**

## Tagline

**Turn DataHub context into authorized incident work—with receipts.**

## Category

**Agents That Do Real Work**

## One-line summary

LedgerLens is an Autonomous Data Incident Commander that grounds a bounded response plan in
DataHub, uses AI for advisory verification, authorizes with deterministic policy, records
receipted actions, writes a durable incident record back to DataHub, and prepares the next-agent
handoff.

## Inspiration

A data alert usually tells responders that something looks wrong. It does not reliably answer:

- Which DataHub asset is the response anchored to?
- Who owns it?
- Which downstream assets are recorded in lineage?
- Which facts came from the trigger, which came from DataHub, and which remain unknown?
- Which operational actions are safe and reversible?
- Who or what authorized the exact action payload?
- Where will the receipts and unresolved questions live for the next responder?

Adding a general chatbot to that gap can make it worse. Fluent model output is useful for proposing
and reviewing work, but it must not silently become execution authority. We built LedgerLens to
make the evidence, uncertainty, authority, actions, and handoff visible in one incident workspace.

## What it does

LedgerLens runs this end-to-end incident-command chain:

```text
trigger
  -> DataHub context
  -> bounded plan
  -> AI advisory verification
  -> deterministic authorization
  -> receipted actions
  -> DataHub write-back
  -> next-agent handoff
```

1. **Trigger:** accepts a DataHub-shaped assertion or incident signal with a stable incident and
   idempotency key.
2. **DataHub context:** retrieves the root entity, owner, tier, schema field, documentation,
   quality signal, and bounded downstream lineage. Every fact has a source class and reference.
3. **Bounded plan:** proposes only allowlisted, reversible collaboration records and metadata
   write-back. It does not authorize rollback or claim recovery.
4. **AI advisory verification:** configured verifier variants check evidence coverage, unknowns,
   action completeness, targets, parameters, and risk. Different model identifiers are not
   presented as provider-family independence.
5. **Deterministic authorization:** exact plan fingerprint, action schema, evidence IDs, quorum,
   confidence, risk, target allowlist, and confirmation contract must pass. AI cannot authorize
   itself.
6. **Receipted actions:** typed adapters support GitHub issues, Slack messages, PagerDuty
   events/notes, and Jira issues with preview/execute separation, signed authorization binding,
   idempotency, bounded retries, conservative timeout handling, and sanitized receipts.
7. **DataHub write-back:** a disabled-by-default mutation policy can write the bounded incident
   command receipt through an allowlisted DataHub MCP tool.
8. **Next-agent handoff:** records known facts, unknowns, completed work, receipt references, and
   the exact recovery checks that must happen before anyone claims resolution.

## How we built it

### DataHub as operating context

DataHub is used on both sides of the workflow. The read path grounds owner, tier, schema,
documentation, quality evidence, and lineage-derived response scope. The write path records the
bounded incident command receipt so the next recovery agent can retrieve the same entity and
provenance instead of reconstructing the incident from chat history.

The public fixture contains synthetic DataHub-shaped context. Separate local-live receipts record
DataHub OSS v1.6.0 ingestion, official MCP read behavior, an authorized `save_document` mutation,
and fresh MCP retrieval of the created document.

### AI verification without AI self-authorization

The planner and verifier roles use typed JSON contracts. A live 020s rehearsal ran one planner and
two verifier variants over a bounded incident context. Their output satisfied quorum, but the
authorization receipt was issued by deterministic policy. No external action was executed by that
AI rehearsal.

The gate checks the frozen plan—not a later paraphrase—against action type, target, parameters,
risk, evidence fact IDs, quorum, confidence, and plan hash. Any mismatch closes the gate.

### Receipted provider actions

Each provider adapter separates preview from execute, requires a signed authorization bound to the
action digest, supports idempotency, limits retries, treats ambiguous timeouts conservatively, and
sanitizes receipts. A live GitHub rehearsal created and immediately closed issue `#3`. Slack,
PagerDuty, and Jira are implemented and tested but have not been executed live.

### DataHub write-back and retrieval

The mutation path is disabled by default and limited to allowlisted tools and entities. A published
receipt records a live DataHub `save_document` call, resulting document URN, before/after state,
limitations, and successful next-agent retrieval through official MCP `get_entities`. This proves
that bounded context was persisted and retrieved; it does not prove incident recovery.

### Public replay and hosted monitoring

The public Hugging Face Space runs a deterministic fixture replay without credentials, provider
calls, paid models, or external mutations. Every simulated action receipt uses `fixture://`. The
health endpoint exposes fixture mode and the claim ceiling. The trigger endpoint exposes exactly
four synthetic provider receipts, recorded fixture write-back, ready next-agent memory,
deterministic authority, and `ai_can_authorize: false`.

A scheduled and manually dispatchable GitHub workflow checks that public contract without
repository secrets and uploads a sanitized smoke receipt.

### Supervised authenticated DataHub proof

We also completed a temporary authenticated public proof against DataHub OSS v1.6.0 on an existing
physical workstation, without provisioning a paid resource. The proof returned 401 without
gateway credentials, 200 for the authenticated login and judge UI, rejected the factory
`datahub/datahub` credential, and verified bounded Reader grants without metadata-mutation
authority. The tunnel, gateway, relay, and remote stack were stopped, and the former URL returned
503. It was a supervised reachability proof, not a durable judge deployment or security
certification.

### Reproducibility and fail-closed release gates

Default CI runs on Python 3.11 and 3.12 and installs the DataHub, development, web, and video
dependencies needed to exercise imports and strict typing. It runs Ruff, strict mypy,
deterministic tests, the public-package guard, the secret scan, non-video readiness, source/wheel
builds, and a non-root container build.

The separate non-video readiness guard verifies required receipts, claim flags, teardown state,
CI/typecheck dependencies, hosted-smoke automation, current product copy, and release wording. It
reports the public video, final `v0.2.1` tag, owner submission action, external reviewers,
provider credentials, and upstream maintainer review as explicit deferred dependencies instead of
silently claiming completion.

## Challenges

### Model judgment is not authority

Verifier agreement can be useful evidence, but it cannot grant itself permission. The hardest
design constraint was binding authorization to the exact plan and exact action payload while
keeping model output advisory.

### Provenance is not validation

DataHub can tell us what metadata was recorded, by which path, and at what observed time. That does
not make the underlying incident assertion true. LedgerLens separates source assertions, DataHub
metadata, deterministic policy decisions, AI advisory output, provider receipts, and unknowns.

### Provider timeouts can be ambiguous

A timed-out create request may have succeeded remotely. Blind retry can duplicate incident work.
The adapters therefore use idempotency and conservative ambiguous-timeout behavior rather than
equating “no response” with “nothing happened.”

### Honest demos need separate fixture and live evidence

A stable public fixture is reproducible and judge-friendly, but it is not a live provider run. A
temporary DataHub tunnel can prove authenticated reachability, but it is not a durable production
deployment. We keep those result classes separate and publish receipts with explicit limitations.

### External feedback requires consent discipline

Small reviewer feedback can expose usability gaps, but two people cannot validate reliability or
predict a competition score. The evaluation kit keeps raw records private, separates aggregate,
comment, and attribution consent, and refuses to invent testimonials.

## Accomplishments

- Built a complete trigger-to-handoff incident-command state machine.
- Made DataHub context and write-back structurally necessary rather than decorative.
- Added planner and verifier interfaces with deterministic, fail-closed authorization.
- Implemented GitHub, Slack, PagerDuty, and Jira adapters with authorization binding,
  idempotency, bounded retries, and sanitized receipts.
- Recorded a real GitHub create-and-close receipt.
- Recorded a real DataHub write-back and official-MCP retrieval receipt.
- Completed and tore down a supervised authenticated public DataHub reachability proof.
- Built a deterministic 120-asset, 24-scenario DataHub-context ON/OFF benchmark.
- Deployed a stable public fixture replay with automated credential-free smoke monitoring.
- Prepared a consent-safe external evaluation kit and aggregation tool.
- Opened upstream DataHub MCP provenance/audit-context issue #159 and PR #160 with focused tests;
  PR #160 remains open, not merged.
- Added strict mypy, secret, public-package, hosted-smoke, and non-video readiness gates.

These accomplishments describe working-prototype mechanics and bounded receipts. They are not
independent validation, production readiness, validated uplift, incident recovery, or AGI.

## What we learned

The most valuable role for AI in an incident commander is often proposing and criticizing a
bounded plan—not owning authority. Once DataHub context, evidence IDs, action schemas, and plan
hashes are explicit, deterministic policy can enforce a much narrower execution contract.

We also learned that “real work” needs receipts and next-step semantics. A provider response proves
an action result, not root cause or recovery. A DataHub write-back is most useful when it carries
the unresolved questions and tells the next agent what evidence must arrive before the status can
change.

## What's next

- Complete two consented formative reviews and publish only allowed aggregate information.
- Execute Slack, PagerDuty, or Jira only if scoped competition credentials are supplied; otherwise
  preserve the tested-but-not-live wording.
- Respond to upstream review on DataHub MCP PR #160 without bypassing maintainers.
- Add the public under-three-minute video URL, then cut the final `v0.2.1` release from the actual
  merged commit.
- Run recovery verification against new DataHub observations without converting an action receipt
  into a resolution claim.

## Built with

- DataHub OSS v1.6.0
- DataHub MCP Server
- Python 3.11 and 3.12
- Pydantic
- Typer
- FastAPI
- Docker
- pytest
- Ruff
- strict mypy
- optional 020s OpenAI-compatible API
- GitHub Actions
- Hugging Face Docker Spaces

## Pre-existing work disclosure

The failure-ledger concept, original Sophia-AGI corpus, and general provenance/no-overclaim
discipline predate this hackathon. The public repository discloses that source boundary.

The LedgerLens incident models, DataHub context and mutation paths, planner/verifier integration,
authorization policy, provider adapters, dashboard, tests, benchmark, deployment package,
receipts, and submission automation were newly built in this public repository during the contest
period. No pre-existing DataHub ledger adapter implementation was imported or reused.

See `DISCLOSURE.md` for the full boundary.

## Limitations and claim boundary

LedgerLens is a working prototype. It does not establish:

- provider-family independence;
- live Slack, PagerDuty, or Jira execution;
- incident causality, user impact, recovery, or resolution;
- production reliability or security certification;
- independent validation or validated uplift;
- an upstream MCP merge while PR #160 remains open;
- AGI.

```yaml
candidateOnly: true
canClaimAGI: false
externalValidation: false
```

## Submission links

- Public repository: `https://github.com/tomyimkc/ledgerlens`
- Public project URL: `https://tomyimkc-ledgerlens-incident-commander.hf.space/`
- Current public baseline: `v0.2.0`
- Final release target: `v0.2.1`, pending the public video URL
- Public video: owner input required
- Final submission receipt: owner action pending
