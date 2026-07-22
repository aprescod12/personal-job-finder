# Stage 4 Step 4 — Deduplication, Provenance, and Extraction History

## Purpose

The extraction pipeline can now create high-quality structured drafts, but a reliable intake system also needs to answer three questions:

1. Has this listing already been tracked?
2. Where did the saved information come from?
3. Which extractor, version, warnings, and human edits produced the final record?

This step adds those controls without weakening the human approval gate.

## Persistence boundary

The existing rule remains unchanged:

```text
paste listing
→ duplicate preflight
→ extraction draft
→ human review
→ one database transaction
   → JobPosting
   → JobRequirement
   → JobExtractionRun
```

No `JobPosting`, `JobRequirement`, or `JobExtractionRun` is created when the paste step begins. A discarded draft leaves no database history.

Extraction providers still do not write to the database. Provenance is written by the reviewed form only after approval.

## New app

The bounded intake-history data lives in:

```text
intake_history/
```

It is a small Django app because extraction history has a different lifecycle from the current mutable job record.

A `JobPosting` represents the current tracked opportunity. A `JobExtractionRun` represents the immutable evidence and process that created that record.

## Duplicate signals

The service calculates three conservative signals.

### 1. Exact normalized URL

The URL normalizer:

- lowercases the scheme and host,
- removes URL fragments,
- removes known tracking parameters such as `utm_*`, `gclid`, and `fbclid`,
- removes default ports,
- removes a trailing slash,
- retains job-identifying query values,
- and sorts remaining query parameters.

Example:

```text
https://Example.com/jobs/123/?utm_source=linkedin&job=abc#apply
```

becomes:

```text
https://example.com/jobs/123?job=abc
```

An exact normalized URL match is a blocking duplicate signal.

### 2. Exact normalized listing text

The complete pasted listing is normalized with Unicode normalization, case folding, and whitespace collapse. A SHA-256 fingerprint is stored instead of repeatedly comparing large text bodies.

An exact text fingerprint match is also a blocking duplicate signal.

### 3. Same role identity

After extraction, the system fingerprints normalized:

```text
title + company + location
```

This is a warning rather than a blocking match. Employers can legitimately post multiple openings with the same title and location.

## Two duplicate gates

### Before extraction

An exact URL or text match stops the workflow before the extractor runs. This matters when the configured extractor is a paid API.

The user must open the existing record and explicitly confirm that extraction should continue.

### Before saving

The same exact match is shown again on the review screen. A separate confirmation is required before a second job is created.

The two decisions are intentionally different:

1. spend an extraction request and prepare another draft,
2. create a separate tracked opportunity.

A user may reasonably approve the first and reject the second after comparing the records.

## JobExtractionRun

Each approved intake creates one linked history record containing:

- original source URL,
- normalized source URL,
- source label,
- complete original listing text,
- listing-text fingerprint,
- reviewed role-identity fingerprint,
- provider key and label,
- provider version,
- extraction mode,
- orchestration status,
- fallback and manual-review flags,
- total extraction duration,
- provider attempts,
- extraction evidence,
- extraction warnings,
- complete extracted payload,
- final reviewed payload,
- duplicate candidates,
- and whether the user explicitly overrode a duplicate warning.

The record is read-only in Django admin. It should not be edited to make a past extraction appear cleaner than it was.

## Why history is separate from JobPosting

`JobPosting` is intentionally mutable. The user can later correct the URL, title, deadline, status, or requirements.

Provenance should not silently change with it.

Keeping a separate history record preserves:

```text
what was pasted
what the provider returned
what the reviewer approved
```

That distinction will support future re-extraction and change comparison without overwriting the original evidence.

## Transaction safety

The reviewed save uses one database transaction. If the history record cannot be created, the new job and requirements are rolled back as well.

This prevents a partially saved intake where a job exists but its source history is missing.

## What the tests prove

The regression tests verify that:

- URL tracking parameters do not defeat exact duplicate detection,
- listing-text fingerprints are stable across whitespace and case differences,
- exact matches stop before the extractor is called,
- same-role matches remain non-blocking warnings,
- no history exists before review approval,
- approved intake creates one linked history record,
- reviewed dates are serialized safely,
- exact duplicates require a second confirmation before save,
- duplicate overrides are recorded,
- and discarded drafts create no job or history.

## Current limitation

This step uses exact normalized signals. It does not use fuzzy embeddings or probabilistic duplicate classification.

That is deliberate. A false positive that suppresses a legitimate opening is more harmful than showing a conservative warning.

Future improvements may add:

- employer requisition identifiers,
- explicit posting-version relationships,
- re-extraction runs attached to an existing job,
- side-by-side extracted-versus-reviewed diffs,
- and carefully evaluated fuzzy duplicate suggestions.

## Local verification

After pulling the branch:

```bash
python manage.py migrate
python manage.py check
python manage.py test
```

A focused test run is:

```bash
python manage.py test intake_history tracker.test_job_intake
```

Manual workflow:

1. Import a new listing and confirm no database records exist before approval.
2. Approve it and confirm one job, one requirement set, and one extraction run exist.
3. Paste the same URL with tracking parameters.
4. Confirm extraction is stopped before a draft is created.
5. Explicitly continue.
6. Confirm the review screen requires a second duplicate override.
7. Save only when the listing is intentionally separate.
8. Inspect the read-only extraction run in Django admin.

## Architecture boundary

Extraction history is development and operational evidence. It must never become:

- the candidate-job `/100` score,
- an automatic eligibility decision,
- proof that an extraction is correct,
- or permission to skip human review.

Its role is traceability: preserve what happened so future improvements can be measured and audited.
