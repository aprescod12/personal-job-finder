# Stage 5 Step 7 — Candidate Profile Composition and Activation

## Why this step exists

Stage 5 Step 6 created a trustworthy evidence layer. A résumé claim can enter that layer only after a human edits it, approves it, and explicitly applies it.

That still leaves an important systems question:

> Which exact set of approved claims should the job matcher use?

Reading the live claim table directly during every match would make results difficult to reproduce. A claim could be approved, superseded, or edited between two job analyses, and the program would not have a stable candidate-profile version to point to.

Step 7 solves that problem by introducing immutable, versioned candidate-profile snapshots.

The workflow is now:

```text
approved active claims
→ deterministic composition
→ immutable preview
→ explicit activation
→ matcher use
```

No AI call occurs during composition.

---

## Evidence, strategy, and snapshots are different things

The project now has three deliberately separate layers.

### 1. Approved candidate claims

These are individual résumé facts with provenance:

- a degree,
- an experience entry,
- a project,
- a skill,
- a leadership entry,
- an identity field.

They answer:

> What evidence has the user explicitly approved?

### 2. Manual career profile

This contains user-controlled strategy and preferences:

- target roles,
- target industries,
- preferred locations,
- work arrangement,
- employment type,
- work authorization,
- priorities,
- deal-breakers,
- experience-level judgment.

It answers:

> What kind of opportunity does the user want and what constraints matter?

### 3. Candidate-profile snapshot

This is an immutable composition of approved résumé evidence at a specific moment.

It answers:

> Which exact evidence version was active when matching ran?

Keeping these layers separate prevents an AI extraction or résumé update from silently changing career strategy.

---

## Deterministic composition

The composer is versioned as:

```text
candidate-profile-composer-v1
```

Given the same approved claims, claim values, and ordering rules, it produces the same structured profile and fingerprint.

The composed structure contains:

```text
identity
  full_name
  emails
  phone
  location
  links

profile
  professional_summary
  education
  experience
  projects
  skills
  certifications
  leadership
```

The composer does not infer missing facts, summarize experience, estimate experience duration, or generate new skills.

---

## Source precedence

Approved evidence can contain variants from multiple résumé reviews. Composition therefore needs explicit precedence rules.

### Scalar fields

Fields such as name, email, phone, location, and professional summary use the newest approved claim for that field.

Older variants are excluded from the snapshot and a warning is shown.

### Structured entries

Education, experience, project, certification, and leadership claims use the newest approved claim for the same extraction slot, then deduplicate identical normalized entries.

### List items

Skills and links are deduplicated case-insensitively while preserving deterministic order.

Precedence is not hidden. The preview includes a warning when older variants were collapsed.

---

## Why snapshots are immutable

After composition, the snapshot stores:

- structured candidate data,
- composition version,
- fingerprint,
- source claim count,
- warnings,
- links to every contributing approved claim,
- a value copy for each claim link.

If an approved claim changes later, the older snapshot does not change.

This supports audit questions such as:

- Which profile version produced this match?
- Which approved claims were included?
- Which résumé and provider produced those claims?
- What changed between profile versions?

Mutable snapshots would make those questions impossible to answer reliably.

---

## Fingerprints and no-op recomposition

The snapshot fingerprint includes:

- composer version,
- contributing claim IDs,
- contributing claim values,
- composed data.

When the user composes again without changing approved evidence, the existing snapshot is reused.

This avoids meaningless version inflation such as:

```text
v1 = same data
v2 = same data
v3 = same data
```

A new version is created only when the composition inputs or output differ.

---

## Preview is not activation

Composition creates a draft preview.

A draft snapshot:

- can be inspected,
- has full claim lineage,
- can show warnings,
- does not affect matching.

Activation is a separate POST action.

This protects against accidental changes caused by merely visiting a page, refreshing, or composing a preview.

---

## One active snapshot

The database enforces one active candidate-profile snapshot per career profile.

