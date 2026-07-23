# Stage 5 Step 8 — Profile Change and Job Reevaluation History

## Why this step exists

The matcher already recalculates a job whenever the Match Analysis page is opened. That guarantees a current live answer, but it does not preserve what the answer used to be.

After a résumé, approved claim, candidate snapshot, manual preference, job requirement, or matcher version changes, two different questions matter:

1. What is the job's score now?
2. How and why did that result change from the previous profile version?

A dynamic-only matcher answers the first question. A persisted evaluation history is required for the second.

The workflow is now:

```text
current candidate profile + current job requirements
→ live match analysis
→ explicit persistence as a JobEvaluationRun
→ later input change marks the run stale
→ explicit reevaluation creates a new immutable run
→ old and new results remain comparable
```

No AI or external API call is introduced by this step.

---

## Live analysis versus persisted evaluation

These are intentionally separate concepts.

### Live analysis

The live result is calculated when a job or dashboard page is rendered. It always uses the current activated candidate snapshot and current manual preferences.

It answers:

> What does the matcher think right now?

### Persisted evaluation

A `JobEvaluationRun` is created only when the user selects **Save Baseline**, **Reevaluate Job**, or **Reevaluate All Jobs**.

It answers:

> What exact result did the system preserve at a specific point in time?

This separation avoids creating database history merely because a page was refreshed.

---

## What each evaluation run stores

Every run records:

- job and career profile;
- active candidate-profile snapshot, when one exists;
- candidate snapshot version and composition version;
- matcher version;
- manual-profile fingerprint;
- job-and-requirements fingerprint;
- score, classification, opportunity lane, and evidence coverage;
- category results;
- direct, related, and controlled-semantic evidence;
- gaps;
- confirmed and review blockers;
- trigger type;
- previous run;
- comparison with the previous run;
- current or stale state;
- stale reasons;
- evaluation timestamp.

The full result is stored as structured JSON so future interface changes do not erase historical evidence.

---

## Fingerprints

A fingerprint is a SHA-256 digest of canonical structured input.

### Profile fingerprint

The profile fingerprint includes:

- all manually controlled CareerProfile fields;
- active candidate snapshot ID;
- snapshot version;
- composition version;
- snapshot fingerprint.

The raw résumé file is not hashed again here because the activated snapshot already identifies the approved evidence version supplied to matching.

### Job fingerprint

The job fingerprint includes evaluation-relevant fields from:

- `JobPosting`;
- `JobRequirement`.

Operational fields such as application status and next action are not intended to change fit. Listing text, role, skills, education, experience, industry, location, arrangement, authorization, and blockers do affect fit and are included.

Canonical JSON sorting ensures that the same values produce the same fingerprint.

---

## Automatic staleness

A persisted result is current only while all of its important inputs still match.

The system marks current evaluations stale after:

- a manual CareerProfile save;
- activation of a candidate-profile snapshot;
- a JobPosting save;
- a JobRequirement save.

Matcher-version drift is detected whenever evaluation status is read. This matters because deploying new matcher code does not save any database model that a Django signal could observe.

Staleness does not delete or recalculate anything. It records that the historical run no longer represents the current input state.

---

## Why reevaluation remains explicit

Automatic staleness and automatic reevaluation are different decisions.

Marking stale is safe because it only reports an input mismatch.

Automatically creating a new persisted result after every edit would create several problems:

- intermediate form edits could generate noise;
- a bulk profile update could produce many redundant runs;
- page loads and signals could cause hidden work;
- history would become difficult to interpret;
- future AI-based evaluation could create unexpected cost.

Therefore:

```text
input change → automatic stale marker
new persisted result → explicit user action
```

The live match still recalculates immediately, so the user is never forced to look at an outdated score.

---

## One current run per job

The database enforces at most one current `JobEvaluationRun` for each job.

When reevaluation runs:

1. the job row is locked;
2. the previous latest run is identified;
3. the current matcher executes;
4. the old current run is marked historical;
5. the new run is created as current;
6. the previous-run relationship is preserved.

