# Demo Storyboard and Shot Plan

## Visual rules

1. Real functionality is shown only with real UI, terminal, DataHub, test, and artifact capture.
2. Grok `/imagine-video` assets are optional concept transitions.
3. Every generated clip carries `CONCEPT VISUAL — AI-GENERATED`.
4. Generated assets must never contain fake DataHub, LedgerLens, terminal, test, or benchmark UI.
5. Synthetic imitation must never substitute for real product proof.
6. Use the sanitized fixture and a clean browser profile.
7. Keep all critical text inside a 16:9 title-safe area.
8. Capture at 1920×1080 and render at 30 fps.

## Shot list

| ID | Time | Duration | Source | Content | Proof requirement |
|---|---:|---:|---|---|---|
| C1 | 0:00 | 3 s | Grok optional | Abstract failure records separating from owners/evidence | Label as generated |
| R1 | 0:03 | 6 s | Real LedgerLens UI | Product title and claim boundary | `candidateOnly` and `canClaimAGI` readable |
| R2 | 0:09 | 6 s | Real DataHub UI | Finding properties, owner, receipt, audit context | Stable URN and metadata readable |
| R3 | 0:15 | 6 s | Real LedgerLens UI | Remediation queue and saved report | Artifact result and reasons visible |
| R4 | 0:21 | 6 s | Real LedgerLens UI | Supersession chain | Current/superseded labels visible |
| R5 | 0:27 | 6 s | Real receipt view | Deterministic and live receipts | Result classes and versions distinct |
| R6 | 0:33 | 6 s | Real public repository | Apache-2.0 and disclosure | Public URL readable |
| C2 | 0:39 | 2 s | Grok optional | Abstract end transition | Label as generated |

Total target: **41 seconds**. Generated footage is at most 5 seconds, or about 12.2%.

## Real capture preparation

Open these surfaces before recording:

1. LedgerLens demo UI at `http://localhost:8000`;
2. DataHub UI at `http://localhost:9002`;
3. a clean terminal in the public repository;
4. generated reports under `artifacts/demo/`;
5. CI page or a local rendered receipt.

Use `docs/demo/capture-plan.example.json` as the automation plan. Selectors are intentionally
configuration-driven because the UI may evolve.

## Edit plan

- Use hard cuts or short 6-frame dissolves.
- Keep generated concept footage below 15% of total runtime.
- Burn English captions into the final MP4.
- Normalize narration and avoid background music that masks speech.
- Overlay source labels:
  - `REAL LEDGERLENS UI`
  - `REAL DATAHUB OSS UI`
  - `DETERMINISTIC FIXTURE RESULT`
  - `LIVE DATAHUB SMOKE`
  - `CONCEPT VISUAL — AI-GENERATED`
- Do not speed terminal footage until text becomes unreadable.

## Required final review

- Video duration is strictly less than 180 seconds.
- All product claims are backed by real capture.
- Every result shown matches its receipt.
- No placeholder, fake result, or planned feature is presented as complete.
- No secrets or private data are visible.
