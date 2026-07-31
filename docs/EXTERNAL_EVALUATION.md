# LedgerLens External Evaluation

## Purpose and claim boundary

This package defines a small, formative review of the public LedgerLens Incident Commander
fixture. It is designed to answer a narrow question:

> Can a data engineer or incident responder understand the bounded incident workflow, find the
> evidence and uncertainty boundaries, and identify the next safe action in 7–10 minutes?

The review is **not** a production incident exercise, security assessment, scientific validation,
or official competition judging. Two reviewers are useful for finding obvious usability and
operational-credibility gaps; they are not a representative sample. Do not describe the result as
independent validation, validated uplift, production readiness, reliability, or a predicted
competition score.

```yaml
candidateOnly: true
canClaimAGI: false
externalValidation: false
```

## Reviewer target

Recruit two people who did not build the evaluated workflow:

1. one data engineer familiar with catalog, lineage, ownership, or data-quality incidents;
2. one incident responder, SRE, on-call engineer, or incident commander.

Record a broad role only. Do not request employer, customer, location, incident details, or other
unnecessary personal information. A prior project conversation does not disqualify a reviewer, but
record the relationship privately so the review is not misrepresented as independent.

## Public demo

Use the exact public URL supplied by the maintainer:

```text
LEDGERLENS_PUBLIC_URL
```

Do not replace the fixture with private production data. Reviewers should not enter credentials,
API keys, names, company details, or real incident text. The exercise requires no account and no
screen recording.

## 7–10 minute protocol

Use [`docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md`](evaluation/INCIDENT_COMMANDER_SCORECARD.md)
without coaching the reviewer through the interface.

| Time | Activity |
|---|---|
| 0:00–0:45 | Read the safety and consent statement; choose the data-engineer or incident-responder lens |
| 0:45–1:15 | Open `LEDGERLENS_PUBLIC_URL`; allow one reload if the page does not load |
| 1:15–3:30 | Run the visible replay and narrate what changed |
| 3:30–5:30 | Find DataHub context, authorization scope, synthetic receipts, unknowns, and handoff |
| 5:30–6:30 | Answer the bounded-response prompt without assuming cause, impact, or recovery |
| 6:30–9:00 | Complete six 0–4 scores, task checks, and optional comments |
| 9:00–10:00 | Optional clarification and separate public-use consent |

Stop at 10 minutes. If the demo is unavailable after one reload, record the run as incomplete and
the blocking observation. Do not troubleshoot with the reviewer or substitute a local demo.

## Consent-safe collection

Participation is voluntary. A reviewer may skip any question or stop without giving a reason.
Feedback is private by default, and these permissions are separate:

- **public aggregate:** include completed numeric scores and task checks in an anonymous summary;
- **public anonymous comment:** publish only an exact excerpt the reviewer has explicitly approved;
- **public attribution:** attach a name or handle only after separate explicit approval.

An unchecked box means no permission. Consent can be withdrawn before publication. Never turn a
private comment into a testimonial, infer endorsement from participation, or publish reviewer IDs.
Do not publish raw JSONL records because free text may contain identifying information.

Recommended private storage is one JSON object per line:

```json
{
  "schemaVersion": "ledgerlens.external-evaluation.v1",
  "reviewId": "replace-with-pseudonym",
  "role": "other",
  "completed": false,
  "durationMinutes": 0,
  "relationshipToProject": "not_recorded",
  "consent": {
    "publicAggregate": false,
    "publicAnonymizedComments": false,
    "publicAttribution": false
  },
  "tasks": {
    "openedDemo": false,
    "ranReplay": false,
    "foundDataHubContext": false,
    "distinguishedFixtureReceipts": false,
    "foundClaimBoundary": false,
    "foundNextAgentHandoff": false
  },
  "comments": {
    "mostUseful": "",
    "mostConfusing": "",
    "highestOperationalRisk": "",
    "oneChangeBeforeJudging": "",
    "approvedPublicExcerpt": ""
  }
}
```

Allowed `role` values are `data_engineer`, `incident_responder`, and `other`. Every record must
provide all six Boolean task checks. Completed reviews must also provide all six integer scores
from 0 through 4 under these exact keys:

- `datahubUseAndWriteback`
- `technicalExecution`
- `originalityBeyondBuiltins`
- `realWorldUsefulness`
- `submissionQualityAndReproducibility`
- `openSourceContribution`

The zero-duration, all-false object above is an unstarted template, not an evaluation result.
Incomplete reviews may omit scores but should state the blocker in private notes.

## Claim-safe aggregation

If the optional summarizer is present, create a public-safe descriptive summary with:

```bash
python scripts/summarize_external_evaluations.py private/reviews.jsonl
```

The default public mode:

- includes only completed records with `consent.publicAggregate: true`;
- prints no reviewer IDs, relationships, attribution, or free text;
- reports sample size, broad role counts, task completion counts, medians, and ranges;
- labels the rubric total as descriptive and not an official competition score;
- says when the planned two-reviewer sample has not been reached.

For private diagnosis only, `--scope internal` includes completed non-public records and prints a
prominent do-not-publish warning. Store private review records outside the public repository.

When reporting results manually:

1. report the number of completed, public-consented reviews and reviewer-role mix;
2. report all six criteria, including low scores and disagreements;
3. use median and range rather than unsupported precision;
4. separate task completion from subjective rubric scores;
5. describe comments as reviewer observations, not facts about production behavior;
6. publish an exact comment only if its separate anonymous-comment permission is checked;
7. do not claim that two reviewers validate reliability, usefulness, safety, or competition merit.

If zero reviewers consent to a public aggregate, publish no numeric result. If one reviewer
consents, label it as one person's formative review. If two consent, label it as a two-person
formative review, not external validation.

## Recruitment GitHub issue body

Suggested title:

```text
Seeking two reviewers for a 9-minute Incident Commander evaluation
```

Paste-ready body:

```markdown
We are seeking **two volunteer reviewers** for a 7–10 minute evaluation of LedgerLens:

- one data engineer familiar with catalog/lineage/data-quality incidents;
- one incident responder, SRE, on-call engineer, or incident commander.

Demo: `LEDGERLENS_PUBLIC_URL`

You will run one synthetic fixture replay, answer a bounded-response prompt, and score six
competition-aligned criteria. No account, credentials, private incident data, screen recording, or
testimonial is requested.

Feedback is private by default. Anonymous numeric aggregation, anonymous comment publication, and
attribution each require separate opt-in consent. Participation is not presented as endorsement or
independent validation.

Reply `interested` with only your broad role, or contact the maintainer through an existing private
channel if you do not want to identify yourself publicly. We will close recruitment after two
completed reviews.

Scorecard: `docs/evaluation/INCIDENT_COMMANDER_SCORECARD.md`
```

## Maintainer closeout checklist

- [ ] Replace `LEDGERLENS_PUBLIC_URL` only in the issued reviewer copy or recruitment issue.
- [ ] Recruit one data engineer and one incident responder.
- [ ] Keep raw scorecards and JSONL records private.
- [ ] Confirm consent immediately before any public summary or excerpt.
- [ ] Run the summarizer and review its output for claim boundaries.
- [ ] Publish low scores and disagreements alongside strengths.
- [ ] State the sample size and reviewer roles.
- [ ] Avoid testimonials, endorsements, production claims, and invented results.
