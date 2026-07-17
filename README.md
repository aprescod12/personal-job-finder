# Amiri's Job Finder

A learning-first Django application for collecting, reviewing, and prioritizing job opportunities. Stage 1 established the reliable tracking foundation. Stage 2 now combines structured career evidence, structured job requirements, vocabulary normalization, transparent job-match analysis, dashboard ranking, human calibration, and a curated real-posting review batch.

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
- Flag where the matcher agrees with the human judgment and where it needs review
- Load an idempotent ten-posting calibration batch without pre-filling human judgments

## Transparent matching strategy

The active matcher does not depend only on exact keyword overlap. It currently uses three reviewable layers:

1. **Exact evidence:** direct matches for degrees, tools, standards, role titles, and explicit requirements.
2. **Normalized concepts:** aliases and abbreviations map to shared concepts, such as `V&V`, `verification and validation`, and `testing and validation`.
3. **Role and skill relationships:** documented links connect related work such as test engineering, validation engineering, systems engineering, quality engineering, embedded software, and firmware.

Each result shows:

- A weighted score and classification
- Evidence coverage
- Category-level points
- Direct supporting evidence
- Related or transferable evidence
- Missing evidence
- Confirmed conflicts and items that still require manual verification

The current matcher is deterministic and explainable. It does not use embeddings, an LLM, or an external API. Semantic similarity and AI-assisted extraction are later additions; they will improve recall without replacing the visible scoring rules.

## Calibration workflow

The program should not assume its first scoring weights are correct. For each real posting:

1. Review the job yourself and record **Strong match**, **Possible match**, **Weak match**, or **Not eligible**.
2. Mark the role as a priority opportunity, adjacent opportunity, outside the current priority, or unsure.
3. Save a brief note explaining your judgment.
4. Compare the saved human judgment with the matcher's score and classification.
5. Use a set of roughly 10–20 reviewed jobs before changing scoring weights or vocabulary relationships.

A calibration stores the score, classification, and opportunity lane that existed when the human judgment was saved. This preserves a usable record even after the matcher changes later.

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
6. A future AI agent can use the same validated models and scoring tools.
7. A document-review agent can analyze your resume and LinkedIn profile, extract supported skills and experiences, and identify credible adjacent career paths.

## Roadmap

- **Stage 2 next:** complete the first ten human reviews, measure where the matcher disagrees, refine weights and vocabulary from that evidence, and then add semantic similarity
- **Stage 3:** tool-using AI agents that read the profile, analyze saved jobs, and review resume and LinkedIn content
- **Stage 3 discovery expansion:** distinguish priority-role matches from adjacent opportunities that fit demonstrated background but are not the stated first choice
- **Stage 4:** external job discovery, semantic retrieval, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.
