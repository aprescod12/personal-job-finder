# Stage 6 Step 2A — Greenhouse Live Discovery

## Why this step exists

Stage 6 Step 1 proved the discovery workflow with a deterministic local provider:

```text
provider result
→ raw opportunity
→ duplicate control
→ discovery inbox
→ Job Processing review
```

That foundation intentionally avoided network access. Step 2A adds the first real source without weakening the same trust and human-review boundaries.

Greenhouse is used first because its public Job Board API exposes published jobs through read-only GET requests. The provider calls only:

```text
GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
```

The application contains no Greenhouse application-submission request.

---

## Provider selection versus unrestricted search

A live provider is not permission to search every possible employer.

The Greenhouse provider reads only a curated configuration:

```json
[
  {
    "key": "approved-employer",
    "label": "Approved Employer",
    "board_token": "approved-employer",
    "industry_hint": "Medical devices",
    "enabled": true
  }
]
```

Each record is a deliberate product decision:

- `key` is the stable internal employer-source key;
- `label` is the employer name shown in the application;
- `board_token` identifies the public Greenhouse board;
- `industry_hint` is an optional user-curated broad-discovery hint;
- `enabled` allows a source to be disabled without deleting its history.

The provider does not discover board tokens, crawl employer pages, or accept a board token from an untrusted request parameter.

---

## Two independent switches

A provider being registered is not enough to permit network access.

Live requests require both:

1. an enabled board in `GREENHOUSE_DISCOVERY_BOARDS`; and
2. `JOB_DISCOVERY_LIVE_ENABLED=true`.

The default is:

```text
JOB_DISCOVERY_LIVE_ENABLED=false
GREENHOUSE_DISCOVERY_BOARDS=[]
```

Selecting Greenhouse while either requirement is missing creates a safely failed discovery run. The fixture provider remains available.

---

## Public data does not mean trusted data

The Greenhouse response supplies source material, not verified job facts.

The provider may populate hints such as:

- job title;
- employer label from the curated registry;
- location;
- department and office names;
- source URL;
- updated timestamp;
- complete description text.

Those values remain inside `RawJobOpportunity`. They do not become trusted `JobPosting` or `JobRequirement` values until the existing Job Processing extraction and human-review flow is completed.

The Discovery Agent still does not:

- assign the final match score;
- determine eligibility;
- verify that the listing is open beyond the provider observation;
- create a tracked job directly;
- submit an application.

---

## HTML normalization and original evidence

Greenhouse descriptions are returned as HTML.

The provider performs two separate actions:

1. converts HTML into readable plain text for the Job Processing input;
2. preserves the original HTML in provider metadata.

This avoids sending markup into the deterministic or AI extractor while retaining the original provider evidence for audit.

The normalizer:

- decodes HTML entities;
- preserves paragraph and heading breaks;
- turns list items into readable bullet lines;
- removes tags;
- collapses accidental whitespace.

It does not summarize, rewrite, or infer requirements.

---

## Bounded network behavior

The provider uses conservative operational limits:

```text
GREENHOUSE_DISCOVERY_TIMEOUT_SECONDS=10
GREENHOUSE_DISCOVERY_RETRY_COUNT=1
GREENHOUSE_DISCOVERY_MAX_BOARDS=5
GREENHOUSE_DISCOVERY_MAX_JOBS_PER_BOARD=100
```

The code also caps retries at two even when a larger environment value is supplied.

Requests include:

- method: GET;
- `Accept: application/json`;
- an identifiable user agent;
- a timeout.

Retries are allowed only for network errors, timeouts, HTTP 429, and server-side 5xx errors. Client-side 4xx errors are not repeatedly retried.

---

## Per-employer source attempts

A multi-employer provider run should not be one opaque success or failure.

Every configured board creates a `DiscoverySourceAttempt` with:

- discovery run;
- source key and employer label;
- board token;
- success, failed, or skipped state;
- result count;
- elapsed time;
- error message;
- request and provider metadata.

This supports three run outcomes:

```text
all boards succeed          → Completed
some succeed, some fail     → Partially completed
all boards fail             → Failed
```

Successful employer results remain available during a partial run. A failing employer does not erase them.

---

## Why failed refreshes cannot close jobs

An empty result and a failed request are not the same fact.

