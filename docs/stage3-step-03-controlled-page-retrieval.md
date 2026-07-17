# Stage 3 Step 3 — Controlled Employer-Page Retrieval

## Purpose

This step upgrades the manual verification runner from a URL-only preflight to a real employer-page request. It retrieves transport evidence and bounded page text for later interpretation without deciding whether a job is open or closed.

## Manual workflow

1. Open a saved job.
2. Select **Run Verification** or **Retrieve Employer Page**.
3. The runner creates an auditable `ListingVerificationRun`.
4. The controlled retriever validates the destination and performs the request.
5. Redirects, final URL, HTTP status, content metadata, body hash, bounded page text, timing, and errors are saved.
6. The run remains **Needs Manual Review** because page interpretation is a separate step.

## Retrieval policy

The default policy uses:

- HTTP or HTTPS only
- standard ports 80 and 443 only
- an 8-second network timeout
- no environment proxy
- at most 5 redirects
- at most 750,000 response bytes
- text/html, application/xhtml+xml, or text/plain body storage
- `Accept-Encoding: identity`

Unsupported binary responses can still be recorded at the transport level, but their bodies are not stored.

## Network-target safety

Before the first request and before every redirect, the retriever:

- rejects missing or malformed URLs
- rejects embedded usernames or passwords
- rejects localhost names
- resolves the hostname
- rejects private, loopback, link-local, reserved, multicast, unspecified, and other non-public IP addresses
- rejects nonstandard ports

This reduces the risk of the verification feature being used to access local services or private networks.

## Audit evidence

Each successful retrieval records:

- requested URL
- final URL
- HTTP status
- redirect chain
- final hostname
- content type and charset
- content encoding
- declared content length
- bytes stored
- SHA-256 body hash
- bounded page text
- selected response headers
- timeout and response-size policy
- verifier version

## Explicit non-goals

Step 3 does not:

- infer whether the role is open or closed
- decide whether a redirected page is the correct job
- detect an application button
- extract a deadline
- update `JobPosting.listing_status`
- update deadline fields
- update the last-verified date
- run on a schedule
- apply to a job

## Testing

The test suite uses injected fake resolvers and response objects. Automated tests never depend on live employer websites.

Coverage includes:

- successful HTML retrieval
- bounded text and hash storage
- redirects
- private-network blocking
- private redirect blocking
- declared and streamed response-size limits
- unsupported binary content
- normalized network failures
- runner lifecycle and failure capture
- POST-only triggering
- result-page disclosure

## Next step

Stage 3 Step 4 will interpret the retrieved page evidence. It should identify role and company matches, open or closed signals, application actions, and deadline language while retaining confidence scores and manual-review safeguards.
