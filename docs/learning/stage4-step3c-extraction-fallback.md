# Stage 4, Step 3C — Controlled Extraction Fallback

## Purpose of this chapter

Step 3B connected the Job Processing Agent to a real model provider. That created a new failure boundary: a live provider can time out, reject a request, lose network connectivity, refuse output, return malformed data, or be configured incorrectly.

Step 3C makes the intake workflow dependable when those failures occur.

The goal is not to hide failure. The goal is to degrade safely and visibly:

```text
primary extraction succeeds
→ show the primary draft

primary extraction fails
→ try the deterministic fallback
→ clearly disclose that fallback was used

primary and fallback both fail
→ preserve the original listing
→ open a manual-review draft

all paths
→ save nothing until human approval
```

This is a core agent-development lesson: reliability comes from orchestration around a model, not from assuming the model will always respond correctly.

---

## 1. What changed in Step 3C

The intake view previously called one configured extractor directly:

```text
view
→ configured extractor
→ success or visible error
```

The view now calls an extraction coordinator:

```text
view
→ extraction coordinator
   → primary extractor
   → deterministic fallback when needed
   → manual-review draft when both fail
→ review page
```

The coordinator is implemented in:

```text
tracker/services/job_extraction_coordinator.py
```

The provider contract remains in:

```text
tracker/services/job_extraction.py
```

The OpenAI-specific adapter remains in:

```text
tracker/services/openai_job_extraction.py
```

This separation is intentional.

---

## 2. Extraction versus orchestration

### Extraction

An extractor answers one question:

> Can this provider turn the supplied listing into a `JobExtractionResult`?

Examples:

- `DeterministicJobExtractor`
- `OpenAIJobExtractor`
- Test doubles used in automated tests

An extractor should not decide:

- whether another provider should be tried
- whether a failure is visible to the user
- whether a manual draft should be created
- whether the result should be saved
- whether the candidate is eligible

### Orchestration

The coordinator answers a different question:

> Given the configured providers and their outcomes, what safe review draft should the application present?

Its responsibilities are:

1. Build one trusted `JobExtractionRequest`.
2. Attempt the primary extractor.
3. Record the attempt and elapsed time.
4. Classify a safe failure.
5. Decide whether fallback is allowed.
6. Attempt the fallback at most once.
7. Create a manual-review draft when necessary.
8. Attach visible orchestration metadata.
9. Return a session-safe dictionary.
10. Never write to the database.

This pattern will later be useful to the broader Coordinator Agent.

---

## 3. The structured failure contract

Before Step 3C, `JobExtractionError` carried only a message.

It now carries:

```python
JobExtractionError(
    message,
    category="timeout",
    retryable=True,
)
```

The message is safe for a user-facing review page. The category is stable for program logic. The retryability flag indicates whether the problem may be temporary.

### Current failure categories

| Category | Meaning | Usually retryable? |
|---|---|---:|
| `configuration` | Missing key, invalid provider path, missing model, disabled AI | No |
| `authentication` | Provider rejected the credential | No |
| `permission` | Project or key cannot use the model or endpoint | No |
| `usage_limit` | Rate limit, quota, or usage restriction | Sometimes |
| `timeout` | Provider did not finish in time | Yes |
| `connection` | Network or provider connection failed | Yes |
| `invalid_response` | Wrong type, malformed JSON, schema failure, incomplete output | Usually no |
| `refusal` | Model declined to produce the requested structure | No |
| `provider_failure` | Sanitized unknown provider failure | Unknown |
| `all_extractors_failed` | Coordinator status when no extractor produced a draft | No |

### Why not parse error sentences?

Fragile code might do this:

```python
if "timed out" in str(exc):
    ...
```

That breaks whenever wording changes.

A stable category allows this instead:

```python
if exc.category == ERROR_TIMEOUT:
    ...
```

The program uses machine-readable metadata while the user sees understandable language.

---

## 4. Safe provider boundaries

A provider adapter is expected to translate provider-specific exceptions into `JobExtractionError`.

The OpenAI backend now maps provider failures such as:

```text
AuthenticationError
PermissionDeniedError
RateLimitError
APITimeoutError
APIConnectionError
BadRequestError
NotFoundError
```

