# Final Agent Architecture

**Status:** Approved project architecture and source of truth  
**Last updated:** 2026-07-18  
**Applies to:** The completed Amiri's Job Finder application and all roadmap decisions leading to it

## 1. Purpose of this document

This document defines the final logical agent architecture for Amiri's Job Finder.

It exists to keep development aligned with the intended product instead of allowing individual features, experiments, or implementation choices to gradually change the system's purpose.

The application will contain **seven logical agents**:

1. Coordinator Agent
2. Candidate Profile Agent
3. Job Discovery Agent
4. Job Processing Agent
5. Job Evaluation Agent
6. Project Relevance and Development Agent
7. Presentation and Tracking Agent

These are logical responsibilities inside one controlled Django application. They do not need to be seven separately deployed autonomous services.

The preferred implementation is one orchestrated workflow with specialized Python services, provider interfaces, models, views, background tasks, and review gates.

## 2. Architecture change-control rule

This file is the source of truth for the agent architecture.

Any decision that adds, removes, renames, combines, splits, or materially changes an agent must update this document in the **same pull request** as the corresponding code or roadmap change.

An architecture-changing pull request must explain:

- what changed,
- why the existing architecture was insufficient,
- which responsibilities moved,
- which data contracts changed,
- whether human-approval boundaries changed,
- migration or compatibility effects,
- and whether the change affects the MVP or only a later version.

Do not treat an architecture change as complete until this document has been updated.

Small implementation refactors that preserve responsibilities and boundaries do not require an architecture revision, but they should not contradict this document.

## 3. Product-level objective

The finished application should operate as an evidence-based personal job-search system that:

1. maintains an accurate candidate profile,
2. discovers relevant opportunities,
3. converts raw listings into structured records,
4. evaluates each opportunity against the candidate,
5. explains which projects strengthen the application,
6. presents ranked and actionable recommendations,
7. and tracks the application process.

The application is not intended to become an uncontrolled auto-application bot.

It must prioritize:

- explainability,
- evidence,
- conservative eligibility handling,
- human review,
- reproducibility,
- data provenance,
- and user control.

## 4. High-level workflow

```text
Resume and preferences
        ↓
Candidate Profile Agent
        ↓
Structured candidate profile
        ↓
Job Discovery Agent
        ↓
Raw job opportunities
        ↓
Job Processing Agent
        ↓
Verified and structured job records
        ↓
Job Evaluation Agent
        ↓
Evidence-based fit analysis
        ↓
Project Relevance and Development Agent
        ↓
Project selection and portfolio recommendations
        ↓
Presentation and Tracking Agent
        ↓
Ranked recommendations, tasks, and application history

Coordinator Agent supervises and routes the entire workflow.
```

The workflow is not always strictly linear. A listing may be reprocessed after verification, a candidate profile update may trigger reevaluation, and application activity may create new tasks or reminders.

## 5. Shared architecture principles

### 5.1 One controlled application

The seven agents are specialized components inside one controlled application unless a later, documented need justifies separate deployment.

### 5.2 Structured contracts between agents

Agents should exchange validated structured data rather than free-form prose whenever possible.

Examples include:

- candidate profile records,
- job posting records,
- job requirement records,
- extraction evidence,
- eligibility findings,
- match results,
- project relevance results,
- workflow statuses,
- and application tasks.

### 5.3 AI proposes; application code enforces

Language models may interpret unstructured text and generate proposed structured output.

Python and Django remain responsible for:

- allowed fields,
- data types,
- validation,
- enums,
- database writes,
- duplicate handling,
- workflow permissions,
- scoring rules,
- and human-approval requirements.

### 5.4 Human approval for consequential changes

The system must not silently:

- overwrite candidate evidence,
- save unsupported job requirements,
- declare final eligibility without sufficient evidence,
- submit an application,
- contact an employer,
- or change important records without the user's approval.

### 5.5 Evidence and provenance

Important conclusions should preserve their source.

Examples include:

- resume section supporting a candidate skill,
- exact listing text supporting a requirement,
- employer-page evidence supporting listing status,
- rule or match evidence supporting a score,
- and project details supporting a recommendation.

### 5.6 Conservative eligibility handling

Work authorization, sponsorship, citizenship, clearance, licensing, and other blockers must be handled conservatively.

Unknown information must remain unknown rather than being guessed.

