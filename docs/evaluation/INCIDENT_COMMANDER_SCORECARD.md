# LedgerLens Incident Commander Scorecard

**Target duration:** 7–10 minutes
**Demo:** `LEDGERLENS_PUBLIC_URL`
**Evaluation type:** formative fixture-usability review, not production validation

## 1. Safety and consent

Use only the supplied synthetic fixture. Do not enter credentials, private incident details,
company names, customer data, or other personal information. No screen recording is required.
You may skip any question or stop at any time.

Before starting:

- [ ] I understand this is a visibly labeled fixture replay, not a live provider or production
      incident run.
- [ ] I am participating voluntarily and may stop without giving a reason.

Public-use consent is requested separately at the end. Feedback remains private unless the
relevant box is checked.

## 2. Reviewer context

- Review ID supplied by maintainer: `________________`
- Broad role:
  - [ ] Data engineer
  - [ ] Incident responder / SRE / on-call engineer
  - [ ] Other: `________________`
- Relationship to LedgerLens, recorded privately:
  - [ ] None disclosed
  - [ ] Prior discussion or review
  - [ ] Contributor
- Date: `YYYY-MM-DD`
- Start time: `________`

Choose one lens:

- **Data engineer:** focus on catalog context, ownership, lineage, evidence semantics, and durable
  write-back.
- **Incident responder:** focus on triage clarity, bounded authority, reversibility, receipts,
  unknowns, and handoff.

## 3. Timed walkthrough

### 0:45–1:15 — Open

Open `LEDGERLENS_PUBLIC_URL`. Allow one reload if needed.

- [ ] The demo opened.
- [ ] I found the fixture/replay label and claim boundary without coaching.

### 1:15–3:30 — Replay

Click **Replay trigger** once. Think aloud, but do not ask the facilitator where to click.

- [ ] I could tell what triggered the incident.
- [ ] I could tell what changed after replay.
- [ ] I could distinguish proposed work, deterministic authorization, and completed fixture work.

### 3:30–5:30 — Evidence hunt

Point to each item in the interface:

- [ ] DataHub entity/context or lineage-derived blast radius
- [ ] authorization scope or plan binding
- [ ] a `fixture://` provider receipt
- [ ] explicit unknown cause, impact, recovery, or resolution
- [ ] DataHub write-back receipt
- [ ] next-agent handoff or memory

### 5:30–6:30 — Bounded-response prompt

Assume you are joining the on-call response. Using only what the demo shows, answer:

1. What is known?
2. What remains unknown?
3. What is the first bounded action you would allow or verify?
4. Where should the next responder find the action and write-back receipts?

Do not infer root cause, user impact, recovery, or incident resolution.

Notes:

```text

```

### 6:30–9:00 — Score

Use integer scores only:

| Score | Meaning |
|---:|---|
| 0 | Blocked, absent, or contradicted by the visible demo |
| 1 | Mentioned but difficult to find, understand, or trust |
| 2 | Partially demonstrated; important evidence or limits remain unclear |
| 3 | Clearly demonstrated in the fixture with inspectable evidence and limitations |
| 4 | Exceptionally clear and complete for a short fixture review; evidence and limits are easy to inspect |

The five core criteria are equally weighted. The open-source contribution is shown separately as a
bonus. This scorecard is a reviewer-perception tool, not an official judge score or evidence of
production performance.

| Competition-aligned core criterion | What to inspect | Score 0–4 |
|---|---|---:|
| Meaningful Use of DataHub Tools and Write-Back | DataHub context materially shapes owner, blast radius, evidence, authorization, write-back, or handoff rather than appearing as branding | `__` |
| Technical Execution and End-to-End Functionality | Trigger → context → plan → verification → deterministic gate → fanout → write-back → memory is coherent, visible, and fail-closed in scope | `__` |
| Originality and Extension Beyond Built-ins | The workflow adds evidence-bound authorization, receipted operational fanout, and handoff beyond catalog search or chat summarization | `__` |
| Real-World Usefulness | A responder can identify accountable next work without the interface inventing cause, impact, recovery, or resolution | `__` |
| Submission Quality and Reproducibility | The fixture mode, synthetic receipts, limitations, and replay path are understandable and reproducible without credentials | `__` |

- Core total: `____ / 20`
- Core descriptive percentage, if useful: `core total ÷ 20 × 100 = ______%`

| Separate bonus | What to inspect | Score 0–4 |
|---|---|---:|
| Open-Source Contribution Bonus | The demo or linked material makes the open-source contribution concrete without claiming an unverified upstream merge | `__` |

- Bonus score: `____ / 4` (report separately; do not fold it into the core total)

## 4. Task checks for aggregation

Mark one value per row:

| Task | Yes | No |
|---|:---:|:---:|
| Opened the public demo | [ ] | [ ] |
| Ran the replay | [ ] | [ ] |
| Found meaningful DataHub context | [ ] | [ ] |
| Distinguished `fixture://` receipts from live provider evidence | [ ] | [ ] |
| Found the claim boundary / explicit unknowns | [ ] | [ ] |
| Found the next-agent handoff | [ ] | [ ] |

- End time: `________`
- Duration in minutes: `________`
- Completed the full scorecard:
  - [ ] Yes
  - [ ] No — blocker: `________________________________________________`

## 5. Optional observations

Short operational observations are more useful than praise.

- Most useful element:

  ```text

  ```

- Most confusing element:

  ```text

  ```

- Highest operational risk or trust gap:

  ```text

  ```

- One change before competition judging:

  ```text

  ```

## 6. Separate public-use permissions

Unchecked means **no permission**. These choices are independent and may be withdrawn before
publication.

- [ ] **Anonymous numeric aggregate:** My completed scores and task checks may be included in a
      public anonymous aggregate.
- [ ] **Anonymous comment:** The exact excerpt written below may be published anonymously.
- [ ] **Attribution:** The exact excerpt may be attributed to the name/handle written below.

Approved public excerpt, if any:

```text

```

Approved name/handle, only if attribution is checked: `________________`

Participation is not an endorsement. The maintainer must not rewrite private feedback into a
testimonial or claim that this review establishes external validation, reliability, production
readiness, validated uplift, or likely competition results.
