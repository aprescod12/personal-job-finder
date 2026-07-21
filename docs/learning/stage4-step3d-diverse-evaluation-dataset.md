# Stage 4, Step 3D — Building a Diverse Job-Extraction Evaluation Dataset

## Purpose

The first Organon test proved that the AI extractor could outperform the deterministic parser on one real medical-device co-op posting. One case, however, cannot establish reliability.

A model can look excellent on one familiar structure and fail on:

- a different engineering discipline,
- a poorly formatted listing,
- a rolling deadline,
- an experience range,
- ambiguous sponsorship language,
- a citizenship requirement,
- or a required-versus-preferred boundary.

Step 3D expands the benchmark from one historical example to a small, deliberately varied evaluation dataset.

The purpose is not to create a large collection of job postings. The purpose is to create a controlled set of difficult examples that reveal whether extraction changes improve the system consistently.

---

## 1. What this step adds

The benchmark now contains seven cases:

| Case | Primary role | Main extraction challenge |
|---|---|---|
| 001 | Medical-device engineering co-op | Real listing, enrollment, preferred equipment experience, residency and sponsorship wording |
| 002 | Embedded firmware engineer | Bounded 0–2 year range, deadline, preferred RTOS/BLE/IEC 62304, no sponsorship |
| 003 | Quality validation engineer | Rolling deadline, internship-inclusive experience, standards familiarity versus certification |
| 004 | Medical-device software engineer | Two-year requirement with academic-project allowance, remote with quarterly onsite work, sponsorship unknown |
| 005 | General software contractor | Poor formatting, contract and part-time details, no degree requirement, no authorization language |
| 006 | Biomedical test engineer | Ambiguous case-by-case sponsorship, 1–3 year range, negative driver's-license fact |
| 007 | Defense medical systems test engineer | Explicit citizenship, clearance eligibility, active clearance only preferred, no sponsorship |

This is not yet a statistically representative sample of the job market. It is an initial engineering benchmark designed to exercise important failure modes.

---

## 2. Why the new cases are synthetic

Case 001 preserves a real listing because it records an actual controlled test. The new cases are synthetic.

Synthetic cases provide several advantages:

1. **Stability** — the source will not disappear or change when an employer edits a page.
2. **Copyright control** — the repository does not become a collection of copied employer postings.
3. **Targeted difficulty** — each case can isolate a specific extraction problem.
4. **Clear provenance** — every synthetic listing is labeled as not being a live opening.
5. **Safe retention** — cases can remain permanently in GitHub without suggesting that the jobs are currently available.

Synthetic cases also have weaknesses:

- They may be cleaner than real postings.
- Their wording may reflect the benchmark author's assumptions.
- They cannot reproduce every employer platform or legal disclaimer.
- A prompt may eventually overfit to repeated synthetic phrasing.

For those reasons, the final evaluation library should contain both:

- stable synthetic edge cases, and
- a limited number of carefully retained real-world historical cases.

---

## 3. Coverage is not the same as case count

Adding many nearly identical listings does not create a diverse benchmark.

A useful dataset varies along several dimensions.

### Role family

The current set includes:

- medical-device development,
- embedded firmware,
- quality and validation,
- medical-device software,
- general web software,
- biomedical testing,
- and defense systems testing.

### Seniority and experience

The cases include:

- internship/student,
- entry level,
- early career,
- mid level,
- no numeric experience requirement,
- bounded ranges,
- and minimum-only requirements.

### Work arrangement

The cases include:

- on-site,
- hybrid,
- remote with an in-person condition,
- and unknown/not specified.

### Deadline style

The cases include:

- confirmed written dates,
- numeric short-form dates,
- rolling review,
- and no deadline stated.

### Authorization language

The cases deliberately create a progression:

```text
no authorization statement
→ current authorization required, future sponsorship unknown
→ sponsorship considered case by case
→ sponsorship explicitly unavailable
→ citizenship and clearance explicitly required
```

This progression is important because authorization mistakes have asymmetric consequences. A false blocker can hide a valid opportunity, while a missed blocker can waste application effort.

### Listing structure

The dataset includes:

- conventional section headings,
- mixed narrative and bullets,
- compressed slash-separated identity lines,
- informal headings such as `must have` and `nice`,
- and explicit negative statements.

---

## 4. Ground truth is a human decision record

The extractor output is not allowed to define the benchmark answer.

Ground truth is created through human review of the source listing. It records:

- expected job identity fields,
- expected requirements,
- supplemental facts,
- critical checks,
- and forbidden interpretations.

This separation prevents a circular evaluation process:

```text
model produces output
→ output copied into expected answer
→ model receives perfect score
```

Ground truth may change only when the source was transcribed incorrectly, a human interpretation was wrong, or the schema changes explicitly.

