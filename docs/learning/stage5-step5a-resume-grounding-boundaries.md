# Stage 5 Step 5A — Resume Grounding Boundaries

## Why this patch exists

The first live synthetic OpenAI résumé test completed successfully at the provider level, but the application rejected the returned education entry:

```text
AI field 'profile.education[0].heading' is not grounded in the supplied resume text.
```

The source résumé did contain the heading. The failure happened because the validator checked the heading only against the model-selected `source_text` excerpt rather than against the complete résumé.

That mixed two different questions:

1. Is the extracted claim present somewhere in the résumé?
2. Does the selected evidence excerpt clearly support that claim?

Those questions need different validation behavior.

## Three layers of correctness

### 1. Schema validity

Structured output verifies that the model returned the expected JSON shape:

- required keys exist,
- lists and strings use the correct types,
- unsupported keys are rejected.

Schema validity does not prove that a claim is true.

### 2. Document grounding

Every non-empty extracted claim must be supported by the complete parsed résumé text.

Examples include:

- institution names,
- degree names,
- job titles,
- employers,
- dates,
- project names,
- skills,
- bullet details.

An invented institution such as `Stanford University` is still rejected when it does not appear in the source résumé.

### 3. Evidence-to-claim alignment

Each entry also has a short `source_text` excerpt. Ideally that excerpt contains every structured field associated with the entry.

However, a model may return a valid excerpt containing the degree lines while omitting the institution line. That is an evidence-quality problem, not necessarily a hallucination.

The new behavior keeps the grounded claim but adds a review warning such as:

```text
Review evidence for profile.education[0].heading: the claim is grounded in the full resume, but the selected source excerpt does not contain it.
```

This preserves useful extraction output while keeping the weakness visible to the reviewer.

## Strict versus tolerant normalization

### Claims

Claim grounding allows minor punctuation and formatting differences.

For example:

```text
B.S. Electrical Engineering
BS Electrical Engineering
```

These are treated as the same document-grounded phrase after compact normalization.

The normalization is intentionally narrow. It removes formatting differences but does not perform semantic rewriting or infer synonyms.

### Source excerpts

`source_text` remains stricter.

A source excerpt must still be present in the résumé with its wording and punctuation preserved, apart from harmless case and whitespace normalization.

Therefore:

```text
B.S. Electrical Engineering | 2025
```

is a valid source excerpt when that text appears in the résumé, while:

```text
BS Electrical Engineering | 2025
```

is not accepted as a verbatim excerpt if the résumé contains the punctuated version.

This distinction prevents the model from rewriting evidence while still allowing small formatting differences in structured claim fields.

## Updated validation flow

For each education, experience, project, certification, or leadership entry:

1. Confirm the entry object has exactly the expected keys.
2. Confirm `source_text` is a non-empty excerpt from the complete résumé.
3. Validate heading, subheading, dates, and details against the complete résumé.
4. Compare each validated claim against the selected excerpt.
5. Add a review warning when the excerpt does not contain a grounded claim.
6. Return the review-only extraction draft without writing to the database.

## What remains rejected

This patch does not weaken the core safety boundary.

The validator still rejects:

- invented headings,
- invented skills,
- invented dates,
- invented details,
- source excerpts absent from the résumé,
- malformed structured payloads,
- extra unsupported fields.

## Automated regression tests

The new tests cover:

- a valid institution heading omitted from the entry excerpt,
- punctuation normalization for a grounded degree,
- rejection of an invented institution,
- rejection of an invented source excerpt,
- rejection of a rewritten non-verbatim source excerpt,
- deduplication and combination of provider and validator warnings.

No test makes a live OpenAI request.

## Learning takeaway

A robust AI workflow should not collapse every validation failure into “hallucination.”

The system must distinguish:

- invalid output structure,
- claims absent from the source document,
- evidence excerpts that are incomplete or poorly selected.

This separation improves reliability without hiding uncertainty or discarding valid extracted information.

## Retesting sequence

After this patch passes CI:

1. Merge the grounding fix.
2. Pull `main` locally.
3. Repeat the one-case synthetic OpenAI test.
4. Inspect any generated evidence-alignment warnings.
5. Run the complete three-case provider comparison only after the one-case extraction completes.
