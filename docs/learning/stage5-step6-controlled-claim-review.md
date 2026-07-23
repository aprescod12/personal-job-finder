# Stage 5 Step 6 — Human Review and Controlled Claim Persistence

## Why this step exists

Résumé extraction is not the same as candidate-profile truth.

Even after structured output, document grounding, local evidence anchoring, and benchmark testing, an extractor can still:

- classify a fact under the wrong section;
- combine neighboring entries;
- choose the wrong primary email;
- preserve a résumé typo;
- omit useful context;
- produce wording the candidate does not want reused;
- extract a true fact that is not appropriate for every job search.

Step 6 adds the human decision boundary between extracted claims and reusable candidate evidence.

The rule is:

> Extraction may propose. Only the user may approve.

## The three data layers

The implementation deliberately separates three kinds of data.

### 1. Resume source

`ResumeSource` stores the original file and its SHA-256 fingerprint.

It answers:

- Which document was supplied?
- Which exact version was used?
- Is the file still stored?

The file itself is evidence. It is not the career profile.

### 2. Extraction review

`ResumeExtractionReview` and `ResumeReviewClaim` store the review workflow.

A review records:

- source fingerprint, label, and filename;
- provider key, mode, and version;
- document-reader key and version;
- fallback/orchestration metadata;
- extraction and document warnings;
- every proposed claim;
- the extracted value;
- the edited value;
- the user’s pending, approved, or rejected decision;
- whether the approved claim has already been applied.

This layer is editable until a claim is applied.

### 3. Approved candidate evidence

`CandidateProfileClaim` stores only explicitly approved claims.

Each approved claim preserves:

- the reviewed value;
- the field path and section;
- exact source evidence;
- evidence notes;
- source SHA-256, label, and filename;
- provider key, version, and mode;
- parser key and version;
- approval time;
- active or superseded status.

This is the reusable evidence layer that later matching and profile-building steps can consume.

## Why AI output does not write directly to `CareerProfile`

The existing `CareerProfile` contains manually maintained information such as:

- target roles;
- preferred industries;
- work arrangement;
- salary preferences;
- work authorization;
- priorities;
- deal breakers;
- manually written summaries and skills.

Those fields include preferences and judgments that a résumé cannot determine safely.

Directly copying AI output into that model would create several risks:

1. **Silent overwrite** — a model could replace wording the user intentionally wrote.
2. **Mixed provenance** — manual preferences and résumé facts would become indistinguishable.
3. **Hard rollback** — it would be difficult to identify which provider or résumé version caused a change.
4. **Incorrect authority** — the extractor would effectively become the decision maker.
5. **Matcher instability** — a new extraction could unexpectedly change job rankings.

Step 6 therefore writes approved résumé facts to `CandidateProfileClaim`, not directly to manual fields.

A later profile-composition step can decide how manual fields and approved evidence should be combined.

## Claim decisions

Each review claim has one of three decisions.

### Pending

The user has not decided yet.

Pending claims:

- remain editable;
- are never applied;
- do not affect candidate evidence;
- do not affect match scores.

### Approved

The user accepts the reviewed value.

Approval alone does not persist the claim. The user must also select **Apply Approved Claims**.

This two-action design prevents an accidental dropdown change from immediately altering reusable evidence.

### Rejected

The user does not want the claim used.

Rejected claims remain in the review audit record but never enter active candidate evidence.

## Save versus apply

The review page has two distinct actions.

### Save Review Only

This action stores:

- edits;
- pending/approved/rejected decisions.

It creates no `CandidateProfileClaim` records.

### Apply Approved Claims

This action:

1. saves all current edits and decisions;
2. selects approved claims that have not already been applied;
3. validates that approved values are not blank;
4. computes a semantic key;
5. supersedes matching active evidence when appropriate;
6. creates provenance-backed candidate claims;
7. locks applied review claims.

Pending and rejected claims are ignored.

## Why applied claims become locked

Once applied, the reviewed value and provenance form an audit record.

Allowing the review value to change afterward would make the approval history misleading: the saved candidate claim could say one thing while its review claim later displayed another.

Applied claims are therefore immutable in the review interface.

A correction should come from a new extraction/review cycle or a future explicit claim-management workflow.