Historical runs are never overwritten.

---

## Score and evidence comparison

A score change alone is not sufficient explanation.

The comparison stores:

- score delta;
- classification change;
- opportunity-lane change;
- newly added direct evidence;
- removed direct evidence;
- newly added related or semantic evidence;
- removed related or semantic evidence;
- resolved gaps;
- new gaps.

Evidence is compared using normalized requirement-and-evidence pairs. Gaps are compared by normalized requirement.

This makes changes such as the following auditable:

```text
Candidate Profile v1
Python requirement → gap
Score 58

Candidate Profile v2
Python requirement → direct match from approved résumé skill
Score 66

Comparison
+8 points
1 added direct match
1 resolved gap
```

The comparison describes matcher output changes. It does not claim that one profile version is objectively better in every recruiting context.

---

## Calibration preservation

`JobCalibration` stores the user's judgment together with the matcher result shown when that judgment was saved.

Reevaluation does not change:

- human rating;
- opportunity lane selected by the user;
- saved predicted score;
- saved predicted classification;
- saved predicted track;
- notes.

That historical snapshot is necessary for honest matcher calibration. Replacing it with the newest score would make past human-versus-model comparisons meaningless.

Evaluation history and calibration therefore serve different purposes:

```text
JobEvaluationRun → how system output changes over time
JobCalibration → what user judgment was paired with the system at review time
```

---

## Bulk reevaluation

**Reevaluate All Jobs** runs the existing deterministic matcher once for every tracked job and creates a new current run for each.

It does not:

- fetch job websites;
- call OpenAI;
- alter job requirements;
- alter candidate claims;
- alter calibrations;
- apply to jobs.

The first bulk run establishes baselines. Later bulk runs create comparable history after profile or matcher changes.

The implementation is synchronous because the current personal dataset is small. A future background-task system can reuse the same evaluation service if job volume becomes large.

---

## Blind validation protection

The bulk service may persist the matcher result for a blind holdout, but the interface continues hiding evaluation history until the independent human judgment is recorded.

This preserves validation integrity while retaining one common evaluation pipeline.

---

## Django model registration

`JobEvaluationRun` lives in `tracker/evaluation_models.py` rather than further expanding the already large `tracker/models.py` file.

`TrackerConfig.ready()` imports the model module so Django registers it for:

- migrations;
- system checks;
- ORM access;
- admin registration.

The admin interface is read-only because evaluation runs are audit records created by the workflow, not manually authored data.

---

## Tests

The regression suite verifies that:

- a first evaluation creates a current baseline;
- profile changes mark it stale;
- requirement changes mark it stale;
- matcher-version drift is detected;
- reevaluation preserves the previous run;
- one current run exists per job;
- resolved gaps and added evidence are reported;
- bulk reevaluation covers every job;
- endpoints require POST;
- the match page distinguishes live and persisted state;
- dashboard counts distinguish current, stale, and missing baselines;
- history displays multiple versions;
- calibration snapshots remain unchanged.

---

## Manual test

After merging and migrating:

1. Open a job's Match Analysis.
2. Select **Save Baseline**.
3. Confirm the status changes to **Current**.
4. Open **View History** and inspect the first run.
5. Change an approved résumé claim or manual Career Profile field.
6. Activate a new candidate snapshot if résumé evidence changed.
7. Return to Match Analysis.
8. Confirm the live score reflects current inputs and the persisted status says **Stale**.
9. Select **Reevaluate Job**.
10. Confirm a new current run appears with score and evidence changes.
11. Confirm the prior run remains visible.
12. Confirm the saved human calibration has not changed.
13. Use **Reevaluate All Jobs** on the dashboard and confirm every non-blind card becomes current.

---

## Architectural takeaway

A trustworthy agent workflow needs both current computation and historical state.

```text
versioned candidate evidence
+ versioned matcher
+ versioned job requirements
→ reproducible job evaluation
```

This reevaluation layer should be in place before automated Job Discovery adds many more opportunities. It ensures that newly found jobs and previously stored jobs can be compared against the same explicit candidate-profile version.