### 5.7 Graceful fallback

AI and external services should enhance the application rather than become single points of failure.

Where practical, the system should provide deterministic fallback, manual review, or a preserved unprocessed record.

## 6. Agent 1 — Coordinator Agent

### Purpose

The Coordinator Agent manages the overall workflow and determines which specialized component should act next.

It is an orchestrator, not an all-purpose reasoning agent.

### Responsibilities

- Start and sequence multi-step workflows.
- Route structured records between agents.
- Track workflow state and completion.
- Prevent required stages from being skipped.
- Handle retry, fallback, and failure states.
- Trigger reevaluation when candidate or job data changes.
- Enforce human-review gates.
- Record which agent and version produced each result.
- Avoid duplicate concurrent work on the same record.

### Primary inputs

- Workflow trigger
- Candidate profile status
- Job-processing status
- Verification status
- Evaluation status
- Project-analysis status
- User decisions
- Retry and error state

### Primary outputs

- Next workflow step
- Task state
- Agent invocation request
- Pause-for-review state
- Retry or fallback instruction
- Completed workflow record

### Must not

- Replace specialized agents' logic.
- Invent candidate or job evidence.
- Submit applications.
- Bypass human approval.
- Hide failed stages.

## 7. Agent 2 — Candidate Profile Agent

### Purpose

The Candidate Profile Agent converts the user's resume, verified background information, preferences, and portfolio into a structured reusable candidate profile.

### Responsibilities

- Read resume or CV documents.
- Extract education, degrees, minors, coursework, skills, experience, research, projects, certifications, and tools.
- Preserve evidence linking profile claims to source text.
- Distinguish explicit evidence from inferred or user-confirmed information.
- Collect career preferences and deal-breakers.
- Maintain target roles, target industries, location preferences, employment preferences, and work-authorization context.
- Present extracted information for review.
- Refresh profile data when the resume or preferences change.
- Version or timestamp profile evidence used by later evaluations.

### Primary inputs

- Resume or CV
- User-confirmed profile information
- Career preferences
- Work-authorization information
- Project portfolio
- Corrections and approvals

### Primary outputs

- Structured candidate profile
- Candidate evidence records
- Preferences and deal-breakers
- Profile warnings and unknowns
- Profile version or freshness metadata

### Must not

- Invent qualifications not supported by evidence or user confirmation.
- Rewrite the resume without explicit instruction.
- Decide final job fit.
- Change user preferences silently.

## 8. Agent 3 — Job Discovery Agent

### Purpose

The Job Discovery Agent finds relevant opportunities from approved sources and places them into a discovery inbox for processing.

### Responsibilities

- Read candidate search preferences.
- Search approved job providers, feeds, APIs, and employer career pages.
- Find internships and early-career or full-time roles consistent with user preferences.
- Collect raw listing text, source, URL, employer, and source identifiers.
- Apply broad discovery filters without pretending they are final evaluations.
- Avoid rediscovering known listings.
- Schedule or run controlled searches.
- Record discovery source and time.
- Send new listings to the Job Processing Agent.

### Primary inputs

- Target roles
- Industries
- Employment types
- Locations and work arrangements
- Seniority preferences
- Search schedule
- Approved discovery providers
- Previously discovered identifiers

### Primary outputs

- Raw opportunity record
- Listing URL and source
- Provider identifier
- Discovery timestamp
- Initial discovery status
- Processing request

### Must not

- Treat a provider excerpt as verified truth without processing.
- Decide final fit.
- Auto-apply.
- Bypass duplicate detection.
- Search unrestricted sources without an approved provider strategy.

### Manual intake in the final application

Manual paste or URL intake may remain as an optional fallback for recruiter messages, private listings, unsupported sources, and testing.

It is not intended to be the normal completed-product workflow.

## 9. Agent 4 — Job Processing Agent

### Purpose

The Job Processing Agent converts raw job listings into validated, reviewable, structured job records regardless of how the listing entered the application.

This is the agent currently under active development.

### Responsibilities

