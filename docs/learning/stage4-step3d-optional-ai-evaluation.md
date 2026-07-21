# Stage 4 Step 3D.5 — Optional Local AI Evaluation

## Purpose

Step 3D.4 created one official field-comparison method and measured the deterministic parser across seven stored cases. Step 3D.5 applies that same comparison method to the AI extractor.

The objective is not to prove that one model is universally accurate. It is to answer a narrower engineering question:

> On the same stored listings and the same human ground truth, how does the configured AI extractor compare with the deterministic fallback?

This step introduces no production ranking changes, automatic approvals, or autonomous job decisions.

## New command

```bash
python manage.py evaluate_job_extraction_ai --allow-live-ai
```

The explicit flag is mandatory because a normal full run makes one provider call for each selected case.

To begin with one case:

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --case case-001-organon-medical-device-coop
```

Write a Markdown comparison report:

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --case case-001-organon-medical-device-coop \
  --format markdown \
  --output docs/evaluations/job-processing/runs/local-ai-case-001.md
```

Write JSON instead:

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --case case-001-organon-medical-device-coop \
  --format json \
  --output /tmp/local-ai-case-001.json
```

Do not commit a report containing secrets, raw provider diagnostics, or private listings.

## Required local configuration

The existing AI intake configuration must be ready before a live run:

```env
JOB_INTAKE_AI_ENABLED=true
OPENAI_API_KEY=your-local-key
OPENAI_JOB_EXTRACTION_MODEL=gpt-5-mini
OPENAI_JOB_EXTRACTION_TIMEOUT_SECONDS=30
OPENAI_JOB_EXTRACTION_MAX_OUTPUT_TOKENS=4000
```

The API key belongs in the local `.env` file and must never be committed.

## Why this is a separate command

The deterministic command remains:

```bash
python manage.py evaluate_job_extraction
```

It is safe for CI because it makes no network request.

The AI command remains separate because it has different operational properties:

- it may cost money,
- it needs a secret API key,
- it can time out,
- its provider can be temporarily unavailable,
- its output can vary when the model or prompt changes,
- and it should never run accidentally in CI.

Separate commands make the boundary obvious.

## Direct provider evaluation

The production intake workflow has a coordinator:

```text
AI extraction
    ↓ failure
Deterministic fallback
    ↓
Human review
```

That is correct for user-facing reliability, but it is wrong for provider evaluation.

During evaluation, the AI extractor is called directly:

```text
Stored listing
    ↓
AI extractor only
    ↓
Official comparison scorer
```

Fallback is deliberately disabled. Otherwise, an AI failure could be replaced by deterministic output and falsely presented as an AI result.

## Paired comparison

A valid comparison controls the inputs and scoring method:

```text
Same case set
Same source listings
Same human ground truth
Same field definitions
Same comparison thresholds
Different extractor
```

The command therefore creates two runs:

1. a fresh deterministic run,
2. a fresh AI run.

It then calculates percentage-point deltas:

```text
AI agreement − deterministic agreement
```

Example:

```text
Deterministic required-skills agreement: 25.00%
AI required-skills agreement:            78.00%
Delta:                                  +53.00 points
```

A positive delta means the AI output agreed more closely with stored ground truth under the official scorer. It does not automatically mean the AI interpretation was safe in every case.

## Recorded metadata

Every AI comparison records:

- official scorer version,
- AI evaluation wrapper version,
- extractor provider key and version,
- configured model,
- schema version,
- prompt version,
- generation time,
- selected cases,
- total AI duration,
- per-case duration,
- and whether a live provider was called.

This metadata is required for meaningful historical comparison.

A result from one model cannot be fairly compared with a later result unless the model, prompt, schema, scorer, and case set are identifiable.

## Latency

Latency is measured around each complete extraction call:

```text
start timer
→ build prompt
→ call provider
→ parse structured JSON
→ validate fields
→ create JobExtractionResult
stop timer
```

Therefore the duration represents end-to-end extraction time, not only network time.

Latency is diagnostic. It should not be mixed into field agreement.

A slower extraction can still be more accurate. A faster extraction can still be unsafe.

## Cost awareness

The project does not currently calculate exact provider cost because the stored extraction result does not expose token usage.

For now, the operational rule is:

```text
selected cases = expected live calls
```

One selected case normally means one live request. Seven cases normally mean seven live requests.

Start with one case. Confirm that:

- the key works,
- the model is available,
- the structured output validates,
- the comparison report is created,
- and the result contains no sensitive diagnostic data.

Only then run the complete library.

## Why the command fails without permission

This command intentionally fails:

```bash
python manage.py evaluate_job_extraction_ai
```

The required flag forces a conscious acknowledgement that live provider calls may occur:

```bash
python manage.py evaluate_job_extraction_ai --allow-live-ai
```

This is a command-line safety gate, not a security control. It prevents accidental execution but does not replace proper secret management or provider spending limits.

## Fake providers in tests

CI must verify AI-evaluation behavior without calling a paid service.

Tests inject a fake extractor that implements the same `BaseJobExtractor` contract:

```python
class FakeAIExtractor(BaseJobExtractor):
    extraction_mode = "ai"

    def extract(self, request):
        return self.result(job=..., requirements=...)
