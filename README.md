# Amiri's Job Finder

A learning-first Django application for collecting, verifying, reviewing, and prioritizing job opportunities. Stage 1 established the tracking foundation. Stage 2 now combines structured career evidence, structured job requirements, listing reliability, transparent job-match analysis, human calibration, controlled semantic similarity, blind validation, and weight-model comparison.

## Architecture source of truth

The final product uses seven logical agents inside one controlled Django workflow:

1. Coordinator Agent
2. Candidate Profile Agent
3. Job Discovery Agent
4. Job Processing Agent
5. Job Evaluation Agent
6. Project Relevance and Development Agent
7. Presentation and Tracking Agent

See [`docs/architecture/final-agent-architecture.md`](docs/architecture/final-agent-architecture.md) for responsibilities, boundaries, workflow contracts, implementation status, and change-control requirements.

Any decision that adds, removes, renames, combines, splits, or materially changes an agent must update that architecture document in the same pull request.

## Current features

### Stage 1 — Job tracker

- Create, view, edit, and delete job records
- Track application status from discovery through offer or rejection
- Store job source, employment type, work arrangement, salary, dates, description, and notes
- Record next actions and deadlines
- Search, filter, and sort the application pipeline
- Responsive interface and Django Admin support
- Automated model and view tests

### Stage 2 — Verification, matching, and validation

- Maintain one editable career profile
- Store education, skills, target roles, industries, preferences, priorities, and deal-breakers
- Maintain one structured requirement set for each job
- Separate required skills from preferred skills
- Record role family, seniority, industry, education, experience, responsibilities, certifications, authorization restrictions, and hard blockers
- Calculate a deterministic weighted score without an API key or LLM
- Separate direct, rule-related, semantic, missing, and blocker evidence
- Recognize MedTech product development, quality, product safety, validation, manufacturing, systems, embedded software, firmware, controls, test automation, and other technical entry paths
- Record five human fit judgments: **Strong**, **Good**, **Possible**, **Weak**, and **Not eligible**
- Preserve matcher snapshots for calibration
- Compare the current matcher with saved judgments
- Run a blind ten-job holdout validation workflow
- Keep Model A live while retaining Model B for measured comparison
- Verify whether each listing is open, closed, expired, broken, on the wrong page, or still unverified
- Record when a listing was last checked
- Distinguish confirmed deadlines, rolling deadlines, deadlines not stated, and deadlines still unknown
- Highlight stale listings, link problems, expired roles, and deadlines within seven days

## Listing reliability workflow

A match score is not actionable unless the role can still be applied to. Each job now has two separate states:

1. **Application status** — saved, preparing, applied, interviewing, and so on.
2. **Listing status** — unverified, open, closed, expired, broken link, or wrong company page.

Open listings should be rechecked at least every seven days. The dashboard flags listings that have never been checked, have become stale, have an unknown deadline, or point to an unreliable page.

Use the verification page for a job to confirm:

- the URL opens the exact employer role page
- applications are still accepted
- the deadline is confirmed, rolling, not stated, or unknown
- any verification notes that explain the result

A confirmed past deadline makes an otherwise open listing effectively expired.

## Transparent matching strategy

The active matcher uses four reviewable layers:

1. **Exact evidence:** direct matches for degrees, tools, standards, titles, and explicit requirements.
2. **Normalized concepts:** aliases and abbreviations map to shared concepts.
3. **Rule-based relationships:** documented links connect related technical functions.
4. **Controlled semantic evidence:** local technical tokens and version-controlled concept families identify selected paraphrases.

Each result shows a score, fit classification, evidence coverage, category points, direct evidence, related evidence, controlled semantic evidence, gaps, and eligibility blockers.

The matcher is deterministic and explainable. It does not use an LLM, external API, downloaded language model, or hidden prompt.

## Active and experimental weight models

**Model A remains the live matcher:**

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

**Model B is retained for comparison:** required skills increase to 25 and industry decreases to 15. It can be evaluated at `/calibration/weights/`, but the report does not automatically change the live matcher.

## Five-level human calibration

The human judgment scale now mirrors the matcher:

- **Strong match:** clearly qualified with minimal meaningful gaps
- **Good match:** qualified and worth applying, with minor gaps or a less direct pathway
- **Possible match:** credible but uncertain or dependent on how requirements are interpreted
- **Weak match:** substantial gaps make an application low priority
- **Not eligible:** a confirmed blocker prevents a valid application

Older Strong judgments are preserved. They can be updated to Good where the original interface forced both matcher classifications into one human option.

## Controlled semantic similarity

The semantic layer only revisits selected role, skill, education, and industry gaps. Semantic evidence is capped at `0.65` and cannot satisfy experience, work authorization, certifications, security clearances, licenses, or hard disqualifiers.

## Calibration and validation

Open `/calibration/` to compare saved human reviews with the current matcher. The report supports separate views for the original calibration batch, the unseen validation holdout, and manually entered jobs.

The repository includes two ten-job datasets:

```bash
python manage.py load_stage2_calibration_batch --dry-run
python manage.py load_stage2_calibration_batch
python manage.py load_stage2_validation_batch --dry-run
python manage.py load_stage2_validation_batch
```

The holdout workflow hides the score, classification, lane, and evidence until an independent judgment is saved.

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

The `JobPosting`, `JobRequirement`, `CareerProfile`, and `JobCalibration` models create the foundation for later AI workflows:

1. Verify that a posting is current and actionable.
2. Maintain accurate career preferences and evidence.
3. Convert postings into structured requirements.
4. Compare each job against the career profile.
5. Record independent judgments and matcher snapshots.
6. Validate changes on data that was not used for tuning.
7. Let future AI agents use the same verified records and scoring tools.
8. Review resume and LinkedIn evidence before adding it to the candidate profile.

## Current roadmap

The detailed roadmap and ownership boundaries are maintained in the architecture source of truth.

The recommended implementation sequence from the current state is:

1. Test the OpenAI job-extraction backend with one controlled listing.
2. Add deterministic fallback and disclose which extractor was used.
3. Add duplicate detection.
4. Add job-processing history and provenance.
5. Build resume ingestion and candidate-evidence review.
6. Build the Job Discovery Agent and discovery inbox.
7. Strengthen evaluation versioning and actionable explanations.
8. Build the Project Relevance and Development Agent.
9. Expand tasks, reminders, and application tracking.
10. Build the Coordinator Agent over stable component interfaces.
11. Complete production readiness and deployment.

The application will not submit applications, contact employers, or change important records without explicit approval.
