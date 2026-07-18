# Stage 4 Step 3B — Connecting the OpenAI Extraction Backend

## Goal

Step 3A defined the schema, prompt, validator, and AI backend interface without making a model call. Step 3B connects one real provider to that boundary.

The completed path is:

```text
Pasted listing
→ JobExtractionRequest
→ StructuredAIJobExtractor
→ OpenAIResponsesBackend
→ OpenAI Responses API
→ JSON parsing
→ Step 3A validation
→ reviewable session draft
→ human approval
→ database
```

The provider is one replaceable layer. It does not control Django models, match scoring, or whether a job is saved.

## Files added or changed

```text
requirements.txt
.gitignore
.env.example
config/settings.py
tracker/services/openai_job_extraction.py
tracker/test_openai_job_extraction_backend.py
docs/learning/stage4-step3b-openai-backend.md
```

There is no migration.

## Dependencies

The project adds:

```text
openai>=2.38.0,<3
python-dotenv>=1.0,<2
```

`openai` is the official Python SDK. `python-dotenv` loads local development settings from `.env`.

The upper version bounds reduce the chance that a future major release silently breaks the integration.

## Environment variables

Secrets and environment-specific settings belong outside source code.

The repository commits `.env.example`, but `.gitignore` excludes the real `.env` file.

Important values are:

```text
DJANGO_SECRET_KEY
JOB_INTAKE_AI_ENABLED
JOB_INTAKE_EXTRACTOR
OPENAI_API_KEY
OPENAI_JOB_EXTRACTION_MODEL
OPENAI_JOB_EXTRACTION_TIMEOUT_SECONDS
OPENAI_JOB_EXTRACTION_MAX_OUTPUT_TOKENS
```

The real API key must never be committed, pasted into tests, or shown in screenshots.

## Why there are two activation controls

A live AI request requires both:

```text
JOB_INTAKE_AI_ENABLED=true
```

and:

```text
JOB_INTAKE_EXTRACTOR=tracker.services.openai_job_extraction.OpenAIJobExtractor
```

Changing only the provider path fails because AI remains disabled. Changing only the enable flag leaves the deterministic provider selected.

This reduces accidental requests during testing and ordinary development.

## Settings helpers

Environment variables arrive as strings.

`_env_bool()` converts values such as `true`, `yes`, `on`, and `1` into Python `True`.

`_env_positive_int()` converts timeout and output limits into positive integers and uses a safe default for missing or invalid values.

The API key is intentionally not copied into Django settings. The official SDK reads it from the process environment only when the real client is created.

## The provider boundary

`OpenAIResponsesBackend` implements the Step 3A backend method:

```python
generate_structured(
    schema_name=...,
    schema=...,
    instructions=...,
    input_text=...,
)
```

It is responsible for:

1. creating the provider client
2. sending one structured request
3. reading the response
4. parsing JSON
5. translating provider errors
6. returning a Python mapping

It is not responsible for:

- saving jobs
- updating requirements
- calculating a match
- deciding whether to apply
- bypassing human review

## Lazy client creation

The OpenAI client is created only when `_get_client()` is called.

This means:

- Django can start without an API key
- the deterministic parser still works
- tests can inject a fake client
- unrelated pages do not initialize the provider
- missing configuration fails at the correct boundary

This is also an example of dependency injection. Tests provide a fake client instead of using the network.

## The Responses API request

The backend sends one call through:

```python
client.responses.create(...)
```

The main arguments are:

### `model`

Read from `OPENAI_JOB_EXTRACTION_MODEL`. The current default is `gpt-5-mini`, but model selection remains configurable.

### `instructions`

The Step 3A extraction rules. They tell the model to use only listing facts, separate required and preferred qualifications, preserve uncertainty, and treat listing text as untrusted data.

### `input`

The delimited source metadata and original listing created by `build_ai_extraction_input()`.

### `text.format`

```python
{
    "type": "json_schema",
    "name": schema_name,
    "schema": schema,
    "strict": True,
}
```

This requests strict structured output rather than ordinary prose or loose JSON.

### `max_output_tokens`

Places an upper bound on generated output and helps control cost and unexpected verbosity.

### `timeout`

Prevents the Django request from waiting indefinitely.

### `store=False`

Requests that the response not be stored by the provider for this API operation where supported. It does not replace reviewing the provider's current data-control documentation.

## JSON mode versus strict schema output

Loose JSON mode may produce valid JSON with the wrong field names or structure.

Strict schema output constrains the expected root keys, nested keys, types, enums, arrays, and nullable values.

Even strict output is validated again locally. The architecture uses two layers:

```text
provider schema enforcement
→ local Python validation
```

Local validation remains necessary because it also enforces application-specific relationships, such as:

- a confirmed deadline must include a date
- a date cannot exist when deadline status is not confirmed
- maximum experience cannot be below minimum experience

## Reading the response

The SDK exposes generated text through:

```python
response.output_text
```

The backend converts it with:

```python
payload = json.loads(output_text)
```

