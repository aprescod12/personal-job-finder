# Stage 5 Step 5 — OpenAI Resume Evaluation

## Goal

This step extends the Stage 5 résumé benchmark so the Candidate Profile Agent can compare two extraction approaches on the same controlled evidence:

1. the deterministic local parser,
2. the optional OpenAI structured-output parser.

The comparison remains evaluation-only. It does not approve claims, update `CareerProfile`, save extracted evidence, change job rankings, or make any database write.

## Why compare providers on identical cases

A model can look impressive on one résumé and still be unreliable. A fair provider comparison requires:

- the same source text,
- the same ground truth,
- the same critical claims,
- the same forbidden claims,
- the same field-scoring logic.

This removes the temptation to judge the AI provider using a different or easier test set.

## Three operating modes

The management command now supports:

```text
deterministic
openai
compare
```

### Deterministic

Runs `DeterministicResumeExtractor` only.

Properties:

- offline,
- repeatable,
- no API key,
- safe for CI,
- stable baseline.

### OpenAI

Runs `OpenAIResumeExtractor` only.

Properties:

- live API request,
- structured JSON output,
- grounding validation,
- provider latency,
- potential API cost.

### Compare

Runs the deterministic baseline first and OpenAI second, then calculates provider deltas for each case and for the complete suite.

## Accidental-spend protection

Selecting OpenAI is intentionally harder than selecting the deterministic provider.

A live run requires all of the following:

1. `--provider openai` or `--provider compare`,
2. `--allow-live-openai`,
3. `RESUME_AI_ENABLED=true`,
4. a valid local `OPENAI_API_KEY`.

The explicit command acknowledgement prevents a copied benchmark command from silently making billable requests.

The OpenAI provider remains disabled by default, and GitHub Actions explicitly selects `--provider deterministic`.

## Running the deterministic baseline

```bash
python manage.py evaluate_resume_extraction \
  --provider deterministic \
  --minimum-agreement 60 \
  --output /tmp/resume-deterministic.json
```

This is the CI-safe command.

## Running OpenAI locally

Set local environment values without committing them:

```bash
export RESUME_AI_ENABLED=true
export OPENAI_API_KEY="your-local-key"
```

Then run:

```bash
python manage.py evaluate_resume_extraction \
  --provider openai \
  --allow-live-openai \
  --minimum-agreement 60 \
  --output /tmp/resume-openai.json
```

## Running a side-by-side comparison

```bash
python manage.py evaluate_resume_extraction \
  --provider compare \
  --allow-live-openai \
  --minimum-agreement 60 \
  --output /tmp/resume-provider-comparison.json
```

Add the stricter regression gate when desired:

```bash
python manage.py evaluate_resume_extraction \
  --provider compare \
  --allow-live-openai \
  --minimum-agreement 60 \
  --fail-on-regression \
  --output /tmp/resume-provider-comparison.json
```

The report is written before the command raises a regression or quality error, so the failure can still be inspected.

## Metrics

### Agreement percentage

The same twelve identity and profile field groups from Step 4 are compared against ground truth.

The score measures extraction agreement only. It is not a candidate quality score or job-match score.

### Under-extraction

An under-extracted item is expected by ground truth but missing from provider output.

Examples:

- a degree institution is missing,
- a project heading is omitted,
- Python is absent from extracted skills.

### Over-extraction

An over-extracted item appears in provider output but has no matching expected item.

Examples:

- an extra skill,
- a header line classified as experience,
- a section heading classified as a project.

Over-extraction is not automatically hallucination. It can also expose incomplete ground truth or a disagreement about section boundaries. The source text must be inspected before deciding which side is wrong.

### Evidence coverage

Evidence coverage asks whether each non-empty expected field group has at least one evidence item with source text.

The comparison maps benchmark fields to extraction evidence fields. For example:

```text
profile.project_headings -> profile.projects
profile.education_headings -> profile.education
```

High agreement with low evidence coverage is not enough for profile approval. The system must be able to show why a claim was extracted.

### Latency

The evaluator records provider execution time per case and aggregates average and total latency.

Latency is diagnostic because an AI provider may improve extraction quality while making the workflow slower and more expensive.

### Critical claims

Critical claims represent facts that should not be lost, such as a key project or technical skill.

The OpenAI candidate should not be accepted merely because its aggregate score is higher if it drops a critical claim.

### Forbidden claims

Forbidden claims represent facts that must not appear because the résumé does not state them.

Any forbidden hit still causes the selected provider evaluation to fail.

## Regression classification

A case is classified as a regression when the OpenAI candidate has one or more of these changes relative to the deterministic baseline:

- lower agreement,
- lower evidence coverage,
- more under-extraction,
- more over-extraction,
- fewer critical claims passed,
- more forbidden claims.

The report records the reasons instead of reducing the comparison to a single number.

This matters because a provider can improve average agreement while becoming worse on one important résumé format.

## Test doubles and dependency injection

Automated tests do not call OpenAI.

The evaluation runner accepts any `BaseResumeExtractor`. Tests inject a controlled AI-shaped extractor that:

- uses `extraction_mode = "ai"`,
- returns expected fixture data,
- emits evidence,
- requires no API key,
- makes no network request.

A separate empty AI test double verifies regression detection.

This is dependency injection: the evaluator depends on the extraction contract rather than a hard-coded network client.

## CI boundary

GitHub Actions runs:

```bash
python manage.py evaluate_resume_extraction \
  --provider deterministic \
  --minimum-agreement 60 \
  --output /tmp/resume-evaluation.json
```

CI never passes `--allow-live-openai`, never needs `OPENAI_API_KEY`, and never makes a live provider request.

## Data and privacy boundary

The committed benchmark cases are synthetic. A local OpenAI comparison sends only those synthetic case texts.

The provider request uses strict structured output and `store=False`. However, `store=False` should not be interpreted as a complete Zero Data Retention guarantee. OpenAI organization-level data controls and abuse-monitoring policies are separate platform settings.

Do not replace the synthetic benchmark cases with a real résumé containing private contact information unless there is an explicit decision to do so and the privacy implications have been reviewed.

## How to interpret the first live comparison

A promising AI result should have:

- no forbidden claims,
- all critical claims preserved,
- agreement at or above the deterministic baseline,
- evidence coverage at or above the baseline,
- fewer missing items,
- no material case-specific regression.

A higher score alone is not enough.

The first live run should be saved as an evaluation artifact with the model version and date. It should be reviewed before AI output is allowed to move from the session-backed review draft into persistent candidate evidence.

## Next step

After a satisfactory live comparison, the next Candidate Profile Agent step should design controlled approval and persistence for extracted candidate claims.

That step should include:

- editable review fields,
- claim-level approval or rejection,
- source/evidence links,
- provenance and provider version,
- protection against overwriting manually maintained profile data,
- re-extraction behavior when the active résumé changes.
