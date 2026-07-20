# Job Extraction Evaluation Cases

This directory contains machine-readable benchmark cases for the Job Processing Agent.

The benchmark library exists to answer three questions:

1. What facts should an extractor recover from a listing?
2. Which mistakes are materially dangerous?
3. Did a code, prompt, schema, model, or normalization change improve the system without causing regressions?

Narrative evaluation reports may live elsewhere under `docs/evaluations/job-processing/`. The case directories here are the stable inputs used by validation and future scoring tools.

## Directory structure

Every case must use this shape:

```text
cases/
  case-NNN-short-description/
    listing.txt
    ground-truth.json
    notes.md
```

### `listing.txt`

The source job posting used for evaluation.

Rules:

- Preserve the substantive listing text.
- Do not rewrite it into cleaner prose.
- Do not add expected answers to the listing.
- Remove secrets, personal application data, or session-specific tokens.
- A copied public posting may be retained only for internal evaluation and should not be presented as a republished job board entry.

### `ground-truth.json`

The human-reviewed expected facts and critical checks.

The current schema version is:

```text
job-extraction-evaluation-case-v1
```

The JSON must contain exactly these top-level keys:

```text
schema_version
case_id
title
role_category
source
expected
critical_checks
known_traps
```

The validator intentionally rejects missing and unsupported keys. Schema changes should be deliberate and versioned rather than silently accepted.

### `notes.md`

Human interpretation decisions that should remain visible to developers.

Use it to explain:

- ambiguous language,
- normalization decisions,
- current-model limitations,
- required-versus-preferred classification,
- authorization interpretation boundaries,
- historical baseline observations,
- and why particular critical checks exist.

Do not hide policy or evaluation judgments only inside Python code.

## Ground-truth sections

### Source metadata

`source` records:

```text
company
requisition_id
captured_date
listing_file
notes_file
source_url
```

`listing_file` and `notes_file` must point to files inside the same case directory. Absolute paths and path traversal are rejected.

### Expected job fields

`expected.job` mirrors the core structured job fields currently produced by the AI extraction schema:

```text
title
company
location
employment_type
work_arrangement
salary_text
date_posted
deadline_status
application_deadline
```

Employment type, work arrangement, deadline status, and seniority must use the current Django model enum values. Dates use `YYYY-MM-DD` or `null`.

### Expected requirements

`expected.requirements` stores:

```text
role_family
seniority_level
industry_tags
required_skills
preferred_skills
required_education
preferred_education
minimum_years_experience
maximum_years_experience
responsibilities
certifications
work_authorization_requirements
hard_disqualifiers
requirement_notes
```

Lists should contain concise canonical facts, not copied paragraphs. Required and preferred qualifications must stay separate.

`industry_tags` is deliberately multi-label even though the current model has one industry string. This allows future scoring to distinguish specific, useful classification from vague company-description language.

### Supplemental facts

`expected.supplemental` preserves relevant source facts that the current Django model or extraction schema cannot represent directly:

```text
employment_category
schedule
employment_term
requisition_id
openings
relocation
travel
driving_license_required
```

Supplemental fields should not be discarded merely because the current model lacks a destination. A later schema revision may promote them into first-class fields.

## Critical checks

Each `critical_checks` entry contains:

```text
id
severity
description
expected_behavior
evidence_quotes
```

Allowed severities:

```text
critical
major
minor
```

Every evidence quote must appear verbatim in `listing.txt`. This prevents a benchmark from claiming source support that is not present.

Use `critical` for errors that could materially affect identity, eligibility, required qualifications, deadlines, or original-source preservation.

## Known traps

Each `known_traps` entry contains:

```text
id
description
forbidden_interpretations
```

Known traps document plausible but unsupported readings, such as:

- treating a section heading as a years-of-experience requirement,
- promoting preferred qualifications to required,
- converting ambiguous residency language into citizenship language,
- treating placeholder compensation as real salary,
- or extracting boilerplate as candidate qualifications.

Future evaluators can use these entries to identify unsupported claims and wrong-category errors.

## Validation

Validate the complete case library with:

```bash
python manage.py validate_job_extraction_cases
```

Validate an alternate directory with:

```bash
python manage.py validate_job_extraction_cases --root /path/to/cases
```

Validation checks include:

- valid JSON,
- exact schema keys,
- matching directory and case IDs,
- safe relative file names,
- required files,
- nonempty listing text,
- model enum values,
- ISO dates,
- experience ranges,
- duplicate IDs and list values,
- critical-check severities,
- and evidence quotes present in the source listing.

GitHub Actions runs this validation before the normal Django test suite.

## Adding a new case

1. Create a new `case-NNN-short-description` directory.
2. Add the unchanged substantive listing as `listing.txt`.
3. Copy the current ground-truth structure from an existing case.
4. Review every expected field against the listing.
5. Add critical checks for identity, eligibility, education, experience, deadlines, and required/preferred separation where relevant.
6. Add known traps for plausible unsupported interpretations.
7. Explain ambiguous decisions in `notes.md`.
8. Run the validation command.
9. Add automated tests when the case introduces a new schema edge condition.
10. Review the case separately from extractor output; do not edit expected facts merely to improve a score.

## Change control

Ground truth may change only when:

- the source listing was transcribed incorrectly,
- human review establishes that an expected fact was wrong,
- an ambiguity is resolved and documented,
- or the case schema changes through an explicit versioned migration.

Extractor outputs and run reports must never overwrite source listings or ground truth.