- Accept listings from discovery, manual paste, URL submission, or future imports.
- Extract title, company, location, employment type, work arrangement, salary, dates, and application link.
- Extract role family, seniority, industry, responsibilities, education, experience, certifications, required skills, and preferred skills.
- Identify work-authorization, sponsorship, citizenship, clearance, licensing, and hard-disqualifier language.
- Separate required and preferred qualifications.
- Attach short evidence quotes.
- Mark uncertainty and missing information.
- Validate AI or parser output.
- Preserve original listing text and source metadata.
- Detect possible duplicate listings.
- Record extractor, model, parser, and version information.
- Use fallback behavior when AI is unavailable or invalid.
- Present consequential extractions for human review.
- Create `JobPosting` and `JobRequirement` records only through the approved persistence workflow.

### Primary inputs

- Raw listing text
- Listing URL
- Source label and provider identifier
- Discovery metadata
- Existing job records for duplicate comparison

### Primary outputs

- Structured job data
- Structured requirement data
- Evidence
- Warnings and unknowns
- Duplicate candidates
- Provenance metadata
- Reviewable extraction draft

### Must not

- Invent missing requirements.
- Decide whether the user should apply.
- Calculate final fit independently.
- Save unsupported output without validation.
- Bypass review when review is required.
- Submit applications.

## 10. Agent 5 — Job Evaluation Agent

### Purpose

The Job Evaluation Agent compares a processed job against the structured candidate profile and user preferences.

### Responsibilities

- Calculate an explainable match score.
- Produce a fit classification.
- Compare required and preferred skills.
- Compare education and experience.
- Assess role, industry, location, work arrangement, and employment-type fit.
- Identify strengths, gaps, transferable evidence, and blockers.
- Apply conservative eligibility rules.
- Preserve direct, normalized, rule-related, semantic, missing, and blocker evidence.
- Generate an actionable recommendation and next step.
- Reevaluate jobs when relevant candidate or job data changes.
- Support calibration against human judgments.
- Version matcher and evaluation results.

### Primary inputs

- Structured candidate profile
- Candidate evidence
- Structured job and requirements
- User preferences and deal-breakers
- Matcher configuration
- Eligibility rules

### Primary outputs

- Score
- Strong, Good, Possible, Weak, or Not Eligible classification
- Category-level points
- Strengths
- Gaps
- Eligibility concerns
- Hard blockers
- Explanation and evidence
- Recommended next action

### Must not

- Use AI output as unquestioned truth.
- Hide the basis for a score.
- Allow semantic similarity to satisfy hard eligibility requirements.
- Submit or reject applications automatically.

## 11. Agent 6 — Project Relevance and Development Agent

### Purpose

The Project Relevance and Development Agent connects the user's project portfolio to each target job and recommends portfolio improvements.

### Responsibilities

- Compare existing projects with target-job requirements.
- Rank which projects are most relevant to a role.
- Explain why each selected project matters.
- Identify technical details to emphasize on the resume or in interviews.
- Identify missing evidence in the current portfolio.
- Recommend specific improvements to existing projects.
- Suggest new projects when a meaningful portfolio gap exists.
- Prioritize recommendations by expected career value and feasibility.
- Use candidate, project, and job evidence rather than generic project advice.

### Primary inputs

- Candidate profile
- Stored project portfolio
- Structured job requirements
- Evaluation gaps
- Target career direction

### Primary outputs

- Ranked relevant projects
- Project-to-requirement evidence
- Resume and interview emphasis suggestions
- Portfolio gaps
- Existing-project improvement plan
- New-project recommendations

### Must not

- Invent work the user did not complete.
- Present a proposed project as completed experience.
- Change job evaluation scores without a documented evaluation rule.
- Generate an endless project list without prioritization.

## 12. Agent 7 — Presentation and Tracking Agent

### Purpose

The Presentation and Tracking Agent turns system analysis into an actionable dashboard and maintains the application pipeline.

### Responsibilities

- Rank and present recommended jobs.
- Display concise score and evidence summaries.
- Surface listing availability and deadlines.
- Track application status.
- Track next actions, tasks, interviews, and follow-ups.
- Display stale or blocked records.
- Preserve notes and application history.
- Organize review queues.
- Present discovery, processing, evaluation, and project-analysis states clearly.
- Support reminders and notifications in later versions.

### Primary inputs

- Discovered jobs
- Processing status
- Evaluation results
- Project relevance results
- Verification state
- Deadlines
- User actions
- Application history

### Primary outputs

- Ranked dashboard
- Review inbox
- Application pipeline
- Tasks and next actions
- Deadline and stale-record alerts
- Historical status view
- User-facing summaries

