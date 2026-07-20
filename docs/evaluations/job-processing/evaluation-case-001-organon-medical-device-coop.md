# Job Processing Evaluation Case 001

## Organon Medical Device Engineering Co-op

**Evaluation date:** 2026-07-20  
**Evaluation status:** Baseline recorded  
**Job Processing stage:** Stage 4, Step 3B  
**Purpose:** Compare the deterministic job-listing parser with the first controlled OpenAI structured-extraction run and preserve a baseline for future regression testing.

---

## 1. Why this case exists

This is the first formal evaluation case for the Job Processing Agent.

The application currently supports two extraction paths:

1. A deterministic local parser.
2. A disabled-by-default OpenAI structured-output extractor.

This case records how both extractors handled the same real job listing. Future changes to prompts, schemas, normalization rules, fallback behavior, and model configuration should be tested against this case so improvements and regressions remain visible.

This document is an evaluation record, not a claim that either extractor is production-ready.

---

## 2. Test configuration

### Deterministic extraction

- Provider: deterministic local parser
- Intended role: safe baseline and future fallback
- Network/API use: none
- Human review required: yes

### AI extraction

- Provider label: OpenAI structured extractor
- Backend version: `openai-responses-structured-v1`
- Model configured for the test: `gpt-5-mini`
- Output mode: strict JSON schema
- API storage setting: disabled with `store=False`
- Human review required: yes
- Automatic database save: no

### Shared controls

Both tests used the same pasted job listing and the same review workflow. The user stopped at the review page. No job was approved or automatically created as part of the comparison.

---

## 3. Test listing

### Listing identity

| Field | Ground-truth value |
|---|---|
| Company | Organon |
| Title | Co-Op - Medical Device Engineer - Women's Health |
| Location | Plymouth Meeting, Pennsylvania, United States of America |
| Schedule | Full time |
| Employment category | Intern/Co-op |
| Employment term | Fixed term |
| Requisition ID | R540092 |
| Openings | 1 |
| Relocation | Domestic |
| Travel | No travel required |
| Work arrangement | Not specified |
| Visa sponsorship | No |
| Deadline | No deadline stated |

### Key responsibilities

- Work with Technical Operations Engineers.
- Execute device test methods for design verification.
- Support method development through final test reports.
- Build device drawings in SolidWorks for technical projects.
- Work with tensile and compression test equipment.
- Support the lifecycle of medical devices and combination products.

### Required qualifications

- Enrolled in a bachelor's or master's degree in an engineering or scientific discipline.
- Highly organized.
- Problem-solving ability.
- Methodical completion of technical assignments.
- Strong written and verbal communication skills.
- Excellent interpersonal skills.
- Ability to challenge the status quo professionally.
- Proficiency with Microsoft Excel, Word, and PowerPoint.

### Preferred qualifications

- CAD models and drawings using SolidWorks or similar software.
- Instron tensile/compression machine experience.

### Important eligibility evidence

> US and PR Residents Only

> VISA Sponsorship: No

These statements must be preserved exactly. The Job Processing Agent may identify them as eligibility restrictions, but the Job Evaluation Agent should determine whether they are actual blockers for the candidate.

### Important ambiguity and warning evidence

- The listing displayed an annualized salary range of `$0.00 - $0.00`, which appears to be a placeholder rather than meaningful compensation.
- Flexible work arrangements were explicitly listed as `Not Specified`.
- No application deadline was stated.

---

## 4. Expected structured result

The expected extraction should include the following principles:

- Preserve enrollment as an active student requirement, not a completed-degree requirement.
- Keep required and preferred qualifications separate.
- Do not invent minimum or maximum years of experience.
- Do not infer remote, hybrid, or on-site work when the listing says work arrangement is not specified.
- Do not treat `$0.00 - $0.00` as meaningful compensation.
- Preserve both residency and sponsorship language.
- Separate extracted eligibility restrictions from candidate-specific disqualification decisions.
- Preserve the complete original listing for human review.
- Attach evidence for important extracted fields.

---

## 5. Deterministic parser result

### Summary

The deterministic parser identified a few basic fields but did not extract enough structured information for reliable automated evaluation.

### Field assessment