into the shared failure categories.

The coordinator also protects itself against a provider that accidentally raises an arbitrary exception:

```python
except Exception as exc:
    failure = _safe_failure(exc)
```

The raw exception is not copied into the session or review page. It becomes:

```text
The extraction provider failed unexpectedly.
```

This prevents private response details, internal stack information, or secret-adjacent text from leaking through the UI.

The original exception remains available in a Python exception chain only where the adapter explicitly raises from it. It is not serialized into the draft.

---

## 5. The attempt record

Each provider attempt becomes an `ExtractionAttempt`.

It records:

```text
provider path
provider key
provider label
provider version
extraction mode
success or failure
elapsed milliseconds
failure category
safe failure message
retryability
```

A successful primary attempt may look conceptually like:

```json
{
  "success": true,
  "elapsed_ms": 1842,
  "provider": {
    "key": "openai_structured",
    "mode": "ai"
  }
}
```

A failed primary attempt may look like:

```json
{
  "success": false,
  "elapsed_ms": 30004,
  "error_category": "timeout",
  "error_message": "The OpenAI extraction request timed out.",
  "retryable": true
}
```

These records are currently stored only inside the session draft. They are not yet database provenance records. Persistent extraction history is a later stage.

---

## 6. Timing and observability

The coordinator measures each attempt with `perf_counter()`.

`perf_counter()` is appropriate for duration measurement because it is monotonic. It is not used as a calendar timestamp.

The helper converts elapsed time into milliseconds:

```python
round((clock() - started_at) * 1000)
```

The result contains:

- elapsed time for every attempt
- total elapsed time for the coordinated operation

This begins addressing Evaluation Case 001 item `JP-007`: record extraction latency.

Observability does not mean storing secrets or raw provider payloads. Useful operational metadata can be collected without retaining sensitive request details.

---

## 7. Primary-success path

When the primary extractor succeeds:

1. The coordinator validates that the provider returned `JobExtractionResult`.
2. The result is converted into a JSON-serializable dictionary.
3. One successful attempt is recorded.
4. `fallback_used` is `false`.
5. `manual_review_required` is `false`.
6. The provider's original evidence and warnings remain intact.
7. The review page shows the provider and total duration.

No fallback is called after primary success.

This matters for cost and consistency. A fallback should not run merely to compare results during normal intake.

---

## 8. Fallback-success path

When the primary fails and fallback is enabled:

1. The safe primary failure is recorded.
2. The deterministic provider is attempted once.
3. Its output is validated using the same provider contract.
4. A prominent fallback warning is inserted.
5. The primary failure category and message are preserved.
6. The result provider is the deterministic extractor.
7. `fallback_used` is `true`.
8. The review page displays a **FALLBACK USED** banner.

The fallback is not silent.

Silent fallback would be dangerous because the deterministic parser is materially less capable than the AI extractor on Evaluation Case 001. A user who thinks a fallback result was AI-assisted may place too much trust in empty or misclassified fields.

The warning explicitly says that careful human review is required.

---

## 9. Manual-review path

The coordinator creates a manual-review draft when:

- both primary and fallback fail
- fallback is disabled
- fallback would repeat the same failed provider

The manual draft preserves application-controlled information:

```text
original listing text
source URL
source label
safe field defaults
failure warnings
attempt metadata
```

It does not fabricate extracted fields.

The provider metadata becomes:

```text
key: manual_review
label: Manual review draft
version: manual-review-v1
mode: manual
```

The review page displays a **MANUAL REVIEW REQUIRED** banner.

This is graceful degradation. The user can still work from the source listing even when no extractor is available.

---

## 10. Why the original listing is always preserved

The raw listing is the highest-trust evidence available to the review workflow.

It is preserved in two places during the temporary intake flow:

1. `draft["raw_text"]`
2. the review draft's `description` field

The review page also keeps the expandable original-listing panel.

This ensures that extraction failure never destroys the source information.

The listing is not automatically saved as a tracked job. It remains in the session until the user approves or discards it.

---

## 11. Configuration

The new settings are:

```env
JOB_INTAKE_FALLBACK_ENABLED=true
JOB_INTAKE_FALLBACK_EXTRACTOR=tracker.services.job_intake.DeterministicJobExtractor
```

### `JOB_INTAKE_FALLBACK_ENABLED`

Controls whether the coordinator may attempt the configured fallback after primary failure.

Disabling it does not cause data loss. The coordinator creates a manual-review draft instead.

### `JOB_INTAKE_FALLBACK_EXTRACTOR`

Points to the fallback provider class.

The default remains local and deterministic. A second paid model is not used as fallback.

### Why avoid an AI-to-AI fallback now?

An AI-to-AI fallback could:

- duplicate cost
- duplicate provider outages
- introduce another secret
- make behavior harder to understand
- complicate evaluation before the first provider is calibrated

A deterministic fallback is limited, but predictable and free.

---

## 12. Review-page behavior

The review page now shows:

- the provider that produced the displayed draft
- provider version and extraction mode
- total extraction duration
- a fallback banner when fallback was used
- a manual-review banner when both providers failed
- expandable attempt details
- elapsed time per attempt
- failure category and safe message
- whether the failure may be temporary

It continues to show:

- extracted evidence
- extractor warnings
- every editable field
- the original listing
- the approval button
- the discard button

The database boundary is unchanged:

```text
review page displayed
≠ job created
```

A job is created only by the valid review-form POST.

---

## 13. Test doubles

The Step 3C tests use small fake extractors:

- `SuccessfulAIExtractor`
- `TimeoutExtractor`
- `AuthenticationFailureExtractor`
- `InvalidResultExtractor`
- `UnexpectedFailureExtractor`
- `FailingFallbackExtractor`
- `MustNotRunExtractor`

These are test doubles. They let the test suite force exact conditions without making network calls.

For example, the timeout double raises:

```python
raise JobExtractionError(
    "The AI extraction request timed out.",
    category=ERROR_TIMEOUT,
    retryable=True,
)
```

No test waits thirty seconds. No test spends API credits. No test depends on provider availability.

---

## 14. What the tests prove

### Primary success

- only one attempt occurs
- fallback is not called
- the primary provider produces the draft
- no database record is created

### Timeout fallback

- timeout category is preserved
- retryability is preserved
- deterministic fallback runs
- fallback is disclosed
- source metadata survives
- no database record is created

### Other known failures

- authentication failure can fall back
- invalid provider return type can fall back
- categories remain machine-readable

### Unexpected failure

- arbitrary internal error text is sanitized
- private exception detail does not enter the payload
- fallback still works

### Both providers fail

- a manual-review draft is returned
- the original listing is preserved
- source URL and source label are preserved
- both attempts are recorded
- no `JobPosting` or `JobRequirement` is created

### Fallback disabled

- no fallback attempt occurs
- the system still creates a manual-review draft
- the user is told fallback was disabled

### View integration

- fallback redirects to the normal review page
- the fallback banner is visible
- the timeout category is visible
- the displayed provider is deterministic
- both failures display the manual-review banner
- nothing is saved before approval

---

## 15. What Step 3C does not do

Step 3C does not:

- retry providers beyond the SDK's existing policy
- automatically resubmit a failed listing later
- save extraction attempts to the database
- compare primary and fallback outputs when both could succeed
- change the extraction prompt
- normalize industry labels
- deduplicate responsibilities
- alter eligibility classification
- tune or train a model
- submit a job application

Those boundaries keep the change testable and understandable.

---

## 16. Relationship to the seven-agent architecture

The Job Processing Agent owns extraction and structured job creation.

Step 3C adds a small orchestration layer inside that logical agent. It does not add an eighth agent.

The final Coordinator Agent will eventually sequence larger workflows such as:

```text
Discovery
→ Processing
→ Evaluation
→ Project relevance
→ Presentation and tracking
```

The Step 3C coordinator is narrower:

```text
primary extraction
→ fallback extraction
→ manual review
```

This is a reusable pattern, not a change to the documented seven-agent architecture.

---

## 17. Reading order

Read the implementation in this order:

1. `JobExtractionError` in `tracker/services/job_extraction.py`
2. `execute_job_extractor()` in the same file
3. `OpenAIResponsesBackend._provider_error()`
4. `ExtractionAttempt`
5. `_attempt_extraction()`
6. `_manual_review_payload()`
7. `_orchestration_payload()`
8. `extract_job_with_fallback()`
9. `job_intake_start()`
10. `job_intake_review.html`
11. `tracker/test_job_extraction_fallback.py`

This order moves from contracts to orchestration to presentation to verification.

---

## 18. Exercises

### Exercise 1 — Trace primary success

Starting at `job_intake_start()`, write down every function called before the browser reaches the review page when AI succeeds.

Do not copy the answer from this document. Use the code.

### Exercise 2 — Trace timeout fallback

Draw the call flow for:

```text
OpenAI timeout
→ deterministic fallback success
```

Mark where the timeout becomes a category and where the warning is added.

### Exercise 3 — Add a failure category

Imagine the provider reports a temporary server outage.

Decide whether to:

- reuse `connection`
- reuse `provider_failure`
- add `service_unavailable`

Write a short justification before changing code.

### Exercise 4 — Write a new test double

Create a fake extractor that returns a `JobExtractionResult` containing a non-serializable value.

Predict which layer should reject it.

### Exercise 5 — Explain silent-fallback risk

Using Evaluation Case 001, explain why silently substituting the deterministic parser could produce a misleading match score.

### Exercise 6 — Inspect attempt metadata

Run one controlled local AI test, then open **VIEW EXTRACTION ATTEMPTS AND TIMING**.

Record:

- primary duration
- total duration
- provider version
- success status

Do not record the API key or raw request headers.

### Exercise 7 — Force local fallback

Temporarily use an invalid API key or a deliberately tiny timeout in a controlled local environment.

Confirm that:

- the fallback banner appears
- the deterministic provider is shown
- the failure category is visible
- no job is automatically created

Restore the valid local configuration afterward.

### Exercise 8 — Explain manual degradation

Describe why returning an empty manual-review form is safer than returning an HTTP 500 page or silently discarding the listing.

---

## 19. Self-check questions

1. What is the difference between an extractor and the coordinator?
2. Why does `JobExtractionError` have both a message and a category?
3. Why is retryability separate from the category?
4. Why does the coordinator sanitize arbitrary exceptions?
5. When is deterministic fallback attempted?
6. When is fallback skipped?
7. Why must fallback be visible?
8. What information is preserved when both extractors fail?
9. Where is latency measured?
10. Why is `perf_counter()` preferable to a wall-clock timestamp for duration?
11. Does a review draft create a database record?
12. Why do CI tests use fake extractors?
13. Does Step 3C modify the seven-agent architecture?
14. Does Step 3C train a model?
15. What should happen after Step 3C is validated?

---

## 20. Answer guide

1. An extractor produces one provider result; the coordinator decides between primary, fallback, and manual review.
2. The message is for people; the category is stable program data.
3. Two failures in the same category may differ in whether a later retry is useful.
4. Raw exceptions may contain internal or sensitive information and are not a stable interface.
5. After primary failure, when fallback is enabled and is not the same failed provider.
6. When disabled or when it would repeat the same provider.
7. The fallback may have materially different quality and must not be mistaken for the primary result.
8. Original listing, source URL, source label, safe warnings, attempt metadata, and default form fields.
9. Around each attempt and around the full coordinated operation.
10. It is monotonic and designed for measuring elapsed time.
11. No. Only approval of the valid review form creates records.
12. To force failures quickly, deterministically, without network use or cost.
13. No. It is an internal workflow component of the Job Processing Agent.
14. No. It adds application orchestration and tests.
15. Validate fallback locally, then build the Step 3D multi-listing evaluation set before prompt tuning.

---

## 21. Next step after validation

After Step 3C passes review and local testing, Step 3D should create a diverse evaluation set.

The sequence remains:

```text
reliable provider boundary
→ controlled fallback
→ diverse evaluation cases
→ identify repeated errors
→ refine prompt, schema, or normalization
→ retest every saved case
```

One successful listing proves that the pipeline can work. A diverse evaluation set is needed before changing extraction behavior.
