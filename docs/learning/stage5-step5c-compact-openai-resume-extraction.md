# Stage 5 Step 5C — Compact OpenAI Resume Extraction and Bounded Recovery

## Why this step exists

The first real-CV website test reached OpenAI but returned an `incomplete` response. The synthetic one-page resume had succeeded, while the real two-page CV contained substantially more education, experience, projects, leadership, links, and skills.

The earlier provider contract asked the model to return the same information several times:

1. Structured claims.
2. A `source_text` excerpt inside every structured entry.
3. A second top-level evidence list containing more excerpts and notes.

That duplication consumed output capacity without improving factual safety. The application already had local grounding and evidence-anchoring logic, so model-generated evidence was unnecessary.

## New architecture

The model now returns only compact claims:

```text
identity
profile
  professional_summary
  education
  experience
  projects
  skills
  certifications
  leadership
warnings
```

Each education, experience, project, certification, or leadership entry contains only:

```text
heading
subheading
dates
details
```

The model does **not** return:

- `source_text`
- a top-level evidence list
- evidence notes

After the provider responds, the application performs these steps locally:

```text
strict schema validation
→ full-document claim grounding
→ exact local excerpt selection
→ local evidence construction
→ review-only result
```

This separation makes responsibilities clearer:

- The model proposes structured claims.
- Deterministic application code verifies those claims.
- Deterministic application code creates trusted evidence.
- The user reviews the result before any future persistence step.

## Why compact schemas matter

Structured output still uses tokens. A verbose JSON schema can create a large response even for a short source document. Repeating long bullet text in multiple fields increases:

- response latency,
- cost,
- output-limit risk,
- the chance of an incomplete JSON object,
- the amount of provider-generated text that must be verified.

Compact schemas are not merely an optimization. They reduce the number of untrusted values crossing the provider boundary.

## Output limits and reasoning tokens

The Responses API `max_output_tokens` setting is an upper bound that includes visible response tokens and reasoning tokens. A reasoning model can therefore reach the limit before all visible JSON has been emitted.

The resume provider now uses:

```text
initial output allowance: 8,000
retry output allowance: 12,000
reasoning effort: low
timeout: 120 seconds
```

The defaults remain configurable through environment variables.

Official references:

- Responses API reference: https://platform.openai.com/docs/api-reference/responses
- Reasoning guide: https://platform.openai.com/docs/guides/reasoning
- Structured Outputs guide: https://platform.openai.com/docs/guides/structured-outputs

## Reading incomplete responses safely

An incomplete response is not valid extraction data. Even if `output_text` contains partial JSON, the application must not accept it.

The backend now reads:

```text
response.status
response.incomplete_details.reason
```

The provider maps reasons to a small safe vocabulary:

```text
max_output_tokens
content_filter
unknown
```

Raw provider text is not exposed on the review page.

## Bounded retry policy

Only one condition permits an application-level retry:

```text
status == incomplete
and reason == max_output_tokens
and no output-limit retry has occurred yet
```

The retry uses the same:

- model,
- input document,
- instructions,
- strict schema,
- storage setting,
- timeout.

Only the output allowance increases.

The application does **not** retry:

- content-filter incomplete responses,
- refusals,
- malformed JSON,
- grounding failures,
- authentication errors,
- permission errors,
- unsupported models,
- arbitrary unknown incomplete reasons.

After the one bounded retry, another output-limit response becomes a normal extraction failure and the disclosed fallback workflow may run.

## SDK retries versus application retries

There are two different retry layers:

1. **SDK transport retries** handle transient network-level failures.
2. **Application output-limit retry** handles one completed-but-incomplete model generation.

They solve different problems. The application retry is explicit, reason-aware, and limited to one additional generation.

## Local evidence generation

Every accepted claim is checked against the complete locally parsed resume. The application then selects a short contiguous local text window that supports the claim.

For structured entries, the selected excerpt is stored as the entry's `source_text` in the review result.

For traceability, the application builds evidence items locally for:

- identity fields,
- links,
- professional summary,
- each education entry,
- each experience entry,
- each project,
- skills,
- certifications,
- leadership.

When claims such as links or skills occur in multiple places, evidence generation may create more than one evidence item for the same field so every accepted claim remains traceable.

## Safety properties preserved

This step does not weaken the existing controls:

- Every non-empty claim must still be grounded in the supplied resume text.
- Invented skills, employers, institutions, dates, degrees, and achievements are rejected.
- Partial JSON is never accepted.
- The API key remains local and is never committed.
- `store=False` remains set on provider requests.
- AI extraction remains behind `RESUME_AI_ENABLED`.
- The deterministic fallback remains disclosed.
- The review draft does not write to `CareerProfile`.
- Match scores remain unchanged.

## Version changes

```text
schema: resume-extraction-schema-v2
structured extractor: structured-ai-resume-extractor-v4
OpenAI provider: openai-responses-resume-v4
```

Versioning matters because an evaluation report must reveal which schema and recovery behavior produced its results.

## New configuration

```dotenv
OPENAI_RESUME_EXTRACTION_TIMEOUT_SECONDS=120
OPENAI_RESUME_EXTRACTION_MAX_OUTPUT_TOKENS=8000
OPENAI_RESUME_EXTRACTION_RETRY_MAX_OUTPUT_TOKENS=12000
OPENAI_RESUME_EXTRACTION_REASONING_EFFORT=low
```

The provider still defaults to `gpt-5-mini` unless the local environment selects another permitted model.

## Test strategy

Automated tests verify:

- the provider sends the compact strict schema,
- `source_text` and top-level `evidence` are absent from model output,
- evidence is rebuilt locally,
- one `max_output_tokens` incomplete response triggers one retry,
- the retry uses the larger configured allowance,
- a second output-limit response fails safely,
- content-filter and unknown incomplete reasons are not retried,
- partial output is not accepted,
- refusals and provider errors remain sanitized,
- hallucinated claims remain rejected,
- no database writes occur,
- a long synthetic engineering resume is included in the evaluation corpus.

## Long synthetic benchmark

The repository now includes a sanitized long engineering resume with:

- two degree lines,
- five experience entries,
- eight projects,
- four leadership entries,
- technical and interpersonal skills.

It contains no real user contact information and is safe for repeatable local or live evaluation.

## What this step does not solve

This step does not repair the deterministic parser's handling of decorated PDF section headings. That is the separate Step 5D patch.

It also does not add:

- editable claim controls,
- approve/reject actions,
- permanent profile persistence,
- background job processing.

Those remain later Stage 5 responsibilities.

## Practical takeaway

A reliable AI extraction system should ask the model for the smallest useful semantic output. Evidence, provenance, validation, retries, and persistence rules should remain deterministic wherever possible.