| Field | Deterministic result | Assessment |
|---|---|---|
| Title | Correct title | Correct |
| Company | Blank | Missing |
| Location | Blank | Missing |
| Employment type | Internship | Mostly correct; lost co-op, full-time, and fixed-term detail |
| Work arrangement | Unknown | Acceptable |
| Deadline status | Unknown | Acceptable but less precise than no deadline stated |
| Seniority | Internship/student | Correct |
| Role family | Full title copied into role family | Wrong category |
| Industry | Blank | Missing |
| Required skills | Blank | Missing |
| Preferred skills | Blank | Missing |
| Required education | Blank | Missing |
| Preferred education | Blank | Correct/acceptable |
| Minimum experience | Blank | Correct |
| Maximum experience | Blank | Correct |
| Responsibilities | Large mixed block containing responsibilities and qualifications | Incorrectly structured |
| Certifications | Blank | Correct |
| Work authorization | `VISA Sponsorship:` without the value | Incomplete and materially unsafe |
| Hard disqualifiers | Blank | Missing restriction evidence |
| Original description | Preserved | Correct |
| Warnings | Company and qualifications not confidently detected | Correct warning behavior |

### Strengths

- Correctly found the job title.
- Correctly recognized an internship/student opportunity.
- Did not invent experience years.
- Did not invent certifications.
- Did not invent a work arrangement.
- Warned when company and qualification extraction failed.
- Preserved the human-review boundary.

### Main failures

- Missed Organon.
- Missed Plymouth Meeting, Pennsylvania.
- Missed required and preferred skill separation.
- Missed the required education statement.
- Mixed requirements into responsibilities.
- Dropped the value `No` from `VISA Sponsorship: No`.
- Missed the `US and PR Residents Only` statement.
- Did not provide sufficient structured evidence for a dependable match score.

### Baseline conclusion

The deterministic parser remains useful as an emergency fallback or draft starter, but this result is not sufficient for unattended job evaluation.

---

## 6. OpenAI structured extractor result

### Summary

The OpenAI extractor produced a substantially more complete and useful structured draft. It correctly captured the most important identity, qualification, and eligibility fields and attached evidence and warnings.

### Field assessment

| Field | AI result | Assessment |
|---|---|---|
| Title | Correct title | Correct |
| Company | Organon | Correct |
| Location | Plymouth Meeting, Pennsylvania, United States of America | Correct |
| Employment type | Internship | Mostly correct; lost full-time, co-op, and fixed-term detail |
| Work arrangement | Unknown | Correct |
| Deadline status | No deadline stated | Correct |
| Application deadline | Blank | Correct |
| Role family | Medical Device Engineer | Correct |
| Seniority | Internship/student | Correct |
| Industry | Global healthcare company | Partially correct but too vague for normalized matching |
| Required skills | Organization, problem-solving, communication, interpersonal skills, Microsoft Office, and related traits | Mostly correct |
| Preferred skills | CAD/SolidWorks and Instron tensile/compression experience | Correct |
| Required education | Enrolled in bachelor's or master's engineering/scientific degree | Correct |
| Preferred education | Blank | Correct |
| Minimum experience | Blank | Correct |
| Maximum experience | Blank | Correct |
| Responsibilities | Device testing, design verification, SolidWorks drawings, equipment familiarity, and reports | Mostly correct with duplication/category overlap |
| Certifications | Blank | Correct |
| Work authorization | Preserved residency and no-sponsorship statements | Correctly preserved |
| Hard disqualifiers | Repeated both eligibility restrictions | Too aggressive without candidate-specific evaluation |
| Requirement notes | Travel, credentialing, and vaccination prerequisites | Correct but secondary |
| Original description | Fully preserved; textarea was only scrolled down during review | Correct |
| Evidence | Field-specific quotes and explanations | Strong |
| Warnings | Placeholder salary and unspecified work arrangement | Strong |

### Clear improvements over the deterministic baseline

The AI extractor correctly found information the deterministic parser missed:

- Company
- Location
- Required education
- Required skills
- Preferred skills
- Responsibilities
- Industry context
- Residency restriction
- No-sponsorship restriction
- No-deadline status
- Evidence for extracted fields
- Useful warnings for placeholder salary and unspecified work arrangement

The most important improvement was preserving:

> US and PR Residents Only

> VISA Sponsorship: No

The deterministic parser captured only the sponsorship label and omitted the value.

---

## 7. Comparative result

### Practical quality estimate

The following percentages are qualitative engineering estimates based on visible core fields, not formal statistical accuracy measurements:

| Extractor | Estimated usable extraction quality |
|---|---:|
| Deterministic parser | 30-40% |
| OpenAI structured extractor | Approximately 90% |

### Interpretation

The AI extractor demonstrated meaningful value beyond the deterministic parser. Its remaining issues are primarily normalization, classification, and duplication problems rather than wholesale misunderstanding of the listing.

