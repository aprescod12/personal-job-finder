# Stage 4, Step 3D.4 — Deterministic Extraction Evaluation Runner

## Purpose

The Job Processing Agent now has seven validated evaluation cases. Step 3D.4 adds the first official runner that executes the deterministic extractor against those cases and compares its output with human-reviewed ground truth.

The runner answers:

> What does the current deterministic parser recover correctly, partially, incorrectly, or not at all across the complete benchmark?

It does **not** answer:

> Is this job a good match for Amiri?

Those are separate systems.

```text
extraction evaluator
→ compares parser output with benchmark ground truth
→ development and regression testing only

candidate-job matcher
→ compares a normalized job with the candidate profile
→ production /100 score and recommendation
```

The evaluation runner must remain isolated from the production matcher.

---

## 1. Files added in this step

### Evaluation service

```text
tracker/services/job_extraction_evaluation_runner.py
```

This file contains:

- comparison statuses,
- field definitions,
- normalization helpers,
- typed-field comparison,
- text comparison,
- list-item matching,
- case execution,
- run aggregation,
- Markdown rendering,
- JSON rendering,
- and report writing.

### Management command

```text
tracker/management/commands/evaluate_job_extraction.py
```

The command provides a stable interface for developers and CI.

### Tests

```text
tracker/test_job_extraction_evaluation_runner.py
```

The tests prove the comparison contract, seven-case execution, report rendering, selected-case execution, error handling, and the absence of database writes.

### Baseline report

```text
docs/evaluations/job-processing/runs/
```

A committed baseline records the deterministic parser's current behavior. Future parser changes should create a new report or explicitly update the baseline with version history rather than silently replacing evidence.

---

## 2. Why an evaluation runner is necessary

Without a repeatable runner, extraction quality discussions become anecdotal:

```text
this listing looked good
that listing looked bad
this prompt felt better
```

That is not enough to manage regressions.

A runner creates a controlled experiment:

```text
fixed source listings
+ fixed human ground truth
+ fixed extractor version
+ fixed comparison rules
= repeatable benchmark result
```

The benchmark cannot prove performance on every possible employer listing. It can reveal whether known cases improved or regressed.

---

## 3. Why the deterministic parser is evaluated first

The deterministic parser is:

- local,
- free,
- fast,
- stable,
- available in CI,
- and the Step 3C fallback.

It is therefore the correct first provider for the runner.

The baseline provides two forms of value:

1. It measures the fallback that users may see when AI extraction is unavailable.
2. It proves the evaluation infrastructure without spending API credits or introducing model variability.

AI evaluation is added later as an optional local mode. CI must remain free of paid model requests.

---

## 4. The official comparison statuses

Every compared field receives one status.

### `exact`

The normalized actual value agrees with ground truth.

Examples:

```text
expected: full_time
actual:   full_time
```

or:

```text
expected: Software Engineer I — Connected Medical Devices
actual:   software engineer i - connected medical devices
```

Case, punctuation, and Unicode dash differences do not create false failures.

### `partial`

The output contains meaningful overlap but is incomplete, broader, narrower, or phrased differently.

Examples:

- a role family copied from the full title,
- three expected skills represented in two combined source lines,
- a responsibility that captures the duty but includes extra wording.

Partial does not mean correct enough for unattended use. It means the result contains some recoverable evidence.

### `missing`

Ground truth expects a value, but the extractor returned nothing.

Examples:

- missing company,
- missing location,
- missing experience minimum,
- missing sponsorship restriction.

### `unexpected`

Ground truth is empty, but the extractor returned a value.

This is especially important for:

- invented authorization restrictions,
- invented certifications,
- invented deadlines,
- and invented experience requirements.

Unexpected output can be more dangerous than missing output because it appears confident while lacking source support.

### `incorrect`

Both sides contain values, but they do not agree sufficiently.

Examples:

```text
expected: remote
actual:   onsite
```

or an unrelated title selected from a header line.

---

## 5. Field types

The runner uses three comparison methods.

### Typed fields

Typed fields require exact agreement.

Examples:

- employment type,
- work arrangement,
- deadline status,
- seniority,
- dates,
- minimum years,
- maximum years.

These fields should not receive fuzzy credit. A deadline of August 15 is not partially correct when extracted as August 5.

### Text fields

Text fields use normalized similarity.

Examples:

- title,
- company,
- location,
- role family,
- requirement notes.

Normalization:

1. Applies Unicode NFKC normalization.
2. Converts to lowercase.
3. Removes punctuation differences.
4. Collapses whitespace.

Similarity is the maximum of:

- token F1,
- sequence similarity,
- and containment ratio.

Thresholds:

```text
0.98–1.00 → exact
0.55–0.9799 → partial
below 0.55 → incorrect
```

The thresholds are versioned behavior. They should not be changed merely to make a report look better.

### List fields

List fields include:

- required skills,
- preferred skills,
- education,
- responsibilities,
- certifications,
- authorization requirements,
- hard disqualifiers,
- and industry tags.

The deterministic parser stores these as newline-separated text. Ground truth stores canonical arrays. The runner converts both into lists and performs one-to-one matching.

