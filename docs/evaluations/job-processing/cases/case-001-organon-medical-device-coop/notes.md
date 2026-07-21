# Case 001 Notes — Organon Medical Device Engineering Co-op

## Purpose

This directory is the machine-readable benchmark representation of the first controlled Job Processing extraction test.

The original narrative baseline remains at:

```text
docs/evaluations/job-processing/evaluation-case-001-organon-medical-device-coop.md
```

That historical document records the screenshots, deterministic-versus-AI comparison, qualitative quality estimates, defects JP-001 through JP-007, and the initial live-test verdict. This case directory serves a different purpose: it provides stable source data and expected facts that code can validate and later score.

## Files

- `listing.txt` — the source posting used in both tests.
- `ground-truth.json` — the human-reviewed expected facts, critical checks, and known traps.
- `notes.md` — interpretation decisions that should not be hidden inside scoring code.

## Ground-truth decisions

### Employment type

The current `JobPosting` model has one employment-type field. The closest supported value is `internship`.

The source contains three separate facts that should not be discarded:

- intern/co-op category,
- full-time schedule,
- fixed-term employment term.

Those facts are therefore retained under `expected.supplemental` until the application has dedicated model fields.

### Industry

The current AI extraction schema returns one industry string, but useful ground truth is multi-label. The case stores controlled `industry_tags`:

- Medical devices
- Healthcare
- Women's health
- Combination products

A later evaluator can compare one extracted string against these tags without forcing the benchmark to accept vague wording such as `global healthcare company` as fully correct.

### Education

The listing requires current enrollment. The ground truth deliberately says:

> Currently enrolled in a bachelor's or master's degree in an engineering or scientific discipline

A completed bachelor's or master's degree is not equivalent.

### SolidWorks, CAD, and Instron

The listing explicitly marks CAD/SolidWorks and Instron experience as preferred. Those items must not be promoted to required qualifications.

The separate statement that the applicant should be familiar with tensile and compression test equipment is retained as an expected skill because it is phrased as an expectation outside the preferred sentence.

### Work authorization and sponsorship

The benchmark preserves both source statements:

- `US and PR Residents Only`
- `VISA Sponsorship: No`

The first statement is ambiguous and must not be silently expanded into citizenship language. The second explicitly states that sponsorship is unavailable.

The Job Processing component records the restrictions. Candidate-specific eligibility remains the responsibility of the Job Evaluation component using the candidate profile.

### Salary

The displayed `$0.00 - $0.00` range is treated as a placeholder, not meaningful compensation. The expected normalized salary field is blank, and the future evaluator should reward an appropriate warning rather than a literal zero-dollar salary.

### Experience

The section heading `Required Experience and Skills` does not establish a numeric experience requirement. Both expected experience-year fields remain null.

### Original description

The full listing was preserved during the live test. The review textarea was simply scrolled to the bottom. This case keeps full-description preservation as a critical regression check.

## Baseline results carried forward

The initial test found approximately:

- deterministic parser: 30–40% usable extraction,
- OpenAI structured extractor: approximately 90% usable extraction.

These were qualitative engineering estimates, not formal benchmark scores. Future evaluation runs must not overwrite them or present them as statistically measured accuracy.

## Open improvement items

- `JP-001` — preserve co-op, full-time, and fixed-term details.
- `JP-002` — normalize industry into useful categories.
- `JP-003` — deduplicate overlapping responsibilities.
- `JP-004` — keep skills and responsibilities in the correct categories.
- `JP-005` — separate listing restrictions from candidate-specific eligibility decisions.
- `JP-007` — record extraction latency and provider metadata.

`JP-006`, complete description preservation, passed and remains a regression check.

## Retest rule

Do not edit this ground truth merely to make a new extractor score better. Change it only when:

1. the original listing was transcribed incorrectly,
2. a human review establishes that an expected fact was wrong or ambiguous,
3. the evaluation-case schema itself changes through a documented migration.

Every extractor, prompt, model, schema, or normalization change should be tested against the same source and ground truth so improvements and regressions remain visible.
