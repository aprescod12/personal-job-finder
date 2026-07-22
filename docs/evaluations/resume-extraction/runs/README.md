# Resume Extraction Evaluation Runs

This directory is reserved for reviewed résumé-extraction benchmark results.

## Recommended filename

```text
YYYY-MM-DD-<candidate-provider>-vs-deterministic.json
```

Example:

```text
2026-07-22-openai-vs-deterministic.json
```

## Generate a comparison

```bash
python manage.py evaluate_resume_extraction \
  --provider compare \
  --allow-live-openai \
  --minimum-agreement 60 \
  --output docs/evaluations/resume-extraction/runs/YYYY-MM-DD-openai-vs-deterministic.json
```

## Review before committing

Confirm that the report:

- contains only the committed synthetic benchmark cases,
- contains no API key or environment value,
- identifies the provider and model version,
- records all critical-claim and forbidden-claim results,
- includes case-level regression reasons,
- does not contain a real candidate résumé or private contact information.

Do not commit a live report automatically. Inspect the generated JSON first and commit it only when it is useful as a reviewed project decision record.