## Semantic supersession

New résumé versions often repeat existing facts.

Without supersession, the evidence store could accumulate several active versions of the same name, summary, skill, or experience entry.

Step 6 computes a semantic key differently by claim type.

### Scalar claims

Examples:

- full name;
- email;
- phone;
- location;
- professional summary.

The semantic identity is based on the field path. Approving a new full-name claim supersedes the previous active full-name claim.

### List-item claims

Examples:

- skills;
- links.

The semantic identity includes the normalized value. Python and MATLAB remain separate active claims, while a repeated Python claim supersedes the prior Python evidence.

### Structured entries

Examples:

- education;
- experience;
- projects;
- certifications;
- leadership.

The semantic identity uses the section, heading, and subheading when available. A newly approved version of the same project or role supersedes the prior active version while preserving history.

## Re-extraction behavior

Creating a new extraction review marks older unfinished reviews as stale.

This prevents the user from accidentally reviewing two different extraction snapshots as though both were current.

Important boundaries:

- previously approved candidate claims remain active;
- a new extraction does not automatically replace them;
- only newly approved and explicitly applied claims can supersede matching evidence;
- changing the active résumé source does not change approved evidence by itself.

## Source deletion behavior

A user may remove a stored résumé file later.

Approved claims must not lose their audit identity when that happens.

`CandidateProfileClaim` therefore stores a provenance snapshot:

- source SHA-256;
- source label;
- source filename;
- provider and parser versions;
- evidence text.

The optional database links to `ResumeSource` and `ResumeReviewClaim` may become null after deletion, but the approved claim remains usable and auditable.

## Human review does not prove objective truth

Approval means:

> The user reviewed this extracted claim and chose to include it as candidate evidence.

It does not prove that every résumé statement is independently verified by an employer, school, or certification authority.

The system should preserve the distinction between:

- source-grounded;
- user-approved;
- externally verified.

Step 6 implements the first two, not the third.

## Security and privacy boundaries

This step does not make a new OpenAI request.

It works with the extraction result already produced by the configured provider.

The implementation also avoids storing another copy of the full parsed résumé text. The review page reopens and parses the stored source locally when raw text needs to be displayed.

Approved claims store only the evidence excerpt needed for provenance.

## Database transaction boundaries

Saving review forms and applying approved claims are performed inside database transactions.

This matters because a partial apply would be dangerous. For example, the system should not:

- save half the edits;
- create some candidate claims;
- fail on another claim;
- leave the review in an ambiguous state.

If validation or application fails, the transaction rolls back.

## Idempotency

A review claim has an `applied_at` timestamp and a one-to-one link to its candidate claim.

Running **Apply Approved Claims** again does not create another copy of claims already applied.

Only approved claims with no `applied_at` value are eligible.

## Tests added

The Step 6 tests verify that:

- extraction creates persistent pending review claims;
- no manual career-profile field changes during extraction;
- a newer extraction marks older open reviews stale;
- website edits and decisions save without applying;
- only approved claims are persisted;
- provenance fields are copied correctly;
- applied review claims become locked;
- a repeated scalar claim supersedes the prior active claim;
- source deletion preserves the provenance snapshot;
- closing an unapplied review rejects pending claims;
- the review and approved-claim pages disclose the safety boundary;
- no live OpenAI request is required in tests.

## Commands

After merging, run:

```bash
python3 manage.py migrate
python3 manage.py check
python3 manage.py test candidate_profile
```

For a website test:

1. Extract a stored résumé.
2. Edit one claim.
3. Mark one claim approved.
4. Mark one claim rejected.
5. Select **Save Review Only**.
6. Confirm that the approved-claims page is still unchanged.
7. Select **Apply Approved Claims**.
8. Confirm that only the approved claim appears.
9. Confirm that the manual Career Profile page remains unchanged.
10. Return to the review and confirm the applied claim is locked.

## Next step

The next Candidate Profile Agent step should compose a job-evaluation-ready profile from:

- manually maintained career preferences;
- active approved résumé claims;
- stored projects;
- future user-entered evidence.

That composition layer should be deterministic and transparent before it is supplied to the Job Evaluation Agent.
