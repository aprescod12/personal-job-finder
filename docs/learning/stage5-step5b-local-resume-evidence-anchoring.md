# Stage 5 Step 5B — Local Résumé Evidence Anchoring

## Why this step was needed

The first end-to-end website test reached the OpenAI provider successfully, but the AI draft was rejected and the deterministic fallback was used.

The failing field was:

```text
profile.education[1].source_text
```

The synthetic résumé listed one institution followed by two degree lines:

```text
Villanova University
B.S. Electrical Engineering | 2025
M.S. Biomedical Engineering Candidate | 2027
```

The model represented the degrees as separate education entries. For the second entry, it repeated the institution inside `source_text`, even though the institution appeared only once above both degrees in the original document. The resulting excerpt was factually understandable but was not a contiguous verbatim substring of the résumé.

The application therefore rejected the AI output and safely used the deterministic fallback.

## The engineering lesson

An AI model is useful for identifying semantic structure, but it should not be the authority that creates evidence.

The safer division of responsibility is:

```text
Model identifies candidate claims
→ application validates claims against the complete document
→ application locates exact supporting text locally
→ human reviews the claim and locally anchored evidence
```

The model may suggest an excerpt, but the final evidence shown by the application must come from the locally parsed résumé text.

## Three separate validation questions

### 1. Is the output structurally valid?

The provider must return the required JSON keys and value types.

Examples:

- `education` must be a list.
- Each education entry must contain `heading`, `subheading`, `dates`, `details`, and `source_text`.
- Unsupported extra keys are rejected.

This is schema validation.

### 2. Is each claim grounded in the résumé?

Every non-empty claim is checked against the complete locally parsed résumé.

Examples:

- `Villanova University` is accepted because it appears in the résumé.
- `B.S. Electrical Engineering` is accepted.
- A narrow formatting variation such as `BS Electrical Engineering` can be accepted after normalization.
- `Ph.D. Biomedical Engineering` is rejected when it does not appear in the résumé.

This is document grounding.

### 3. What exact local text supports the claim?

Once the claim passes grounding, the application selects a supporting line or short block directly from the parsed résumé.

This is evidence anchoring.

These checks must remain separate. A malformed provider excerpt should not automatically invalidate a legitimate claim, but a legitimate-looking excerpt must never rescue an invented claim.

## New trust boundary

The provider-supplied `source_text` is now treated as a suggestion.

It is accepted unchanged only when both conditions are true:

1. It is a verbatim excerpt from the parsed résumé.
2. It supports at least one validated claim associated with that entry or evidence field.

When the excerpt contains a validated claim but is not verbatim, the application searches the local document for an exact replacement.

When the excerpt is blank, the application may also build a local excerpt from the validated claims.

When a non-empty excerpt is unrelated to every associated claim, the output is rejected rather than repaired.

## Local anchoring algorithm

The document is divided into blocks separated by blank lines.

For each block, the application evaluates short contiguous windows of up to eight lines.

Each candidate window is scored using this priority:

1. Does the window support every claim in the entry?
2. How many claims does it support?
3. How few lines does it use?
4. How concise is the excerpt?

The highest-scoring exact window becomes the trusted `source_text`.

For the two-degree example, the selected block is:

```text
Villanova University
B.S. Electrical Engineering | 2025
M.S. Biomedical Engineering Candidate | 2027
```

It is acceptable for both degree entries to reference the same local block because the institution appears once and governs both visible degree lines.

## Why not use fuzzy text as final evidence?

Fuzzy matching is useful for deciding whether a claim such as `B.S.` and `BS` refers to visible résumé text.

It is not appropriate for the final evidence excerpt.

The final excerpt must be copied from the locally parsed document so that:

- the review page shows what the résumé actually contained;
- punctuation and dates are not silently rewritten;
- provider wording cannot become application evidence;
- future persistence can retain defensible provenance.

## Security behavior that remains strict

The patch does not permit the model to add unsupported claims.

The following still fail:

- invented institutions;
- invented degrees;
- invented skills;
- invented dates;
- unsupported work experience;
- evidence associated with an empty extracted field;
- non-empty excerpts that do not mention any associated validated claim.

Local anchoring repairs evidence formatting. It does not repair hallucinated facts.

## Warning behavior

When the application replaces a provider excerpt, it adds a review warning such as:

```text
Re-anchored profile.education[1].source_text locally because the provider excerpt was not a verbatim excerpt.
```

Warnings remain visible because automatic repair should be transparent to the reviewer.

If an exact excerpt supports only part of an entry, the existing evidence-alignment warnings remain available for the missing fields.

## Tests added or updated

The regression suite now covers:

- a document-grounded heading omitted from a narrow excerpt;
- punctuation normalization in claims;
- rewritten but claim-related entry excerpts;
- two degrees under one institution;
- blank entry excerpts rebuilt from valid claims;
- rewritten field-level evidence;
- unrelated evidence rejection;
- invented institution rejection;
- invented degree rejection;
- evidence attached to an empty field;
- provider and validator warning deduplication.

The older test for an invented `Principal Engineer` excerpt still passes because that excerpt does not support any validated experience claim.

## Provider versioning

The schema remains version 1 because the JSON shape did not change.

The extraction behavior changes from:

```text
structured-ai-resume-extractor-v2
openai-responses-resume-v2
```

to:

```text
structured-ai-resume-extractor-v3
openai-responses-resume-v3
```

This allows evaluation reports and review drafts to distinguish evidence-validation behavior across runs.

## What this step does not do

This patch does not:

- save AI claims into the permanent candidate profile;
- approve claims automatically;
- eliminate human review;
- send a real résumé during tests or CI;
- add database migrations;
- change the deterministic fallback.

## Retesting sequence

After the pull request is merged:

```bash
git checkout main
git pull origin main
```

Confirm the provider version:

```bash
python3 manage.py shell -c '
from candidate_profile.services.openai_resume_extraction import OPENAI_RESUME_BACKEND_VERSION
print(OPENAI_RESUME_BACKEND_VERSION)
'
```

Expected:

```text
openai-responses-resume-v3
```

Then repeat the synthetic website upload with the OpenAI provider enabled.

The expected primary result is:

```text
Pipeline: OpenAI structured resume extractor
Mode: AI
Provider version: openai-responses-resume-v3
```

A local re-anchoring warning may appear. The deterministic fallback banner should not appear unless a different validation or provider failure occurs.

## Main takeaway

The model proposes structure and claims. The application owns evidence.

That separation makes the résumé workflow more reliable, explainable, and safe enough to support the later claim-level approval and persistence step.