---

## 6. One-to-one list matching

Suppose ground truth contains:

```text
UART
I2C
SPI
```

and the parser returns:

```text
Familiarity with UART, I2C, and SPI.
```

A naive evaluator might match the same actual line to all three expected items. That would exaggerate performance.

The runner instead uses one-to-one greedy matching:

1. Calculate similarity for every expected–actual pair.
2. Keep pairs at or above `0.55`.
3. Sort pairs from highest to lowest similarity.
4. Match each expected item at most once.
5. Match each actual item at most once.

This is intentionally conservative. In the example, one combined actual line cannot earn three independent matches.

That limitation is useful because the current structured model expects one item per line.

---

## 7. Precision, recall, and F1 for list fields

After matching:

```text
matched weight = sum of matched-pair similarities
```

Then:

```text
precision = matched weight / number of actual items
recall    = matched weight / number of expected items
F1        = harmonic mean of precision and recall
```

Interpretation:

- Precision decreases when the extractor adds unsupported items.
- Recall decreases when it misses expected items.
- F1 balances both.

Example:

```text
expected items: 4
actual items:   5
matched weight: 3.2

precision = 3.2 / 5
recall    = 3.2 / 4
```

The field remains `partial` unless normalized expected and actual sets are identical.

---

## 8. Field agreement percentage

Every field has a score from `0.0` to `1.0`:

- Exact fields receive `1.0`.
- Typed incorrect/missing/unexpected fields receive `0.0`.
- Partial text fields receive their similarity.
- Partial list fields receive their weighted F1.

The run-level field agreement is:

```text
100 × sum(field scores) / number of compared fields
```

This number is useful for regression comparison, but it is not a formal statistical accuracy estimate.

The report says **agreement**, not universal accuracy, because:

- the dataset is small,
- six cases are synthetic,
- canonical wording requires judgment,
- and the benchmark does not represent every listing format.

---

## 9. Eligibility-sensitive agreement

The runner also reports agreement for fields that can materially change whether a job is worth pursuing:

```text
job title
company
location
deadline status
deadline date
required skills
preferred skills
required education
minimum experience
maximum experience
work authorization
hard disqualifiers
```

This is a diagnostic slice of the same comparisons. It is not a second independent scorer and not a candidate eligibility decision.

Why keep it?

A parser could perform well on low-risk descriptive fields while failing sponsorship or experience requirements. The sensitive slice prevents the overall average from hiding that pattern.

---

## 10. What is intentionally not scored yet

### Critical-check prose

Each benchmark case includes human-written critical checks. Step 3D.4 does not pretend that their full meaning can be reliably evaluated with string matching.

For example:

> Do not reinterpret case-by-case sponsorship as no sponsorship.

That requires semantic judgment across several fields. The current runner exposes the underlying comparisons for human review instead of fabricating an automatic pass/fail decision.

### Known traps

Forbidden interpretations are retained as benchmark guidance but are not automatically scored in V1.

### Evidence quality

The deterministic parser's evidence notes are not compared against expected evidence in V1.

### Supplemental fields

Schedule, employment term, relocation, travel, openings, and similar facts are preserved in ground truth but are not produced by the current extraction schema. They are therefore excluded from the official field denominator.

Scoring fields the extractor cannot represent would measure schema limitations and parser quality as though they were the same problem.

---

## 11. Running the evaluator

### Full Markdown report

```bash
python manage.py evaluate_job_extraction
```

### Full JSON report

```bash
python manage.py evaluate_job_extraction --format json
```

### Write a report to disk

```bash
python manage.py evaluate_job_extraction \
  --format markdown \
  --output docs/evaluations/job-processing/runs/deterministic-baseline.md
```

### Evaluate one case

```bash
python manage.py evaluate_job_extraction \
  --case case-002-embedded-firmware-entry-level
```

Repeat `--case` to select multiple cases.

### Alternate case root

```bash
python manage.py evaluate_job_extraction --root /path/to/cases
```

---

## 12. Report formats

### JSON

JSON is the machine-readable source for:

- future comparison tools,
- charts,
- version-to-version diffs,
- and automated analysis.

It records:

```text
runner version
provider
run timestamp
case count
field count
overall agreement
sensitive agreement
status totals
per-field summary
per-case summary
full field comparisons
extractor warnings
```

### Markdown

Markdown is the human-readable review artifact.

It contains:

- headline results,
- status totals,
- case summary,
- field summary,
- case-by-case field details,
- warnings,
- and the interpretation boundary.

The Markdown report should be read before changing the parser.

---

## 13. Reproducibility and versioning

A useful baseline must record both:

```text
runner version
extractor version
```

Current versions:

```text
runner:    job-extraction-evaluator-v1
extractor: deterministic-intake-v1
```

Changing comparison logic requires a runner-version change. Changing extraction logic requires an extractor-version change.

Otherwise two different behaviors could produce reports that appear directly comparable when they are not.

A future AI report must also record:

- provider,
- model,
- prompt version,
- schema version,
- latency,
- fallback state,
- and request configuration that affects output.

---

## 14. Why this code stays in the repository

The runner is permanent regression infrastructure.