```

This is dependency injection:

```text
Production
→ OpenAIJobExtractor

Tests
→ FakeAIExtractor
```

The evaluation service does not need to know which implementation it received. It only depends on the shared contract.

## What the tests prove

The Step 3D.5 tests verify that:

- live AI is disabled by default,
- the explicit command flag is required,
- a non-AI extractor cannot masquerade as the AI provider,
- fake extractors make no network calls,
- AI output uses the same official scorer as deterministic output,
- both runs contain the same case IDs and fields,
- model, schema, prompt, and timing metadata are recorded,
- Markdown and JSON reports are generated,
- no `JobPosting` is created,
- no `JobRequirement` is created,
- and deterministic fallback is not used.

## Interpreting the comparison

Focus first on critical fields:

- company,
- title,
- location,
- required skills,
- preferred skills,
- required education,
- minimum and maximum experience,
- authorization requirements,
- hard disqualifiers,
- deadline status,
- and application deadline.

Do not optimize only for overall agreement. A model could improve many minor fields while becoming worse on authorization or hard blockers.

A good review order is:

1. inspect authorization and hard-disqualifier output,
2. inspect required versus preferred classification,
3. inspect education and experience,
4. inspect title, company, location, and deadline,
5. inspect responsibilities and industry,
6. then consider the overall percentage.

## Prompt refinement discipline

Do not change the prompt because of one isolated miss.

Use this sequence:

```text
Run all cases
→ identify repeated failure pattern
→ classify severity
→ propose the smallest prompt/schema/normalization change
→ rerun all cases
→ compare gains and regressions
```

Examples of repeated patterns worth addressing:

- preferred qualifications repeatedly promoted to required,
- authorization uncertainty repeatedly converted into rejection,
- responsibilities repeatedly duplicated,
- industry repeatedly copied as employer marketing language,
- experience ranges repeatedly lost,
- or salary placeholders repeatedly treated as real compensation.

## Reproducibility limitation

AI output may vary even when the code does not change. The report is therefore a captured observation, not a mathematical guarantee.

For stronger comparisons:

- keep the case set fixed,
- keep the model fixed,
- keep the schema and prompt versions fixed,
- run the same cases more than once when variability matters,
- and preserve dated reports.

Future work may add repeated trials and aggregate variance. Step 3D.5 intentionally starts with one extraction per case.

## Relationship to production

Evaluation assets remain outside the production request path.

```text
Development evaluation
stored cases → extractor → scorer → report

Production intake
user listing → coordinator → review draft → human approval → database
```

The evaluation percentage must never become:

- the dashboard `/100` score,
- a candidate eligibility score,
- an automatic application decision,
- or a substitute for human review.

## Recommended local sequence

### 1. Update the branch

```bash
cd /Users/amiriprescod/personal-job-agent
git checkout main
git pull origin main
```

### 2. Confirm `.env`

```env
JOB_INTAKE_AI_ENABLED=true
OPENAI_API_KEY=...
OPENAI_JOB_EXTRACTION_MODEL=gpt-5-mini
```

### 3. Run one case

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --case case-001-organon-medical-device-coop
```

### 4. Save one-case output

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --case case-001-organon-medical-device-coop \
  --output /tmp/organon-ai-comparison.md
```

### 5. Review critical fields manually

Do not rely only on the aggregate percentage.

### 6. Run all seven cases

```bash
python manage.py evaluate_job_extraction_ai \
  --allow-live-ai \
  --output /tmp/full-ai-comparison.md
```

### 7. Disable AI afterward when desired

```env
JOB_INTAKE_AI_ENABLED=false
```

## Exercises

1. Explain why evaluating the coordinator would produce misleading provider results.
2. Calculate a percentage-point delta from a deterministic score of 48.56% and an AI score of 82.40%.
3. Identify which metadata must stay constant for a fair before-and-after prompt comparison.
4. Write a fake extractor that returns one intentionally incorrect authorization requirement.
5. Explain why latency should not be added to extraction agreement.
6. Describe a repeated failure pattern that would justify a prompt change.
7. Explain why one full seven-case run may still be insufficient to estimate model variability.
8. Describe how an AI evaluation report differs from the live `/100` candidate-job match score.

## Self-check answers

1. The coordinator may replace failed AI output with deterministic fallback, hiding the AI failure.
2. `82.40 − 48.56 = +33.84 percentage points`.
3. Case set, ground truth, official scorer, model, prompt, schema, and relevant provider settings.
4. Use `BaseJobExtractor`, set `extraction_mode = "ai"`, and return a normal `JobExtractionResult` with the intentional error.
5. Latency measures performance, while agreement measures correctness relative to ground truth.
6. A pattern repeated across multiple cases, especially one affecting required/preferred or eligibility fields.
7. Model output can vary between runs even with identical inputs.
8. The evaluation report measures extractor-ground-truth agreement; the `/100` score measures candidate-job fit.
