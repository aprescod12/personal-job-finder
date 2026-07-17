# Stage 3 Step 4 — Employer-Page Interpretation

## Purpose

Step 4 adds a deterministic interpretation layer after controlled employer-page retrieval. It converts bounded page evidence into a suggested listing status, deadline state, role/company match, and application-action result.

The interpretation is stored on `ListingVerificationRun`. It does not update the current `JobPosting` record.

## Workflow

A manual verification run now:

1. Validates the saved public HTTP or HTTPS URL.
2. Retrieves the page under the Step 3 safety policy.
3. Parses visible HTML text, page titles, metadata, links, buttons, and JSON-LD.
4. Compares detected role and company evidence with the saved job.
5. Detects explicit open, closed, expired, broken-link, and wrong-page evidence.
6. Detects application actions and deadlines.
7. Stores the suggested result, confidence, reasons, and transport evidence.
8. Requires human review before the job record changes.

## Evidence sources

The interpreter can use:

- Document title
- Open Graph and page metadata
- Visible page text
- Link and button labels
- Application-like links
- Schema.org `JobPosting` JSON-LD
- `hiringOrganization`
- `validThrough`
- `directApply`
- HTTP response status
- Final redirected URL
- Generic careers/search-page signals

## Listing-status rules

### Open

A page can be suggested as open when:

- The response is successful.
- The saved role matches strongly.
- The saved company matches strongly.
- An application action or matching structured `JobPosting` is present.
- No stronger closed, expired, or wrong-page evidence exists.

### Closed

A page can be suggested as closed when it contains an explicit closure statement, such as no longer accepting applications or the position being filled.

### Expired

A page can be suggested as expired when:

- A confirmed deadline is earlier than the verification date, or
- The page explicitly states that the posting or opportunity expired.

### Broken link

HTTP 404 and 410 responses are treated as strong broken-link evidence unless stronger explicit closure or expiration evidence is present.

### Wrong page

A page can be suggested as the wrong page when:

- It resembles a general careers or job-search page and does not match the saved role.
- The final URL looks like a careers home/search URL without a role match.
- Page-level title evidence clearly describes a different role.

### Unverified

The result remains unverified when the evidence is incomplete or conflicting. Missing application evidence is not treated as proof that applications are closed.

## Deadline rules

The interpreter prioritizes:

1. JSON-LD `validThrough`
2. Explicit deadline phrases such as “application deadline,” “apply by,” or “closing date”
3. Rolling/open-until-filled statements
4. Explicit statements that no deadline is specified

When no reliable deadline evidence exists, the deadline remains unknown.

## Confidence

- **High:** explicit and direct evidence, such as matching structured job data plus an application action, a confirmed passed deadline, an exact closure statement on a matching role, or HTTP 404/410.
- **Medium:** credible but less complete evidence, such as a matching role/company plus an application action without matching structured job data, or a clear wrong-page pattern.
- **Low:** incomplete, ambiguous, blocked, or conflicting evidence.

## Safety boundary

Step 4 does not:

- Automatically update listing status
- Automatically update application deadlines
- Delete or hide jobs
- Apply to jobs
- Contact employers
- Make work-authorization decisions
- Use an LLM or external AI model

A later review/apply step will decide how accepted verification results update the current job record.

## Testing

Tests cover:

- Matching open jobs
- Explicit closed jobs
- Passed deadlines
- HTTP 404/410 behavior
- General careers-page redirects
- Unrelated roles with generic Apply actions
- Ambiguous pages
- Text and JSON-LD deadlines
- Rolling deadlines
- Plain-text responses
- Runner integration
- Confirmation that the current job record remains unchanged
