# Stage 5 Step 2 — Resume Extraction Contract

## Goal

This step introduces the first AI-ready layer of the Candidate Profile Agent.

The system can now:

1. read a stored PDF, DOCX, or TXT resume locally,
2. convert the document into normalized text,
3. pass that text through a versioned extraction-provider contract,
4. produce a structured candidate-evidence draft,
5. show the draft with evidence and warnings,
6. discard the draft without changing the approved profile.

The default extractor remains deterministic. A future AI implementation can replace it without changing the view, session workflow, or document-reader layer.

## The two extraction problems

Resume ingestion contains two different technical problems:

```text
binary document
    ↓
document parsing
    ↓
plain text
    ↓
semantic extraction
    ↓
structured candidate evidence
```

### Document parsing

Document parsing answers:

> What text is physically present in this file?

The local readers are:

- `pypdf` for PDF,
- `python-docx` for DOCX,
- UTF-8 decoding for TXT.

This layer does not decide whether a line is a skill, degree, project, or experience claim.

### Semantic extraction

Semantic extraction answers:

> What candidate claims does the text appear to contain?

That responsibility belongs to a provider implementing `BaseResumeExtractor`.

Keeping these concerns separate matters because an AI model should not need access to Django file storage or model objects. It should receive a bounded text request and return a validated result.

## The provider contract

Every provider receives a `ResumeExtractionRequest` containing:

- normalized document text,
- stored source ID,
- source SHA-256 fingerprint,
- original filename,
- human label,
- document-reader key and version.

The fingerprint ties the result to the exact uploaded bytes.

Every provider returns a `ResumeExtractionResult` containing:

- provider key,
- provider label,
- provider version,
- extraction mode,
- identity candidates,
- structured profile candidates,
- field-level evidence,
- warnings.

The result must be JSON serializable before it can enter the review workflow.

## Why providers cannot write to the database

The provider method is deliberately narrow:

```python
def extract(
    self,
    request: ResumeExtractionRequest,
) -> ResumeExtractionResult:
    ...
```

It does not receive:

- an HTTP request,
- a `CareerProfile`,
- a `ResumeSource` model instance,
- a database transaction,
- permission to save candidate claims.

This creates an architectural safety boundary:

```text
provider output ≠ approved candidate profile
```

A provider may suggest claims. Only a later human-review workflow may approve them.

## Structured output shape

The initial result separates identity from reusable profile evidence.

```text
identity
├── full_name
├── email
├── phone
├── location
└── links

profile
├── professional_summary
├── education
├── experience
├── projects
├── skills
├── certifications
└── leadership
```

Section entries preserve `source_text`. This is essential because a reviewer must be able to compare a proposed claim with the exact resume wording.

## Evidence is part of the output

The extractor returns evidence objects such as:

```json
{
  "field": "profile.skills",
  "source_text": "Python, MATLAB, Embedded systems",
  "note": "Split the visible skills section into reviewable skill candidates."
}
```

Evidence is not an optional explanation added after extraction. It is part of the contract.

That design supports future features:

- claim-level approval,
- confidence review,
- source traceability,
- resume-version refresh,
- comparison between deterministic and AI providers,
- extraction evaluation datasets.

## Deterministic baseline

`DeterministicResumeExtractor` is the default provider.

It uses visible section headings such as:

- Education,
- Experience,
- Projects,
- Technical Skills,
- Certifications,
- Leadership and Activities.

It extracts only visible candidates and does not infer missing claims.

This baseline serves three purposes:

1. the application works without an API key,
2. the provider contract can be tested offline,
3. future AI quality can be measured against a stable baseline.

The deterministic parser is intentionally limited. Its warnings disclose that it depends on headings and may combine entries when document layout is ambiguous.

## The separate AI enable switch

Selecting an AI provider path is not enough to run AI extraction.

A future provider can declare:

```python
requires_ai_enabled = True
```

The loader then checks:

```text
RESUME_AI_ENABLED=true
```

Without that second switch, the provider is rejected before extraction.

This prevents accidental live-model requests caused by a configuration-path change alone.

The current defaults are:

```text
RESUME_AI_ENABLED=false
RESUME_EXTRACTOR=candidate_profile.services.resume_deterministic.DeterministicResumeExtractor
```

## Session-backed review draft

The draft is stored under a dedicated Django session key.

The draft includes:

- exact source metadata,
- document-reader metadata,
- extracted document text,
- provider metadata,
- structured candidates,
- evidence,
- warnings,
- draft creation time.

No candidate-evidence database model is created in this step.

That is intentional. Persistent candidate claims should not exist until the application has:

- editable human review,
- explicit approval controls,
- claim-level provenance,
- replacement and refresh rules.

## Source integrity check

When the review page opens, it verifies that:

1. the referenced `ResumeSource` still exists, and
2. its SHA-256 fingerprint still matches the draft.

If either check fails, the draft is discarded.

This prevents a stale draft from appearing to belong to a different or deleted resume version.

## Current workflow

```text
stored ResumeSource
        ↓
POST: Extract Draft
        ↓
local document reader
        ↓
ResumeExtractionRequest
        ↓
configured BaseResumeExtractor
        ↓
validated ResumeExtractionResult
        ↓
session-backed review page
        ↓
keep for review or discard
```

There is deliberately no **Apply to Profile** button yet.

## Tests that protect the AI boundary

The test suite verifies:

- blank document text cannot enter the provider,
- a provider must return `ResumeExtractionResult`,
- result payloads must be JSON safe,
- an AI provider cannot run while `RESUME_AI_ENABLED` is false,
- TXT and DOCX readers extract visible text,
- a PDF without selectable text produces a clear OCR-related error,
- extraction requires POST,
- the review draft is stored only in the session,
- `CareerProfile` fields and timestamps do not change,
- `ResumeSource` review state and timestamps do not change,
- the review page clearly states that the profile is unchanged,
- discarding removes the draft but preserves the stored source.

## Local verification

```bash
python manage.py check
python manage.py test candidate_profile
```

After starting the server, open:

```text
http://127.0.0.1:8000/resume/
```

Upload a resume, then click **Extract Review Draft**.

## Next AI implementation step

The next Stage 5 AI step should add an optional OpenAI resume provider with:

- a strict JSON schema,
- a resume-specific system prompt,
- bounded source text,
- refusal and invalid-response handling,
- deterministic fallback,
- provider attempt metadata,
- an offline evaluation set before live benchmarking.

Human approval and persistent candidate evidence should still remain separate from the provider itself.
