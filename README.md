# Amiri's Job Finder

A learning-first Django application for collecting, reviewing, and prioritizing job opportunities. Stage 1 established the reliable tracking foundation. Stage 2 now combines structured career evidence, structured job requirements, vocabulary normalization, transparent job-match analysis, dashboard ranking, human calibration, software-aware MedTech strategy, and calibration reporting.

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

### Stage 2 — Career, requirements, matching, and calibration

- Maintain one editable personal career profile
- Store education, skills, target roles, target industries, preferences, priorities, and deal-breakers
- Maintain one structured requirement set for each job
- Separate required skills from preferred skills
- Record role family, seniority, industry, education, experience range, responsibilities, certifications, authorization restrictions, and hard blockers
- Preserve the original job description alongside the reviewed structured interpretation
- Normalize abbreviations, aliases, related skills, and role families through a version-controlled vocabulary
- Calculate a deterministic weighted match score without an API key or LLM
- Separate direct matches, transferable related matches, missing evidence, and blockers
- Show evidence coverage so incomplete postings do not receive misleadingly precise scores
- Label opportunities as priority roles, adjacent opportunities, or outside the stated priority
- Display match results directly on the job dashboard
- Filter by fit, opportunity lane, and human-review status
- Sort by match score, deadline, company, or date added
- Record a human judgment and save a snapshot of the matcher result for calibration
- Load an idempotent ten-posting calibration batch without pre-filling human judgments
- Apply an industry-first strategy based on the first human calibration cycle
- Recognize medical-device software, embedded software, firmware, controls, test automation, software quality, integration, and reliability as supported technical pathways
- Compare saved matcher snapshots with current results through a dedicated calibration report
- Measure fit agreement, lane agreement, improvements, regressions, changed scores, and unresolved disagreements

## Transparent matching strategy

The active matcher does not depend only on exact keyword overlap. It currently uses three reviewable layers:

1. **Exact evidence:** direct matches for degrees, tools, standards, role titles, and explicit requirements.
2. **Normalized concepts:** aliases and abbreviations map to shared concepts, such as `V&V`, `verification and validation`, and `testing and validation`.
3. **Role and skill relationships:** documented links connect related work such as test engineering, validation engineering, systems engineering, quality engineering, embedded software, firmware, and software testing.

Each result shows:

- A weighted score and classification
- Evidence coverage
- Category-level points
- Direct supporting evidence
- Related or transferable evidence
- Missing evidence
- Confirmed conflicts and items that still require manual verification

The matcher is deterministic and explainable. It does not use embeddings, an LLM, or an external API. Semantic similarity and AI-assisted extraction are later additions; they will improve recall without replacing the visible scoring rules.

## Industry-first and software-aware strategy

The first calibration cycle showed that exact role-family alignment was too strict for Amiri's actual search strategy. Medical-device product development remains the preferred destination, but entering the medical-device industry through a technically relevant function can create a credible path to an internal pivot.

Matcher version `2.2-industry-first-software` uses these weights:

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

## Calibration workflow

The program should not assume its first scoring weights are correct. For each real posting:

1. Review the job yourself and record **Strong match**, **Possible match**, **Weak match**, or **Not eligible**.
2. Mark the role as a priority opportunity, adjacent opportunity, outside the current priority, or unsure.
3. Save a brief note explaining your judgment.
4. Compare the saved human judgment with the matcher's score and classification.
5. Use a meaningful set of reviewed jobs before changing scoring weights or vocabulary relationships again.

A calibration stores the score, classification, and opportunity lane that existed when the human judgment was saved. This preserves the original baseline after matcher changes. Live dashboard and match-page scores use the newest strategy, while the saved calibration snapshot remains available for comparison. Saving the judgment again updates that snapshot to the current matcher version.

## Calibration report

Open `/calibration/` to compare all saved human reviews with the current matcher.

The report shows:

- Current fit-rating agreement percentage
- Current opportunity-lane agreement percentage
- Jobs that now align after a strategy change
- Previously aligned jobs that now require review
- Score, classification, and lane changes since the saved snapshot
- Filters for attention items, aligned results, changed results, improvements, and regressions

The report is read-only. It does not replace the original human judgment or saved matcher snapshot.

## First real-posting calibration batch

The repository includes ten curated postings researched on **2026-07-16**. They cover direct early-career roles, internships, adjacent opportunities, work-authorization blockers, and stretch positions with experience gaps.

Preview the batch without changing the database:

```bash
python manage.py load_stage2_calibration_batch --dry-run
```

Load it:

```bash
python manage.py load_stage2_calibration_batch
```

The command is idempotent and does not create human judgments. Use `--refresh` only to restore the curated fields on records originally created by this batch.

See [`docs/stage2-calibration-batch-01.md`](docs/stage2-calibration-batch-01.md) for the role list and review procedure.

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

1. You maintain accurate career preferences and background information.
2. You save jobs through the web interface.
3. You convert each posting into structured, reviewable requirements.
4. The transparent scoring service compares each job against the career profile.
5. You record your own judgment and compare it with the matcher.
6. The calibration report measures whether strategy changes improved agreement.
7. A future AI agent can use the same validated models and scoring tools.
8. A document-review agent can analyze your resume and LinkedIn profile, extract supported skills and experiences, and identify credible adjacent career paths.

## Roadmap

- **Stage 2 next:** inspect the remaining calibration-report disagreements and add controlled semantic similarity for vocabulary the explicit rules still miss
- **Stage 3:** tool-using AI agents that read the profile, analyze saved jobs, and review resume and LinkedIn content
- **Stage 3 discovery expansion:** distinguish priority-role matches from adjacent opportunities that fit demonstrated background but are not the stated first choice
- **Stage 4:** external job discovery, semantic retrieval, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.
