# Amiri's Job Finder

A learning-first Django application for collecting, reviewing, and tracking job opportunities. Stage 1 established the reliable job-tracking foundation. Stage 2 adds a structured career profile that will support transparent job-match analysis.

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

### Stage 2 — Career profile foundation

- Maintain one editable personal career profile
- Store education, skills, target roles, and target industries
- Record experience level, location preferences, work arrangement, employment type, and minimum salary
- Separate positive priorities from hard deal-breakers
- Seed the profile with Amiri's known engineering and biomedical background
- Normalize repeated list entries before saving
- Use the profile as the future source of truth for job-match scoring

Match scoring is not active yet. It will be added as the next Stage 2 feature.

## Planned matching strategy

The matcher will not depend only on exact keyword overlap. It will use several layers so that related vocabulary can still match:

1. **Exact evidence:** direct matches for important degrees, tools, certifications, and explicit requirements.
2. **Normalized concepts:** map aliases and abbreviations to shared concepts, such as `V&V` and `verification and validation`, or `embedded software` and `firmware`.
3. **Role and skill families:** recognize broader relationships between related work, such as test engineering, systems verification, validation engineering, and quality engineering.
4. **Semantic similarity:** compare the meaning of profile statements and job requirements even when the wording differs.
5. **AI-assisted extraction:** later agents will convert resumes, LinkedIn profiles, and job descriptions into structured evidence before the transparent scoring rules are applied.

The interface should show which wording or evidence caused each match so that semantic generalization remains reviewable rather than becoming a hidden black-box score.

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

The `JobPosting` and `CareerProfile` models create the shared foundation for later AI workflows:

1. You manually maintain accurate career preferences and background information.
2. You save jobs through the web interface.
3. A transparent scoring service compares each job against the career profile.
4. A future AI agent can use the same validated models and scoring tools.
5. A document-review agent can analyze your resume and LinkedIn profile, extract supported skills and experiences, and identify credible adjacent career paths.

## Roadmap

- **Stage 2 next:** structured job requirements, vocabulary normalization, and transparent job-match scoring
- **Stage 3:** tool-using AI agents that read the career profile, analyze saved jobs, and review resume and LinkedIn content
- **Stage 3 discovery expansion:** distinguish priority-role matches from adjacent opportunities that fit your demonstrated background but are not your stated first choice
- **Stage 4:** external job discovery, semantic retrieval, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.