# Amiri's Job Finder

A learning-first Django application for collecting, reviewing, and prioritizing job opportunities. Stage 1 established the reliable tracking foundation. Stage 2 now combines structured career evidence, structured job requirements, vocabulary normalization, transparent job-match analysis, dashboard ranking, human calibration, software-aware MedTech strategy, controlled semantic similarity, and blind holdout validation.

## Current features

### Stage 1 — Job tracker

- Create, view, edit, and delete job records
- Track application status from discovery through offer or rejection
- Store job source, employment type, work arrangement, salary text, dates, description, and personal notes
- Record next actions and deadlines
- Search jobs and filter by application status
- Responsive user interface
- Django Admin registration for development and data recovery
- Automated model and view tests

### Stage 2 — Career, requirements, matching, and validation

- Maintain one editable personal career profile
- Store education, skills, target roles, target industries, preferences, priorities, and deal-breakers
- Maintain one structured requirement set for each job
- Separate required skills from preferred skills
- Record role family, seniority, industry, education, experience range, responsibilities, certifications, authorization restrictions, and hard blockers
- Preserve the original job description alongside the reviewed structured interpretation
- Normalize abbreviations, aliases, related skills, and role families through a version-controlled vocabulary
- Calculate a deterministic weighted match score without an API key or LLM
- Separate direct, rule-related, semantic, missing, and blocker evidence
- Show evidence coverage so incomplete postings do not receive misleadingly precise scores
- Label opportunities as priority roles, adjacent opportunities, or outside the stated priority
- Display match results directly on the job dashboard
- Filter by fit, opportunity lane, human-review status, and dataset source
- Record a human judgment and save a snapshot of the matcher result for calibration
- Apply an industry-first strategy based on the first human calibration cycle
- Recognize medical-device software, embedded software, firmware, controls, test automation, software quality, integration, and reliability as supported technical pathways
- Compare saved matcher snapshots with current results through a dedicated calibration report
- Use a controlled local semantic layer to recognize selected technical paraphrases without weakening hard requirements
- Load a separate ten-job unseen validation batch without pre-filling judgments
- Hide holdout scores, classifications, lanes, and evidence until an independent judgment is saved
- Isolate holdout metrics from the original calibration data in the calibration report

## Transparent matching strategy

The active matcher uses four reviewable layers:

1. **Exact evidence:** direct matches for degrees, tools, standards, role titles, and explicit requirements.
2. **Normalized concepts:** aliases and abbreviations map to shared concepts, such as `V&V`, `verification and validation`, and `testing and validation`.
3. **Rule-based relationships:** documented links connect related work such as test engineering, validation engineering, systems engineering, quality engineering, embedded software, firmware, and software testing.
4. **Controlled semantic evidence:** local technical tokens, bigrams, and version-controlled engineering concept families identify selected paraphrases that the explicit vocabulary misses.

Each result shows a weighted score, classification, evidence coverage, category points, direct evidence, rule-related evidence, controlled semantic evidence, gaps, and eligibility blockers.

The matcher is deterministic and explainable. It does not use an LLM, external API, downloaded language model, or hidden prompt.

## Industry-first and software-aware strategy

Medical-device product development remains the preferred destination, but entering the medical-device industry through a technically relevant function can create a credible path to an internal pivot.

Matcher version `2.3-controlled-semantic` uses these category weights:

| Category | Weight |
|---|---:|
| Target industry | 20 |
| Required skills | 20 |
| Education | 15 |
| Experience | 15 |
| Exact or transferable role function | 10 |
| Preferred skills | 10 |
| Location and work arrangement | 5 |
| Employment type | 5 |

Technical MedTech functions such as quality, product safety, validation, verification, test, systems, manufacturing, process, reliability, regulatory, design assurance, clinical engineering, applications engineering, medical-device software, embedded software, firmware, controls, test automation, software quality, and integration can receive transferable-function credit when the posting is also inside a target or closely related industry.

Commercial roles do not receive technical-function credit merely because the employer operates in medical devices. General software roles outside healthcare remain valid skill-based opportunities, but they do not automatically outrank strong medical-device roles in strategic priority.

## Controlled semantic similarity

The semantic layer only revisits selected role, skill, education, and industry gaps. It uses local token, bigram, and engineering-family vectors.

Semantic evidence is deliberately limited:

- Maximum strength is `0.65`
- It is always labeled separately from direct and rule-related evidence
- It cannot satisfy experience requirements
- It cannot override work-authorization conflicts
- It cannot satisfy certifications, security clearances, licenses, or hard disqualifiers
- It cannot independently turn a role into a direct priority match

## Calibration workflow

A calibration stores the score, classification, and opportunity lane that existed when the human judgment was saved. This preserves the baseline after matcher changes. Live scores use the newest strategy, while the saved snapshot remains available for comparison.

Open `/calibration/` to compare human reviews with the current matcher. The report supports separate views for:

- the original tuning batch
- the unseen validation holdout
- manually entered and other jobs

## Original calibration batch

The repository includes ten calibration postings researched on **2026-07-16**.

```bash
python manage.py load_stage2_calibration_batch --dry-run
python manage.py load_stage2_calibration_batch
```

See [`docs/stage2-calibration-batch-01.md`](docs/stage2-calibration-batch-01.md).

## Unseen validation batch

The repository also includes ten holdout opportunities researched on **2026-07-17**. These jobs were not used to design the weights, role pathways, vocabulary, or semantic concept families.

```bash
python manage.py load_stage2_validation_batch --dry-run
python manage.py load_stage2_validation_batch
```

Use this dashboard view:

```text
SOURCE: Validation holdout
CALIBRATION: Not yet reviewed
SORT: Company A–Z
```

Unreviewed holdout jobs do not render the calculated score, classification, opportunity lane, evidence counts, or detailed matcher evidence. Saving the independent judgment records the hidden matcher snapshot and then reveals the comparison.

Do not change matcher rules until all ten holdout jobs are reviewed. See [`docs/stage2-validation-batch-01.md`](docs/stage2-validation-batch-01.md).

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```

Open `http://127.0.0.1:8001/`.

## Run tests

```bash
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

## Data model direction

The `JobPosting`, `JobRequirement`, `CareerProfile`, and `JobCalibration` models create the shared foundation for later AI workflows:

1. Maintain accurate career preferences and background information.
2. Save jobs through the web interface.
3. Convert postings into structured, reviewable requirements.
4. Compare each job against the career profile.
5. Record independent judgments and matcher snapshots.
6. Validate the matcher on data that was not used for tuning.
7. Let future AI agents use the same validated models and scoring tools.
8. Review resume and LinkedIn evidence before adding it to the candidate profile.

## Roadmap

- **Stage 2 next:** complete the unseen validation reviews, record matcher-version history in saved snapshots, and add the candidate-evidence foundation for resume and LinkedIn review
- **Stage 3:** tool-using AI agents that read the profile, analyze saved jobs, and review resume and LinkedIn content
- **Stage 3 discovery expansion:** distinguish priority-role matches from adjacent opportunities that fit demonstrated background but are not the stated first choice
- **Stage 4:** external job discovery, semantic retrieval, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.
