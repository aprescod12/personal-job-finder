# Stage 6 Step 1 — Job Discovery Inbox Foundation

## Why this stage exists

The application previously required a user to paste every job listing manually. That was useful for learning and remains a safe fallback, but it is not the completed product workflow.

The Job Discovery Agent introduces a controlled source of raw opportunities:

```text
approved provider
→ discovery run
→ raw opportunity
→ duplicate and broad-preference review
→ discovery inbox
→ explicit handoff
→ existing Job Processing workflow
```

Discovery does not replace processing or evaluation. It only finds and preserves source material.

---

## Agent boundary

The Job Discovery Agent owns:

- approved provider execution;
- search-query construction from manual preferences;
- raw listing capture;
- provider identifiers and timestamps;
- rediscovery detection;
- broad recall-oriented preference labels;
- inbox workflow state;
- explicit handoff to Job Processing.

It does not own:

- final title or company validation;
- structured requirements;
- listing verification;
- candidate-job scoring;
- eligibility decisions;
- application submission.

A provider title is therefore stored as `title_hint`, not as a trusted `JobPosting.title`.

---

## Models

### `DiscoveryRun`

One run records one controlled provider search.

It stores:

- provider key, label, and version;
- manual or scheduled trigger;
- pending, running, completed, or failed state;
- the exact preference query supplied to the provider;
- result, new, duplicate, and outside-preference counts;
- error text and timing.

The saved query makes later discovery behavior auditable when career preferences change.

### `RawJobOpportunity`

One opportunity stores one unprocessed provider result.

It preserves:

- discovery run;
- provider metadata;
- external listing identifier;
- source and normalized URL;
- title, company, location, industry, seniority, arrangement, and employment hints;
- complete raw listing text;
- text and role fingerprints;
- broad-preference reasons;
- duplicate evidence;
- inbox status;
- processing handoff state;
- eventual tracked job link.

Raw source text remains available even when extraction later fails.

---

## Provider contract

Providers implement one small interface:

```python
class DiscoveryProvider(Protocol):
    key: str
    label: str
    version: str

    def discover(self, query: DiscoveryQuery) -> Iterable[DiscoveredOpportunity]: ...
```

Every result must be a `DiscoveredOpportunity` with:

- external ID or source URL;
- source URL when available;
- title, company, and location hints;
- full raw listing text;
- optional structured hints;
- provider-specific metadata.

Application code validates the contract. Provider output cannot write directly to Django models.

---

## Approved-provider registry

Only provider classes listed in `APPROVED_DISCOVERY_PROVIDERS` may run.

This prevents an arbitrary import path, unrestricted scraper, or unreviewed integration from being executed through the UI.

The first provider is:

```text
fixture
Local fixture provider
fixture-discovery-v1
```

It is deterministic, offline, and uses fictional listings under `example.com`. It proves the workflow without network access, API cost, scraping policy questions, or changing external data.

---

## Search preferences

The discovery query captures manually controlled search preferences:

- target roles;
- target industries;
- preferred locations;
- work arrangement;
- employment type;
- experience level.

Résumé evidence is intentionally not converted into hidden search preferences. Candidate evidence answers what the user can support; manual preferences answer what the user wants the system to search for.

---

## Broad relevance is not a match score

Discovery applies a conservative recall-oriented label:

- broad preference match;
- outside broad preferences;
- unknown.

The label checks visible title, industry, location, arrangement, and employment hints. It does not inspect the full candidate evidence or produce `/100` fit.

A result outside broad preferences is retained for review instead of silently deleted. This protects recall while the provider and preference vocabulary are still developing.

---

## Duplicate layers

Discovery checks multiple identifiers before processing.

### Previously discovered opportunities

- same provider and external ID;
- same normalized URL;
- same normalized raw listing text.

These are blocking rediscovery signals.

### Existing tracked jobs

The discovery service reuses the established intake-history duplicate logic:

- exact normalized job URL;
- exact historical listing text;
- same title, company, and location warning.

Exact URL and text matches are blocking. A same-role match is a warning because employers may post several openings with similar titles.

