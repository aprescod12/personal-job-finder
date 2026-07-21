# Deterministic Job Extraction Baseline — 2026-07-21

## Run identity

- Runner: `job-extraction-evaluator-v1`
- Extractor: `deterministic-intake-v1`
- Evaluation cases: 7
- Compared fields: 161
- External API calls: 0
- Database writes: 0

This report measures agreement with stored benchmark ground truth. It is not a candidate-job match score or a universal accuracy estimate.

## Headline results

| Measure | Result |
|---|---:|
| Overall field agreement | 48.56% |
| Eligibility-sensitive field agreement | 39.88% |
| Exact fields | 64 |
| Partial fields | 17 |
| Missing fields | 44 |
| Unexpected fields | 2 |
| Incorrect fields | 34 |

## Results by case

| Case | Overall | Sensitive |
|---|---:|---:|
| `case-001-organon-medical-device-coop` | 54.82% | 38.41% |
| `case-002-embedded-firmware-entry-level` | 45.34% | 33.76% |
| `case-003-quality-validation-engineer` | 44.14% | 42.40% |
| `case-004-medical-device-software` | 47.30% | 32.28% |
| `case-005-general-software-poor-format` | 52.52% | 44.44% |
| `case-006-ambiguous-sponsorship` | 49.77% | 50.13% |
| `case-007-citizenship-clearance` | 46.00% | 37.72% |

## Results by field

| Field | Agreement |
|---|---:|
| `job.title` | 37.14% |
| `job.company` | 0.00% |
| `job.location` | 0.00% |
| `job.employment_type` | 42.86% |
| `job.work_arrangement` | 100.00% |
| `job.salary_text` | 100.00% |
| `job.date_posted` | 85.71% |
| `job.deadline_status` | 57.14% |
| `job.application_deadline` | 100.00% |
| `requirements.role_family` | 34.35% |
| `requirements.seniority_level` | 14.29% |
| `requirements.industry_tags` | 0.00% |
| `requirements.required_skills` | 25.21% |
| `requirements.preferred_skills` | 30.23% |
| `requirements.required_education` | 71.43% |
| `requirements.preferred_education` | 100.00% |
| `requirements.minimum_years_experience` | 14.29% |
| `requirements.maximum_years_experience` | 57.14% |
| `requirements.responsibilities` | 31.45% |
| `requirements.certifications` | 100.00% |
| `requirements.work_authorization_requirements` | 28.82% |
| `requirements.hard_disqualifiers` | 57.14% |
| `requirements.requirement_notes` | 29.59% |

## Main findings

The parser correctly handled work arrangement and explicit deadline values, and it remained conservative for certifications and preferred education. Required education was also recovered in most structured cases.

The benchmark exposed repeated weaknesses:

1. Company and location were missing in every case.
2. The synthetic disclaimer was selected as the title in Cases 002–007.
3. Role family inherited incorrect title text.
4. Mentions of internships as acceptable experience often caused incorrect internship classification.
5. Numeric experience requirements were usually missed.
6. Required and preferred qualifications were only partially normalized.
7. Responsibilities were sometimes missed or contaminated by later sections.
8. Authorization text was found inconsistently and sometimes included nearby travel or license text.
9. Explicit eligibility restrictions were often not converted into structured blockers.
10. Industry normalization was absent.

The 39.88% sensitive-field agreement confirms that the deterministic extractor should remain a visibly labeled fallback requiring human review. It should not make unattended eligibility decisions or feed unreviewed requirements into the production matcher.

## Reproduction

Run the full human-readable report:

`python manage.py evaluate_job_extraction --format markdown`

Run the machine-readable report:

`python manage.py evaluate_job_extraction --format json`

The generated report includes every expected and actual field for each case. This committed summary preserves the stable baseline without storing the large generated output.

## Interpretation boundary

This baseline does not rank jobs, alter the production matcher, determine candidate eligibility, approve an intake draft, write application data, or call a model provider.
