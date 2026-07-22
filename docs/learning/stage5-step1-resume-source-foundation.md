# Stage 5 Step 1 — Resume Source Foundation

## Goal

Stage 5 begins the Candidate Profile Agent. The final agent will read a resume, convert it into structured candidate evidence, compare that evidence with job requirements, and refresh the reusable candidate profile when the resume changes.

This first step does **not** extract resume content yet. It establishes the source-control boundary that later extraction depends on.

The workflow introduced here is:

```text
resume file
    ↓
validate file type and size
    ↓
calculate SHA-256 fingerprint
    ↓
check for exact duplicate content
    ↓
store immutable source version
    ↓
select one active resume source
    ↓
future extraction and human review
```

## Why source storage comes before extraction

An extraction pipeline is only trustworthy when it can answer:

- Which exact resume produced this candidate claim?
- Was the source file changed or replaced?
- Which resume version is currently active?
- Can the original document be reopened for review?
- Did an upload update the profile automatically?

Without a stored source and fingerprint, later structured evidence cannot be audited reliably.

## Existing state before this step

The project already had a singleton `CareerProfile` model containing:

- professional identity,
- education summary,
- target roles and industries,
- skills,
- search preferences,
- work authorization,
- priorities and deal breakers.

That model is useful for matching, but it is manually maintained and flattened. It does not identify which resume supports each field or preserve resume versions.

## New application boundary

A separate Django app named `candidate_profile` now owns resume-source records.

This separation matters:

- `tracker.CareerProfile` remains the approved structured source of truth used by matching.
- `candidate_profile.ResumeSource` stores original resume evidence.
- Future extraction runs will sit between those two layers.

A resume file is evidence. It is not automatically the structured profile.

## `ResumeSource` model

Each stored resume version records:

- the associated `CareerProfile`,
- the uploaded file,
- original filename,
- optional human label,
- browser-provided content type,
- byte size,
- SHA-256 fingerprint,
- active/inactive status,
- review status,
- optional notes,
- creation and update timestamps.

## Why SHA-256 is used

A filename is not a reliable identity.

The same file can be renamed:

```text
Amiri_Resume.pdf
Medical_Device_Resume.pdf
Resume_Final_Final.pdf
```

SHA-256 hashes the file bytes. Identical bytes produce the same fingerprint regardless of filename.

Conceptually:

```text
SHA256(file bytes) → 64-character fingerprint
```

The upload form reads the file in chunks:

```python
for chunk in document.chunks():
    digest.update(chunk)
```

Chunked reading avoids loading the entire document into memory at once.

After hashing, the file pointer is reset:

```python
document.seek(0)
```

This is necessary because Django still needs to save the uploaded file after it has been read for hashing.

## Duplicate protection

The form checks whether the same profile already has the calculated SHA-256 fingerprint.

The database also has a unique constraint across:

```text
(profile, sha256)
```

The two layers serve different purposes:

- Form validation provides a clear user-facing message.
- The database constraint protects integrity during races or future code changes.

## File validation

The initial accepted formats are:

- PDF (`.pdf`),
- Microsoft Word (`.docx`),
- plain text (`.txt`).

The maximum file size is 5 MB.

This step checks the extension and size. It does not yet inspect or parse the internal document structure.

Content parsing belongs in a later provider layer so that parsing behavior can be versioned and tested separately.

## Resume versioning

Multiple different resume files may be stored because candidates often maintain tailored versions.

Examples:

- Medical Device Resume,
- Embedded Systems Resume,
- Test and Validation Resume,
- General Engineering Resume.

Only one version can be active for the profile at a time.

The database enforces this with a conditional unique constraint:

```text
one active ResumeSource per CareerProfile
```

When a new active version is uploaded, the previous active version is deactivated within the same database transaction.

An older stored version can later be made active explicitly.

## Why uploaded files use generated storage names

The original filename is stored as metadata, but the filesystem path uses a generated UUID.

Example:

```text
media/resumes/profile-1/7de85d...c92.pdf
```

This avoids collisions when different uploads use names such as `Resume.pdf`.

It also prevents the application from relying on user-provided filenames as storage identifiers.

## Local media configuration

Django now uses:

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

During local development, `config/urls.py` serves media only when `DEBUG` is enabled.

The `media/` directory is ignored by Git. Resume files must never be committed to the repository.

Production storage will need a protected media service and access controls. Django's development media server is not a production file-serving solution.

## Human and AI safety boundary

Uploading a resume currently does **not**:

- parse PDF or DOCX text,
- call OpenAI or another external provider,
- infer skills,
- add employment history,
- change education,
- change work authorization,
- update `CareerProfile`,
- change any job-match score.

The success message states that the source was stored and that no extraction ran.

This boundary is covered by automated tests.

## Read-only administration

Resume-source records are visible in Django admin for auditing.

Admin users cannot add or delete them through the admin interface. Uploads and active-version changes go through the controlled application workflow.

The stored file and fingerprint remain reviewable.

## Automated tests

The Stage 5 Step 1 tests cover:

1. The page clearly discloses source-only behavior.
2. The first resume is stored, fingerprinted, and made active.
3. Uploading does not modify `CareerProfile`.
4. Identical file bytes cannot be stored twice under different names.
5. Unsupported extensions are rejected.
6. A new active upload deactivates the previous version.
7. A stored older version can be activated explicitly.

The tests use a temporary media directory so test uploads do not enter the developer's real `media/` folder.

## Local verification commands

After merging this step:

```bash
python manage.py migrate
python manage.py check
python manage.py test candidate_profile
```

Run the server:

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/resume/
```

## Manual test plan

### Test 1 — First upload

Upload a PDF, DOCX, or TXT resume smaller than 5 MB.

Expected:

- success message appears,
- one resume source exists,
- it is marked active,
- original filename and file size appear,
- the stored file opens,
- career-profile fields remain unchanged.

### Test 2 — Exact duplicate

Upload the same file again, even under a different filename.

Expected:

- duplicate message appears,
- no second version is created.

### Test 3 — New version

Upload a file whose contents differ and leave the active checkbox selected.

Expected:

- the new version is active,
- the old version remains stored but inactive,
- only one source is active.

### Test 4 — Reactivate an older version

Click **Make Active** on the older source.

Expected:

- the older source becomes active,
- the newer source becomes inactive,
- no profile fields change.

## Next Stage 5 step

Stage 5 Step 2 should introduce a resume-extraction contract analogous to the job-extraction contract:

```text
ResumeExtractionRequest
ResumeExtractionResult
BaseResumeExtractor
```

The output should be a structured, reviewable draft containing evidence such as:

- contact and professional identity,
- education entries,
- experience entries,
- project entries,
- technical skills,
- certifications and standards,
- leadership and activities,
- evidence snippets tied to each claim.

The extractor must remain read-only. A later human-review step will decide which evidence is accepted into the reusable candidate profile.