No duplicate is deleted or merged automatically.

---

## Duplicate override

A blocking duplicate cannot be sent to processing immediately.

The user must select **Keep Despite Duplicate**. That action:

- records `duplicate_override=True`;
- changes the opportunity to `Ready for processing`;
- preserves every duplicate reason;
- still requires the normal Job Processing review.

The override does not create a job and does not suppress the earlier record.

---

## Processing handoff

Selecting **Send to Job Processing** calls the existing extraction coordinator with:

- raw listing text;
- provider source URL;
- provider label.

The resulting extraction draft is stored in the same session contract used by manual intake, with two additional identifiers:

```text
discovery_opportunity_id
discovery_run_id
```

At this point:

- the opportunity becomes `Sent to processing`;
- no `JobPosting` exists;
- no match score is calculated;
- the user must review the existing Stage 4 form.

This avoids maintaining two different processing pipelines.

---

## Reversible handoff

A session draft is temporary.

When the user discards it, or replaces it with another intake draft, the opportunity returns to the discovery inbox:

```text
Sent to processing
→ draft discarded or replaced
→ New or Ready
```

This prevents opportunities from becoming permanently stuck because a browser review was abandoned.

---

## Successful completion

Only the existing reviewed `JobIntakeReviewForm.save()` creates:

- `JobPosting`;
- `JobRequirement`;
- `JobExtractionRun` provenance.

After those records are created in the same transaction, the source opportunity changes to `Processed` and records `processed_job`.

If reviewed job creation fails, the discovery link is not advanced independently.

---

## Status lifecycle

```text
New
├─ Ignore → Ignored → Restore → Ready
├─ Send → Sent to processing
│  ├─ Discard/replace draft → New
│  └─ Approve reviewed intake → Processed
└─ Extraction failure → Processing failed → Retry

Duplicate
├─ Ignore → Ignored
└─ Keep despite duplicate → Ready → normal processing
```

The model also supports scheduled discovery runs later, but this step creates only manual runs.

---

## Why discovery does not create scores

Discovery is optimized for finding possibilities. Evaluation is optimized for careful fit analysis.

Combining them would create several problems:

- provider snippets could be treated as complete job descriptions;
- incomplete requirements could produce misleading scores;
- duplicate and verification boundaries could be skipped;
- provider-specific behavior could leak into the matcher;
- discovery could silently suppress useful adjacent roles.

The final score is therefore available only after processing creates validated job and requirement records.

---

## Tests

The regression suite verifies that:

- fixture discovery records the exact preference query;
- provider version and raw source text are preserved;
- no tracked job is created by discovery;
- repeated provider IDs become blocking duplicates;
- tracked-job URLs are detected;
- the inbox exposes the untrusted-source boundary;
- discovery runs require POST;
- send-to-processing creates only a session draft;
- duplicate processing requires an explicit override;
- ignoring and restoring are explicit POST actions;
- discarding the intake draft returns the opportunity to the inbox;
- human-approved intake creates the job and links the discovery source.

---

## Manual test

After merging and migrating:

1. Open **Discovery**.
2. Run **Local fixture provider**.
3. Confirm four fictional opportunities appear.
4. Open a result and inspect provider metadata, raw text, broad relevance, and duplicate evidence.
5. Send one new result to Job Processing.
6. Confirm the familiar extraction review page appears and no job exists yet.
7. Discard once and confirm the result returns to the inbox.
8. Send it again, review the extracted fields, and save the job.
9. Confirm the opportunity says `Processed` and links to the tracked job.
10. Run fixture discovery again.
11. Confirm the second set is marked duplicate.
12. Retain one duplicate explicitly and confirm it becomes ready rather than creating a job.

---

## Next step

After this offline foundation is stable, Stage 6 Step 2 should add the first real approved provider.

The real provider must reuse the same contract and boundaries:

```text
real source
→ provider result
→ raw opportunity
→ duplicate control
→ inbox decision
→ Job Processing
```

No live integration should bypass the inbox or create trusted jobs directly.