It should stay because it allows the project to answer:

```text
Did this parser change improve the seven known cases?
Did it fix sponsorship but break deadlines?
Did a new schema increase coverage?
Did an AI prompt improve required/preferred separation?
```

Temporary prototypes may be removed. The official case format, official evaluation runner, reports, and tests should remain.

The runner must stay isolated from:

```text
dashboard ranking
candidate-job matching
application decisions
eligibility decisions
job discovery ordering
```

---

## 15. Why CI does not enforce a minimum score yet

The deterministic parser is known to be limited. A fail-under threshold would create the wrong incentive:

```text
change comparison rules until CI turns green
```

CI should currently prove:

- all cases load,
- the runner completes,
- output is valid,
- tests pass,
- no database records are created,
- and no external API call occurs.

A quality threshold can be considered only after:

1. The comparison method is stable.
2. The baseline is reviewed.
3. Expected variation is understood.
4. The team agrees on a meaningful floor.

---

## 16. Reading the baseline responsibly

Do not focus only on the headline percentage.

Read in this order:

1. Eligibility-sensitive agreement.
2. Unexpected fields.
3. Missing authorization and deadline fields.
4. Required versus preferred skills.
5. Experience fields.
6. Company, title, and location.
7. Responsibilities and industry.
8. Extractor warnings.

A single critical eligibility error may matter more than several correct descriptive fields.

---

## 17. How the baseline informs future development

The baseline should reveal recurring weaknesses.

Examples:

```text
company missing in six cases
→ identity extraction needs attention

experience always null
→ deterministic parser does not parse numeric experience

authorization lines captured but hard blockers missed
→ restriction classification needs refinement

well-structured sections work; messy listing fails
→ section parser has format sensitivity
```

Only repeated patterns should drive parser or prompt changes.

Do not optimize the extractor solely to increase one case's score.

---

## 18. Exercises

### Exercise 1 — Trace one field

Choose `requirements.required_skills` for Case 002.

Trace:

```text
ground-truth JSON
→ deterministic listing section extraction
→ newline-separated actual value
→ list normalization
→ pairwise similarity
→ one-to-one matches
→ field F1
→ status
```

### Exercise 2 — Explain an unexpected field

Create two small lists:

```python
expected = []
actual = ["US citizenship required"]
```

Explain why the correct status is `unexpected`, not `incorrect`.

### Exercise 3 — Test punctuation normalization

Compare:

```text
Software Engineer I — Connected Medical Devices
software engineer i - connected medical devices
```

Explain why they should be exact.

### Exercise 4 — Challenge the threshold

Find one partial text comparison near `0.55`.

Describe the risks of:

- lowering the threshold,
- raising the threshold,
- and tuning it using only that example.

### Exercise 5 — Review sensitive fields

For each authorization case, inspect:

```text
expected work authorization
actual work authorization
expected hard disqualifiers
actual hard disqualifiers
```

Explain why extraction and candidate eligibility are separate decisions.

### Exercise 6 — Propose V2

Design one V2 enhancement without implementing it.

Possible directions:

- executable critical checks,
- semantic aliases,
- supplemental-field scoring,
- evidence scoring,
- or version-to-version report comparison.

State how you would prevent the enhancement from affecting production ranking.

---

## 19. Self-check questions

1. What does the evaluation runner compare?
2. Why is it separate from candidate-job matching?
3. Which fields require exact typed agreement?
4. What creates a `missing` status?
5. What creates an `unexpected` status?
6. Why are unexpected authorization values dangerous?
7. How is text normalized?
8. What similarity threshold begins partial credit?
9. Why is list matching one-to-one?
10. How are list precision and recall calculated?
11. Why is the headline percentage called agreement?
12. What is the sensitive-field slice?
13. Why are supplemental fields excluded?
14. Why is there no CI quality threshold yet?
15. Which versions must be recorded in a baseline?

### Answers

1. Extractor output against stored human-reviewed ground truth.
2. Extraction evaluation tests parsing; candidate-job matching evaluates personal fit.
3. Enums, dates, seniority, employment type, work arrangement, and experience numbers.
4. Ground truth expects a value and the extractor returns none.
5. Ground truth is empty and the extractor returns a value.
6. They can falsely reject or discourage a valid application.
7. Unicode NFKC, lowercase, word extraction, and collapsed whitespace.
8. `0.55`.
9. To prevent one broad actual line from earning credit for many independent expected items.
10. Matched similarity weight divided by actual count and expected count, respectively.
11. The small benchmark is not a universal statistical sample.
12. The same comparisons restricted to fields with material pursuit or eligibility impact.
13. The current extraction schema cannot represent them consistently.
14. The scorer and baseline need review before defining a meaningful floor.
15. At minimum, runner version and extractor version.

---

## 20. Completion criteria for Step 3D.4

Step 3D.4 is complete when:

- the deterministic runner executes all seven cases,
- one official comparison contract is documented,
- Markdown and JSON reports are supported,
- a baseline report is committed,
- tests cover comparison and command behavior,
- CI runs the offline evaluator,
- no database write occurs,
- no live API call occurs,
- and production ranking remains untouched.
