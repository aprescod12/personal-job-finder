# Amiri's Job Finder

A learning-first Django application for collecting, reviewing, and tracking job opportunities. Stage 1 established the reliable job-tracking foundation. Stage 2 is building the structured evidence needed for transparent job-match analysis.

## Current features

### Stage 1 — Job tracker

- Create, view, edit, and delete job records
- Track application status from discovery through offer or rejection
- Store job source, employment type, work arrangement, salary text, dates, description, and personal notes
- Record next actions and deadlines
- Search jobs and filter by application status
- Dashboard counts for total, saved, applied, and interview-stage jobs
- Responsive user interface
- Django Admin registration for development and data recovery
- Automated model and view tests

### Stage 2 — Career and requirement foundations

- Maintain one editable personal career profile
- Store education, skills, target roles, target industries, preferences, priorities, and deal-breakers
- Maintain one structured requirement set for each job
- Separate required skills from preferred skills
- Record role family, seniority, industry, education, experience range, responsibilities, certifications, authorization restrictions, and hard blockers
- Normalize repeated list entries before saving
- Preserve the original job description alongside the reviewed structured interpretation

Match scoring is not active yet. The next Stage 2 unit will compare the career profile with these structured job requirements.

## Planned matching strategy

The matcher will not depend only on exact keyword overlap. It will use several layers so related vocabulary can still match:

1. **Exact evidence:** direct matches for important degrees, tools, certifications, and explicit requirements.
2. **Normalized concepts:** aliases and abbreviations mapped to shared concepts, such as `V&V` and `verification and validation`.
3. **Role and skill families:** broader relationships between related work such as test engineering, systems verification, validation engineering, and quality engineering.
4. **Semantic similarity:** meaning-based comparison when profile and posting vocabulary differ.
5. **AI-assisted extraction:** later agents will convert resumes, LinkedIn profiles, and job descriptions into structured evidence before transparent scoring rules are applied.

The interface should show which evidence caused a match so semantic generalization remains reviewable rather than becoming a hidden black-box score.

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
python manage.py test
```

## Data model direction

The `JobPosting`, `JobRequirement`, and `CareerProfile` models create the shared foundation for later AI workflows:

1. You maintain accurate career preferences and background information.
2. You save jobs through the web interface.
3. You convert each posting into structured, reviewable requirements.
4. A transparent scoring service compares each job against the career profile.
5. A future AI agent can use the same validated models and scoring tools.
6. A document-review agent can analyze your resume and LinkedIn profile, extract supported skills and experiences, and identify credible adjacent career paths.

## Roadmap

- **Stage 2 next:** vocabulary normalization and transparent job-match scoring
- **Stage 3:** tool-using AI agents that read the profile, analyze saved jobs, and review resume and LinkedIn content
- **Stage 3 discovery expansion:** distinguish priority-role matches from adjacent opportunities that fit demonstrated background but are not the stated first choice
- **Stage 4:** external job discovery, semantic retrieval, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.
