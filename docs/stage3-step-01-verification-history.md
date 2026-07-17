# Stage 3 Step 1 — Listing Verification History

Stage 3 begins with an audit trail for future listing checks.

## Purpose

The current `JobPosting` fields show the latest accepted listing state. A future agent should also preserve what it observed, how confident it was, and whether a person reviewed the conclusion.

`ListingVerificationRun` stores one verification attempt. Each job can have many runs over time.

## Information stored

A run can record:

- Manual, agent, or scheduled trigger
- Pending, running, completed, review, or failed status
- Requested URL and final URL
- HTTP status code
- Detected title and company
- Detected listing and deadline states
- Detected deadline date
- Whether an application action was found
- Confidence and review state
- Human-readable and structured evidence
- Error details, verifier version, and timing

## Safety boundary

Creating a run does not change the current job listing status, deadline, or verification notes. A later service will decide when a result is reliable enough to apply to the current job record.

## Next step

Stage 3 Step 2 will add a manual Run Verification action and a deterministic service interface. The first version will create and complete history records without scheduled background jobs.