The result supports continuing development of the AI-assisted Job Processing Agent while retaining:

- strict schema validation,
- evidence display,
- deterministic fallback,
- explicit warnings,
- and mandatory human review.

It does not support automatic approval or automatic candidate eligibility decisions.

---

## 8. Improvement issues discovered

### JP-001 — Preserve employment details

**Observed:** The listing's `Full time` and `Intern/Co-op (Fixed Term)` details were reduced to `Internship`.

**Desired:** Preserve or separately represent:

- internship/co-op category,
- full-time schedule,
- fixed-term employment term.

### JP-002 — Normalize industry

**Observed:** Industry became `global healthcare company`.

**Desired:** Normalize into useful controlled categories such as:

- medical devices,
- healthcare,
- women's health,
- combination products.

### JP-003 — Deduplicate responsibilities

**Observed:** One responsibility sentence and a shorter paraphrase communicated substantially the same duty.

**Desired:** Avoid duplicate or near-duplicate responsibility entries.

### JP-004 — Separate skills from responsibilities

**Observed:** Familiarity with tensile and compression test equipment appeared as both a skill and a responsibility.

**Desired:** Keep equipment familiarity in qualifications unless the listing clearly describes operating the equipment as a duty.

### JP-005 — Separate restrictions from confirmed blockers

**Observed:** `US and PR Residents Only` and `VISA Sponsorship: No` were placed in both work-authorization requirements and hard disqualifiers.

**Desired:** The Job Processing Agent should preserve the restrictions. The Job Evaluation Agent should combine them with the candidate profile before determining whether they are actual blockers.

### JP-006 — Preserve complete original description

**Observed:** Initially suspected because the textarea displayed the bottom of the listing.

**Resolution:** Passed. The description was fully preserved; the textarea was scrolled down.

**Status:** Resolved in this baseline; no code defect found.

### JP-007 — Measure extraction latency

**Observed:** The user reported that the AI request appeared to take a long time.

**Limitation:** Exact elapsed time was not recorded.

**Desired:** Record request duration, provider/model metadata, success/failure state, and whether a retry occurred without storing secrets or sensitive request headers.

---

## 9. Safety and control checks

| Control | Result |
|---|---|
| API key absent from screenshots and saved evaluation | Pass |
| Original listing preserved | Pass |
| Strict structured result reached review page | Pass |
| Human could inspect and edit every field | Pass |
| Job automatically saved | No |
| Application automatically submitted | No |
| Candidate automatically declared ineligible | No |
| Placeholder salary flagged | Pass |
| Unknown work arrangement preserved rather than guessed | Pass |
| No experience years invented | Pass |

---

## 10. Evaluation verdict

**Step 3B live integration test: PASS with improvement items.**

The complete pipeline worked:

```text
raw listing
-> OpenAI structured extraction
-> strict schema and Python validation
-> evidence and warnings
-> editable human-review page
-> no automatic persistence
```

The OpenAI extractor produced a substantially better draft than the deterministic parser and preserved critical eligibility language. Human review remains necessary because employment-detail normalization, industry classification, responsibility deduplication, and blocker interpretation still need refinement.

---

## 11. Retest protocol

After any relevant change to the schema, prompt, normalization rules, model, or backend, repeat this case using the same listing and record:

1. Date of retest.
2. Commit or pull request containing the change.
3. Extractor and model version.
4. Total request duration.
5. Whether a retry occurred.
6. Field-by-field results.
7. Whether JP-001 through JP-005 and JP-007 improved, regressed, or stayed unchanged.
8. Any new unsupported claims.
9. Any new missing fields.
10. Whether all safety controls still passed.

Do not overwrite the baseline. Add a dated retest entry below so development history remains visible.

---

## 12. Retest history

| Date | Version/change | Result | Notes |
|---|---|---|---|
| 2026-07-20 | Initial Step 3B live OpenAI extraction | Pass with improvement items | First deterministic-versus-AI baseline; JP-001 through JP-005 and JP-007 opened; JP-006 confirmed passed |

---

## 13. Decision carried forward

This evaluation supports the following development direction:

1. Keep the deterministic parser as a fallback rather than the primary final extraction method.
2. Continue using structured output and local validation.
3. Keep AI extraction disabled by default until explicitly configured.
4. Preserve human review before database persistence.
5. Build Step 3C fallback and controlled failure handling.
6. Build a broader evaluation dataset before prompt tuning or any discussion of fine-tuning.
7. Use this document as the historical baseline for measuring future Job Processing improvements.
