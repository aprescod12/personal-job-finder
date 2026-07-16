# Personal Job Finder

A learning-first Django application for collecting, reviewing, and tracking job opportunities. Stage 1 establishes the reliable data and interface layer that a future AI job-finding agent will use.

## Stage 1 features

- Create, view, edit, and delete job records
- Track application status from discovery through offer or rejection
- Store job source, employment type, work arrangement, salary text, dates, description, and personal notes
- Record next actions and deadlines
- Search jobs and filter by application status
- Dashboard counts for total, saved, applied, and interview-stage jobs
- Responsive user interface
- Django Admin registration for development and data recovery
- Automated model and view tests

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

The `JobPosting` model is the shared foundation for both workflows:

1. You can manually save a job through the web interface.
2. A future AI agent can call a controlled tool that creates the same validated database record.

## Roadmap

- **Stage 2:** personal career profile and structured job-match analysis
- **Stage 3:** tool-using AI agent that reads the profile, analyzes saved jobs, and updates records
- **Stage 4:** external job discovery, deduplication, scheduled searches, and notifications

The agent will not submit applications, contact employers, or change important records without explicit approval.