The result must be a top-level mapping. Arrays, strings, and other valid JSON roots are rejected.

After that, Step 3A validates every field and converts list values into the newline-separated text used by the current Django models.

## Status and refusal handling

The synchronous workflow expects status `completed`.

Statuses such as `failed` or `incomplete` are rejected even when some output text exists. Partial output must not be treated as a complete extraction.

A provider refusal is also rejected. The raw refusal text is not copied into the user-facing error.

## Error translation

Provider exceptions are translated into controlled `JobExtractionError` messages.

Handled categories include:

- authentication
- permission
- rate limits
- timeout
- connection failure
- invalid request
- unavailable model
- unknown provider failure

Raw exception messages are hidden because they may contain request details, provider internals, or response-body text.

The original exception remains attached as the Python cause for debugging.

## `OpenAIJobExtractor`

`OpenAIJobExtractor` extends `StructuredAIJobExtractor`.

It supplies provider metadata and creates `OpenAIResponsesBackend` only after the AI switch is enabled.

The inherited Step 3A flow still performs:

1. input construction
2. backend call
3. strict local validation
4. normalization
5. `JobExtractionResult` creation

The database boundary remains unchanged:

```text
successful API request ≠ saved job
```

Only the existing review form can save the approved draft.

## Deterministic tests

The test suite does not call the live API.

A fake client records the arguments passed to `responses.create()` and returns controlled responses.

The tests cover:

- exact strict-schema request shape
- model, timeout, token limit, and `store=False`
- valid JSON parsing
- missing local key
- malformed JSON
- wrong top-level JSON type
- provider refusal
- incomplete response
- sanitized authentication failure
- disabled AI switch
- full extractor output with zero database writes

This is how nondeterministic external systems should normally be tested: isolate the provider and make application behavior deterministic.

## Local setup after merge

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Keep the deterministic provider active while running checks:

```bash
python manage.py check
python manage.py test
```

Then add the real provider credential only to `.env`.

## Controlled activation

In the local `.env` file:

```text
JOB_INTAKE_AI_ENABLED=true
JOB_INTAKE_EXTRACTOR=tracker.services.openai_job_extraction.OpenAIJobExtractor
```

Keep the model and limits explicit, restart Django, and use one public job listing for the first live test.

Do not approve the draft until each field has been checked against the original listing.

## What to inspect during the first live request

Review:

- exact title and company
- required versus preferred skills
- degree requirements
- experience range
- authorization language
- hard blockers
- deadline handling
- evidence quotes
- unknown fields
- warnings

Record mistakes. Those examples become the evaluation set in Step 3D.

## Cost and privacy controls

Current controls include:

- AI disabled by default
- deterministic provider retained
- one request per explicit intake action
- configurable model
- token limit
- timeout
- no live calls in tests
- no automatic background processing
- no automatic database write
- `store=False`

Use public listings during early testing and monitor usage in the provider dashboard.

## What Step 3B does not add

It does not yet provide:

- deterministic fallback after AI failure
- side-by-side provider comparison
- extraction-run history
- token or cost reporting
- an evaluation dataset
- duplicate detection
- prompt-quality metrics
- model training

These are later steps.

## Step 3C preview

The next workflow will be:

```text
attempt AI extraction
→ success: review AI draft
→ failure: run deterministic extractor
→ review fallback draft with an explicit warning
```

The fallback must preserve provenance and must not silently mix fields from two providers.

## Practice exercises

1. Add a fake `APITimeoutError` test and assert that the displayed message says the request timed out.
2. Add a fake `RateLimitError` test.
3. Use `override_settings` to confirm that a new backend reads a different model name.
4. Add a response with status `failed` and confirm it is rejected.
5. Put a fake secret-like value in a provider exception and confirm the displayed error does not contain it.
6. Explain why `store=False` is useful but not a complete privacy policy.
7. Trace which layer converts skill arrays into newline-separated strings.
8. Explain why a valid API response still cannot create a job.

## Self-check

1. Why is `.env.example` committed while `.env` is ignored?
2. Why are two activation controls used?
3. Why is the client created lazily?
4. What does dependency injection make possible in tests?
5. Why is strict schema output better than loose JSON mode here?
6. Why does local validation still run?
7. Why are incomplete responses rejected?
8. Where is the API key read?
9. Which layer saves a job?
10. Why is this agent development but not model training?

## Answers

1. The example documents names and safe defaults; the real file contains private values.
2. They reduce accidental activation and spending.
3. The app can start and use deterministic features without provider configuration.
4. Tests can inspect requests and simulate errors without network access.
5. It constrains the exact output contract.
6. It enforces application semantics and protects against integration failures.
7. Partial structured data must not enter the review workflow as complete.
8. The SDK reads it from the process environment when the real client is created.
9. Only the existing human-reviewed form save path.
10. The project is integrating and controlling a model, not changing model weights.

## Official references

- OpenAI Python SDK: https://github.com/openai/openai-python
- Responses API: https://platform.openai.com/docs/api-reference/responses
- Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- Models: https://platform.openai.com/docs/models