A low model score is not a reason to weaken the expected answer.

---

## 5. Canonical facts versus verbatim text

The listing is preserved verbatim in `listing.txt`, but expected values are usually canonical facts.

For example:

```text
Listing: “Zero to two years of internship, project, or professional experience.”
Expected minimum: 0
Expected maximum: 2
Expected note: internship and project experience are accepted
```

The benchmark should not demand exact sentence copying for every field. It should evaluate whether the extractor captured the underlying fact correctly.

At the same time, exact wording matters for sensitive restrictions. Evidence quotes preserve source language such as:

```text
United States citizenship is required.
Sponsorship decisions are made case by case and are not guaranteed.
```

The future scorer will need both semantic comparison and exact critical-check logic.

---

## 6. Critical checks and ordinary fields

Not all mistakes are equally harmful.

Missing a secondary preferred technology is less serious than:

- extracting the wrong employer,
- inventing a degree requirement,
- dropping the word `No` from a sponsorship statement,
- converting ambiguous sponsorship into a hard blocker,
- or confusing an active clearance preference with a required active clearance.

Each case therefore contains critical checks with severity levels:

- `critical`
- `major`
- `minor`

A future evaluation report should show both:

1. overall field accuracy, and
2. critical-error counts.

A system with 95 percent ordinary-field accuracy but one false citizenship interpretation should not be described as fully safe.

---

## 7. Required versus preferred qualifications

This is one of the benchmark's repeated themes because it directly affects matching.

The extractor must preserve section boundaries:

```text
Required
- Python

Preferred
- Django
```

A wrong-category error is different from a missing-field error.

- Missing Django loses useful context.
- Marking Django as required can incorrectly lower a candidate's match.

The future scorer should therefore distinguish:

- correct category,
- wrong category,
- missing,
- unsupported,
- and partially correct.

Cases 001 through 007 include repeated required/preferred boundaries so prompt changes cannot improve one role while degrading another unnoticed.

---

## 8. Authorization is evidence, not candidate evaluation

The Job Processing Agent extracts listing restrictions. The Job Evaluation Agent later compares them with the candidate profile.

Processing should answer:

```text
What did the employer state?
```

Evaluation should answer:

```text
Does that statement block this candidate?
```

These questions must remain separate.

Examples:

### Explicit blocker

```text
Visa sponsorship is not available.
```

The Processing Agent may classify this as a hard listing restriction.

### Ambiguous policy

```text
Sponsorship decisions are made case by case.
```

The Processing Agent should preserve the evidence but should not automatically declare the candidate ineligible.

### Silence

```text
The posting says nothing about sponsorship.
```

The system must remain unknown rather than guessing.

The benchmark includes all three situations.

---

## 9. Negative facts matter

Extraction systems often focus on positive requirements and lose explicit negatives.

Examples in the dataset include:

- no degree required,
- no certification required,
- no driver's license required,
- no deadline stated,
- sponsorship not stated,
- and work arrangement not specified.

These facts prevent unsupported assumptions.

A future scorer should reward correct preservation of negative facts and penalize contradictions such as:

```text
Source: degree not required
Output: bachelor's degree required
```

---

## 10. Avoiding data leakage

Data leakage occurs when information from expected answers reaches the extractor input.

The application should send only:

- listing text,
- source label,
- and source URL metadata.

It must not send:

- `ground-truth.json`,
- `notes.md`,
- critical-check descriptions,
- forbidden interpretations,
- prior model judgments,
- or expected field values.

Evaluation code may compare output with ground truth only after extraction completes.

The cases are stored near each other for repository organization, but the runner must enforce this logical separation.

---

## 11. Avoiding overfitting

Overfitting means improving performance on the saved cases without improving general extraction.

Warning signs include:

- adding prompt rules that quote a benchmark listing,
- special-casing company names,
- writing regexes only for one exact phrase,
- changing ground truth to match current output,
- or repeatedly testing only the case that motivated a change.

A healthy development cycle is:

```text
identify a repeated failure pattern
→ propose a general rule
→ rerun every saved case
→ test at least one unseen listing
→ accept the change only when benefits exceed regressions
```

Case 001 remains valuable, but it must no longer be the only test used during prompt refinement.

---

## 12. What the future evaluation scorer should do

The scorer built in Step 3D.4 should consume these cases without affecting production ranking.

It should:

1. Load and validate every case.
2. Run a selected extractor against `listing.txt` only.
3. Record provider, model, prompt, schema, and extractor versions.
4. Measure latency and fallback use.
5. Compare job fields and requirement fields.
6. Check required/preferred category placement.
7. Evaluate experience ranges and dates.
8. Run critical checks.
9. detect forbidden interpretations where possible.
10. Generate a report without changing source cases.

The scorer should not:

- modify job-match weights,
- rank opportunities for the user,
- write `JobPosting` records,
- change candidate eligibility,
- or call the live AI provider during CI.

---

## 13. Why the benchmark stays in the repository

The cases are permanent development assets.

Keeping them allows future comparisons across:

- prompt versions,
- schema versions,
- model changes,
- deterministic-parser changes,
- normalization layers,
- and fallback behavior.

Generated experiments may be removed, but the official cases and accepted run reports should remain as history.

This is similar to keeping unit tests after a bug is fixed. The test is valuable precisely because it prevents the bug from silently returning.

---

## 14. Current limitations

The dataset still lacks several useful situations:

- multiple listed locations,
- salary ranges with hourly versus annual units,
- temporary versus contract ambiguity,
- required professional licenses,
- graduate-degree requirements,
- multilingual or partially formatted listings,
- extremely long legal boilerplate,
- and employer-specific application questions.

It also contains only one historical real-world listing.

These gaps should be addressed gradually. Adding cases without a clear failure mode would increase maintenance without necessarily improving evaluation quality.

---

## 15. Recommended reading order

1. `docs/evaluations/job-processing/cases/README.md`
2. Case 001 listing, ground truth, and notes
3. Case 004 for incomplete sponsorship information
4. Case 006 for case-by-case sponsorship
5. Case 007 for explicit citizenship and clearance
6. Case 005 for poor formatting
7. `tracker/services/job_extraction_evaluation.py`
8. The future Step 3D.4 scorer once implemented

---

## 16. Exercises

### Exercise 1 — Classify evidence

For each line below, decide whether it belongs in work authorization, hard disqualifiers, or notes:

```text
Sponsorship is unavailable.
Sponsorship may be considered.
Must be authorized through the start date.
The listing does not discuss sponsorship.
```

### Exercise 2 — Find a wrong-category error

Run the deterministic parser against Case 002 and identify which preferred qualifications are incorrectly mixed into other fields or lost.

### Exercise 3 — Add an unseen case

Draft a synthetic listing with multiple locations and a salary range. Create ground truth without reading any extractor output first.

### Exercise 4 — Protect against leakage

Sketch a runner function signature that receives a `JobExtractionEvaluationCase` but passes only `listing_text` and source metadata to the extractor.

### Exercise 5 — Design severity weights

Propose numeric penalties for critical, major, and minor failures. Explain why one critical authorization error should not be hidden by many correct low-risk fields.

### Exercise 6 — Test overfitting

After a prompt change improves Case 001, identify which other cases must be rerun and what regression would cause you to reject the change.

---

## 17. Self-check questions

1. Why is one successful live test insufficient?
2. Why are synthetic cases useful?
3. What is the main weakness of synthetic data?
4. Why must expected answers be written independently from model output?
5. What is the difference between verbatim evidence and canonical ground truth?
6. Why should authorization extraction and candidate eligibility remain separate?
7. Why is `case by case` sponsorship not a hard no?
8. Why is a required-versus-preferred mistake more serious than a simple omission?
9. What is data leakage in this evaluation workflow?
10. What is overfitting to the benchmark?
11. Why should negative facts be preserved?
12. Why should the evaluation scorer remain separate from the `/100` job-match score?
13. Why do the cases remain after extraction improves?
14. What information should every evaluation run record?
15. Why must CI avoid live AI calls?

### Answers

1. It does not reveal performance across different formats, roles, deadlines, experience rules, or authorization language.
2. They are stable, targeted, retainable, and safe from employer-page changes.
3. They may reflect author assumptions and fail to reproduce real-world messiness.
4. Otherwise the benchmark becomes circular and cannot measure error.
5. Evidence is exact source language; canonical ground truth is the normalized fact the system should recover.
6. Processing records what the employer said; evaluation determines what it means for a particular candidate.
7. It expresses uncertainty and possible consideration rather than categorical unavailability.
8. It can incorrectly change eligibility or match strength instead of merely losing useful context.
9. Expected answers or notes entering the extractor's prompt or input.
10. Tuning specifically to saved cases without improving unseen listings.
11. They prevent invented requirements and preserve meaningful absences.
12. The evaluation scorer measures extraction quality; the production score measures candidate-job fit.
13. They provide regression protection and historical comparability.
14. Case ID, provider, extractor version, schema version, prompt version, model, date, latency, fallback use, and field results.
15. CI must remain deterministic, free, secret-independent, and provider-independent.

---

## 18. Decision carried forward

The benchmark is now broad enough to begin building a deterministic evaluation runner.

The next implementation step is:

```text
load validated cases
→ run the deterministic extractor
→ compare outputs with ground truth
→ report field and critical-check results
```

AI evaluation remains optional and local. Prompt refinement should begin only after the runner produces a baseline across the complete dataset.