### Must not

- Change underlying evidence merely for presentation.
- Hide uncertainty or blockers.
- Mark an application submitted unless the user confirms it.
- Contact employers without explicit user action.

## 13. Agent interaction contracts

### Discovery to Processing

The Job Discovery Agent provides raw source material and provenance. The Job Processing Agent owns interpretation and structuring.

### Processing to Evaluation

The Job Processing Agent provides validated job and requirement records. The Job Evaluation Agent must not evaluate unvalidated free-form provider excerpts as if they were structured truth.

### Profile to Evaluation

The Candidate Profile Agent provides versioned candidate evidence and preferences. The Job Evaluation Agent should record which profile version it used.

### Evaluation to Project Relevance

The Job Evaluation Agent provides requirements, strengths, and gaps. The Project Relevance and Development Agent converts those findings into project-specific guidance.

### All agents to Presentation

The Presentation and Tracking Agent displays results but does not redefine the underlying logic.

### Coordinator across all agents

The Coordinator Agent routes records, records state, enforces review gates, and triggers retries or reevaluation.

## 14. Final user workflow

A normal completed-product workflow should resemble:

```text
1. User maintains resume and preferences.
2. Candidate Profile Agent maintains a reviewed candidate profile.
3. Job Discovery Agent searches approved sources.
4. New listings enter a discovery inbox.
5. Job Processing Agent structures, validates, and deduplicates listings.
6. Human review occurs where required.
7. Job Evaluation Agent scores and explains fit.
8. Project Relevance and Development Agent identifies supporting projects and gaps.
9. Presentation and Tracking Agent ranks jobs and creates actionable next steps.
10. User chooses whether and how to apply.
11. Application progress is tracked.
12. Coordinator Agent manages workflow state throughout.
```

## 15. Application-status direction

The presentation layer may eventually use statuses such as:

```text
Discovered
Queued for processing
Processing
Needs review
Ready for evaluation
Recommended
Preparing application
Applied
Interviewing
Offer
Rejected
Withdrawn
Closed
```

Exact model choices may evolve without changing the seven-agent architecture, provided responsibilities remain consistent.

## 16. Current implementation mapping

### Substantially implemented

- Stage 1 job tracking and dashboard
- Structured career profile foundation
- Structured job requirements
- Explainable deterministic evaluation and calibration
- Listing reliability and verification workflows
- Presentation of score, classification, listing state, deadline, and next action

### Currently under active development

- Job Processing Agent
  - deterministic intake
  - provider interface
  - strict AI extraction schema
  - OpenAI structured-output backend
  - human review gate

### Not yet complete

- AI fallback and controlled failure workflow
- Duplicate detection
- Intake provenance and processing history
- Resume-document ingestion and evidence review
- Automated job discovery
- Project relevance and portfolio-development analysis
- Full coordinator workflow
- Expanded application tasks, reminders, and notifications
- Production deployment and operational hardening

## 17. Recommended implementation order from the current state

1. Test the current OpenAI job-extraction backend with one controlled listing.
2. Add deterministic fallback and clearly disclose which extractor was used.
3. Add duplicate detection.
4. Add processing history and provenance.
5. Build resume ingestion and candidate-evidence review.
6. Build the Job Discovery Agent and discovery inbox.
7. Strengthen evaluation versioning and actionable explanations.
8. Build the Project Relevance and Development Agent.
9. Expand application tasks, reminders, and pipeline tracking.
10. Build the Coordinator Agent over the stable component interfaces.
11. Complete production readiness, deployment, security review, and documentation.

## 18. Out-of-scope autonomy for the initial completed version

The initial completed application should not:

- submit applications automatically,
- generate or send employer communications without approval,
- operate seven unsupervised autonomous processes,
- scrape every possible website,
- make final eligibility claims without evidence,
- overwrite important user data silently,
- or make hidden matcher changes.

## 19. Decision record

### 2026-07-18 — Seven-agent architecture confirmed

The project architecture is confirmed as seven logical agents operating inside one controlled Django workflow:

1. Coordinator Agent
2. Candidate Profile Agent
3. Job Discovery Agent
4. Job Processing Agent
5. Job Evaluation Agent
6. Project Relevance and Development Agent
7. Presentation and Tracking Agent

Manual job intake is recognized as a development and fallback interface, not the primary completed-product workflow.
