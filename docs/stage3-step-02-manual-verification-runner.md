# Stage 3 Step 2 — Manual Verification Runner

## Purpose

This step connects the `ListingVerificationRun` history model to a manually triggered service and web workflow.

The goal is to prove that one verification request can move through a controlled lifecycle, preserve evidence, handle failures, and remain separate from the current `JobPosting` record.

## User workflow

1. Open a saved job.
2. Select **Run Verification** or **Run URL Preflight**.
3. The server creates a pending history record.
4. The runner changes it to running.
5. The configured verifier returns an observation or raises an error.
6. The runner stores a completed, review, or failed result.
7. The browser opens the saved run detail page.

The trigger endpoint accepts POST requests only.

## Current verifier

`UrlReadinessVerifier` is the intentionally limited default verifier for this step.

It checks only that:

- a job URL exists
- the URL has an `http` or `https` scheme
- the URL contains a host

It does **not**:

- make a network request
- follow redirects
- inspect employer-page content
- confirm that the role still exists
- detect an Apply button
- extract a deadline
- update the current listing status

A structurally valid URL produces a low-confidence result requiring manual review. A missing or invalid URL produces a failed run with an actionable error.

## Service interface

`run_listing_verification(job, verifier=...)` accepts any verifier implementing:

```python
class ListingVerifier(Protocol):
    version: str

    def verify(self, job: JobPosting) -> VerificationObservation:
        ...
```

This keeps orchestration separate from retrieval and interpretation. Later verifiers can fetch employer pages or use an agent without changing the run lifecycle.

## Safety boundaries

- Only one pending or running verification may exist for a job at a time.
- Verifier exceptions are saved as failed runs instead of disappearing.
- Every result preserves the verifier version and timestamp.
- Creating or completing a run never changes `JobPosting.listing_status`, deadlines, or verification notes.
- Applying a trusted result to the job remains a separate future action.

## Next step

Stage 3 Step 3 will add controlled employer-page retrieval, redirect capture, HTTP status recording, and safe response limits. Content interpretation and open/closed classification will remain separate from retrieval.
