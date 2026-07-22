# Stage 5 Step 4 — Resume Extraction Evaluation

## Goal

This step adds a repeatable offline benchmark for the Candidate Profile Agent before any extracted résumé claim can be approved or persisted.

The benchmark answers four questions:

1. Did the extractor recover the expected identity and profile fields?
2. Did it preserve critical claims that matter for matching?
3. Did it invent any forbidden claims?
4. How does performance change across résumé formats and missing sections?

## Why evaluation comes before profile persistence

An extractor can return valid JSON and still be unreliable. It may:

- miss a skill,
- combine separate entries,
- confuse a project with work experience,
- infer a credential,
- add a technology that never appeared,
- fail when section headings change.

The review workflow protects the database, but evaluation measures whether the extraction itself is good enough to continue developing.

## Case structure

Each benchmark case is a directory containing:

```text
resume.txt
ground-truth.json
```

The ground-truth file uses:

```text
resume-extraction-evaluation-case-v1
```

It records:

- a stable case ID,
- a category,
- expected identity values,
- expected section headings,
- expected skills,
- critical claims,
- forbidden claims.

Critical claims require a source quote that must exist in `resume.txt`. This prevents benchmark expectations from drifting away from the actual source.

## Current benchmark coverage

The initial suite includes:

- a standard engineering résumé,
- alternate section headings,
- a résumé that omits optional sections.

The cases are synthetic. They are safe to commit and do not expose a real candidate's private contact information.

## Deterministic baseline

The first official run uses `DeterministicResumeExtractor` only.

That matters because it creates a stable baseline that:

- works without an API key,
- runs in CI,
- produces reproducible output,
- reveals the limitations of heading-based parsing,
- gives future OpenAI runs something concrete to beat.

A live AI request is not part of CI.

## Comparison metrics

The evaluator compares twelve field groups:

```text
identity.full_name
identity.email
identity.phone
identity.location
identity.links
profile.professional_summary
profile.education_headings
profile.experience_headings
profile.project_headings
profile.skills
profile.certification_headings
profile.leadership_headings
```

Text fields use normalized token and sequence similarity.

List fields match expected and actual items conservatively, then report:

- field score,
- missing items,
- unexpected items.

The aggregate agreement percentage is diagnostic. It is not a candidate-job score and never affects ranking.

## Critical and forbidden claims

Critical claims represent evidence the system must not lose, such as:

- a key technical skill,
- a degree institution,
- a relevant project,
- an experience title.

A critical claim passes when its field comparison reaches the minimum similarity threshold.

Forbidden claims test non-inference. Examples include skills, credentials, or seniority that never appeared in the résumé.

Any forbidden hit makes the management command fail.

## Management command

Run the benchmark with:

```bash
python manage.py evaluate_resume_extraction
```

Write a JSON report with:

```bash
python manage.py evaluate_resume_extraction \
  --minimum-agreement 60 \
  --output /tmp/resume-evaluation.json
```

The command fails when:

- a case is malformed,
- a critical claim is missed,
- a forbidden claim appears,
- aggregate agreement falls below the selected threshold.

## CI boundary

GitHub Actions now runs the résumé benchmark after the existing job-extraction evaluation and before the complete Django test suite.

The CI run:

- makes no live OpenAI call,
- requires no API key,
- writes no application data,
- creates no migrations,
- does not change match scores.

## Tests

The test suite verifies:

- repository cases load successfully,
- benchmark categories are diverse,
- case IDs are unique,
- absent evidence quotes are rejected,
- the deterministic provider produces structured comparisons,
- critical claims pass,
- forbidden claims remain absent,
- the management command writes a JSON report.

## Next step

The next AI-specific evaluation step should add an optional local provider mode that runs the same cases through `OpenAIResumeExtractor` using an injected or explicitly enabled backend.

That comparison should record:

- deterministic agreement,
- AI agreement,
- over-extraction,
- under-extraction,
- evidence coverage,
- latency,
- provider version,
- case-by-case regressions.

It should remain opt-in and must not run live API calls in CI.