Activating a new version:

1. locks the career profile and relevant snapshots,
2. archives the previous active version,
3. activates the selected version,
4. records the activation time.

Archived versions remain available for audit.

---

## The matching adapter

The existing matcher expects a `CareerProfile`-shaped object. Directly copying snapshot evidence into the manual `CareerProfile` would violate the separation boundary.

Instead, Step 7 introduces an adapter.

The adapter supplies evidence-backed fields from the activated snapshot while delegating strategy fields to the manual profile.

### Snapshot-backed evidence

- full name,
- approved résumé skills,
- education evidence,
- experience evidence,
- project evidence,
- certification evidence,
- leadership evidence,
- professional summary.

### Manual strategy

- target roles,
- target industries,
- experience-level judgment,
- preferred locations,
- work arrangement,
- employment type,
- salary preference,
- work authorization,
- priorities,
- deal-breakers.

Manual skills and context are retained as reviewed supplemental evidence and deduplicated with snapshot evidence.

---

## Matcher activation boundary

The matcher follows this rule:

```text
no active snapshot
→ use manual CareerProfile only

active snapshot exists
→ use snapshot evidence + manual preferences
```

Draft and archived snapshots have no matching effect.

The match result receives:

- candidate snapshot ID,
- candidate snapshot version,
- composition version,
- matcher version.

The matcher version is now:

```text
2.2-activated-candidate-snapshot
```

---

## Database design

### `CandidateProfileSnapshot`

Stores:

- profile,
- version,
- status,
- composition version,
- fingerprint,
- structured JSON data,
- warnings,
- source-claim count,
- creation, activation, and archive timestamps.

Constraints enforce:

- unique version per profile,
- unique fingerprint per profile,
- only one active snapshot per profile.

### `CandidateProfileSnapshotClaim`

Stores the immutable lineage between a snapshot and an approved claim:

- source claim,
- position,
- section,
- field path,
- semantic key,
- copied value.

The source claim is protected from deletion while a snapshot references it.

---

## Transaction boundaries

Composition locks the career-profile row before assigning a version. This prevents concurrent composition requests from choosing the same next version.

Activation also locks the profile and target snapshot before archiving the previous active version.

These transaction boundaries support the database constraints rather than relying only on application timing.

---

## What the tests prove

The automated suite verifies that:

- inactive and superseded claims are excluded,
- skills are deduplicated,
- the newest scalar variant wins,
- collapse warnings appear,
- unchanged evidence reuses the same snapshot,
- versions increment only when evidence changes,
- activating a new snapshot archives the previous one,
- only one snapshot is active,
- snapshot data and claim-link values remain immutable,
- manual profile fields remain unchanged,
- manual preferences still reach the matcher,
- draft snapshots do not affect matching,
- activated skills become matching evidence,
- match results expose snapshot metadata,
- compose and activate endpoints require POST,
- the website preview displays the activation boundary.

No live OpenAI request is required for these tests.

---

## Manual testing sequence

After merging and migrating:

1. Open **Approved Claims**.
2. Select **Compose / View Profile Versions**.
3. Click **Compose New Preview**.
4. Verify identity, education, experience, projects, skills, and leadership.
5. Expand the lineage section and inspect source claims.
6. Confirm the preview says **No Matching Effect**.
7. Open a known job and note its current evidence.
8. Activate the candidate-profile version.
9. Reopen the job analysis.
10. Confirm the activated snapshot version is used and approved résumé evidence appears.
11. Confirm manual preferences and Career Profile fields remain unchanged.
12. Compose again without changing evidence and confirm the same version is reused.

---

## Architectural takeaway

Human approval alone is not enough for reproducible agent systems.

Trustworthy profile use requires four boundaries:

```text
extract
→ approve claims
→ compose immutable version
→ activate version
```

This turns a changing collection of facts into a stable, auditable input for job evaluation and later agents.