A successful request returning no jobs may indicate that previously observed jobs disappeared from that board.

A timeout, DNS error, rate limit, malformed response, or server failure says nothing about whether those jobs remain open.

Therefore source-closure reconciliation runs only for a board whose attempt status is `success`.

```text
successful board refresh + missing prior ID
→ prior source observation marked closed

failed board refresh
→ no source-closure changes
```

This prevents network failures from creating false closed-job conclusions.

---

## Source observations and historical records

Discovery records are audit observations, not mutable copies of a provider listing.

When the same Greenhouse post is observed again:

- the new observation becomes the active source record;
- prior observations remain in history;
- duplicate detection links the rediscovery to earlier evidence;
- the prior observation is no longer active but is not marked closed when the ID is still present.

When an ID disappears during a later successful board refresh:

- the latest prior observation is marked inactive;
- `source_closed_at` is recorded;
- the historical record remains visible;
- it cannot be sent to Job Processing.

A newly rediscovered or reopened post creates a new active observation and still receives duplicate review.

---

## Provider metadata retained

Each Greenhouse opportunity retains:

- curated board key, label, and token;
- Greenhouse job-post ID;
- internal job ID when supplied;
- source URL;
- provider update timestamp;
- location object;
- departments;
- offices;
- language;
- custom metadata;
- original HTML description;
- normalized raw listing text;
- local URL, text, and role fingerprints.

This supports later debugging and provenance review without treating the metadata as approved requirements.

---

## Why no new scoring logic was added

Discovery is recall-oriented. It should find plausible opportunities broadly enough that Job Processing and Job Evaluation can make the consequential decisions later.

The existing broad label still uses manually maintained search preferences. The Greenhouse provider does not inspect the activated résumé snapshot or run the matcher.

```text
Greenhouse source
→ broad discovery label
→ human inbox review
→ structured Job Processing
→ profile-aware Job Evaluation
```

Keeping these stages separate prevents provider titles or descriptions from bypassing validation.

---

## Testing strategy

CI never contacts Greenhouse.

The test suite mocks `urlopen` and verifies:

- live requests are disabled by default;
- only the GET jobs endpoint is constructed;
- `content=true` is requested;
- no application endpoint appears;
- HTML is converted to readable text;
- original HTML and provider metadata are preserved;
- job limits prefer the most recently updated records;
- partial board failures retain successful results;
- source attempts record both success and failure;
- discovery creates no `JobPosting`;
- successful refreshes close disappeared IDs;
- failed refreshes do not close prior listings;
- closed source records cannot enter Job Processing.

---

## Local configuration

Add a real employer only in the local `.env` file:

```text
JOB_DISCOVERY_LIVE_ENABLED=true
GREENHOUSE_DISCOVERY_BOARDS=[{"key":"approved-employer","label":"Approved Employer","board_token":"approved-employer","industry_hint":"Medical devices","enabled":true}]
```

The board token is not an API key. It is the public identifier used by the employer's Greenhouse job board. It should still be configured deliberately because it controls which employers the program searches.

After changing `.env`, restart Django before running discovery.

---

## Manual validation sequence

1. Configure one approved employer board.
2. Keep `GREENHOUSE_DISCOVERY_MAX_BOARDS=1` for the first test.
3. Enable live discovery.
4. Restart Django.
5. Open Discovery.
6. Select **Greenhouse approved employer boards**.
7. Run controlled discovery.
8. Confirm the run records one employer source attempt.
9. Open one result and inspect provider metadata, original source URL, normalized listing text, and broad preference explanation.
10. Confirm no tracked job exists yet.
11. Send one result to Job Processing.
12. Review every extracted field before saving.
13. Run Greenhouse discovery again and confirm repeated job-post IDs become duplicate observations.
14. Disable live discovery again when the controlled test is finished, unless recurring discovery is intentionally being configured next.

---

## Architectural takeaway

External data access should be narrower than the provider's technical capability.

```text
public API
+ explicit employer allowlist
+ disabled-by-default network switch
+ bounded requests
+ per-source audit
+ conservative closure logic
+ existing human review
= controlled live discovery
```

The next stage can reuse this pattern for another approved provider or add scheduling over the stable Greenhouse interface without weakening the Discovery-to-Processing contract.
