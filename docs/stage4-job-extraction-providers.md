# Stage 4 Job Extraction Providers

## Purpose

The job-intake workflow accepts raw listing text and produces a temporary, reviewable draft. Extraction providers may use deterministic rules or an AI model, but every provider must return the same internal result shape.

No extraction provider may create or update database records. The existing human review screen remains the only path from an extracted draft to a tracked job.

## Runtime flow

```text
Pasted listing
→ extract_job(...)
→ configured BaseJobExtractor
→ JobExtractionResult
→ JSON-safe session draft
→ human review
→ JobPosting + JobRequirement
```

## Configuration

The active provider is selected in Django settings:

```python
JOB_INTAKE_EXTRACTOR = "tracker.services.job_intake.DeterministicJobExtractor"
```

The default provider is the local deterministic parser. A future AI provider can replace the dotted class path without changing the intake views or forms.

## Provider contract

Every provider must subclass `BaseJobExtractor` and implement:

```python
class ExampleExtractor(BaseJobExtractor):
    provider_key = "example"
    provider_label = "Example extractor"
    provider_version = "example-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        return self.result(
            job={...},
            requirements={...},
            evidence=[...],
            warnings=[...],
        )
```

## Standard result

The standardized result includes:

- provider key, label, version, and mode
- normalized job fields
- normalized requirement fields
- evidence explaining extracted values
- warnings identifying uncertain or missing values

Missing optional fields receive safe defaults so the review form receives a stable shape regardless of provider.

The result must be JSON serializable because the draft is stored temporarily in the Django session.

## Safety boundaries

Providers must not:

- write to the database
- mark a listing verified
- calculate or save a match result
- suppress the human review screen
- invent missing facts without a warning
- return non-serializable objects

Provider failures should raise `JobExtractionError`. The intake page then displays the failure without creating a session draft or database record.

## Future AI provider

The next AI-assisted provider should:

1. accept `JobExtractionRequest`
2. request structured output from the selected model
3. validate the response against the standard job and requirement fields
4. convert dates and enum values to session-safe strings
5. include field-level evidence or uncertainty warnings
6. return `JobExtractionResult`
7. fall back to the deterministic provider when the AI service is unavailable

The review and save workflow should remain unchanged.
