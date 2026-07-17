# Stage 2 Calibration Batch 01

Research date: **2026-07-16**

This batch contains ten real medical-device and adjacent-role postings selected to test the current matcher across a useful range:

- direct early-career engineering opportunities
- internships and hands-on technical roles
- adjacent commercial or manufacturing roles
- explicit work-authorization blockers
- stretch roles with meaningful vocabulary overlap but excessive experience requirements

The postings are deliberately varied. Do not assume the first computed score is correct.

## Load the batch

After Pull Request #8 is merged and migrations are applied:

```bash
python manage.py load_stage2_calibration_batch --dry-run
python manage.py load_stage2_calibration_batch
```

The command is idempotent. Running it again will not create duplicates.

To restore the curated fields on records originally created by this batch:

```bash
python manage.py load_stage2_calibration_batch --refresh
```

The refresh option never overwrites an existing job that was created from another source.

## Included postings

| # | Company | Role | Location | Why it is useful for calibration |
|---:|---|---|---|---|
| 1 | Stryker | Product Safety Engineer | Portage or Grand Rapids, MI | Direct early-career electrical and medical-device safety role |
| 2 | BD | Engineering Intern | Canaan, CT | Internship involving equipment, troubleshooting, CAD, and validation |
| 3 | BD | Quality Engineering Development Program Associate | Multiple U.S. sites | Strong technical fit with an explicit no-sponsorship condition |
| 4 | Intuitive | Manufacturing Engineer | Blacksburg, VA | Early-career manufacturing and validation role accepting an advanced degree |
| 5 | Intuitive | Engineering Technician 1 | Peachtree Corners, GA | Hands-on assembly, fixtures, soldering, testing, and documentation |
| 6 | Intuitive | Manufacturing Engineer | Sunnyvale, CA | Relevant medical-device work with stronger mechanical/manufacturing emphasis |
| 7 | BD | Associate Territory Manager | Charlotte, NC | Deliberate adjacent medical-device commercial opportunity |
| 8 | Philips | Quality Engineer I | Plymouth, MN | Quality vocabulary overlap plus experience and sponsorship blockers |
| 9 | BD | Engineering Intern - Documentation | Sumter, SC | Narrower technical internship centered on CAD and document control |
| 10 | Stryker | Staff Embedded Software & Controls Engineer | Flower Mound, TX | Stretch role testing whether experience requirements outweigh skill overlap |

## Review process

For each posting:

1. Open the original posting and confirm that it is still active.
2. Read the posting before relying on the match score.
3. Record your independent human fit judgment.
4. Select whether the role is priority, adjacent, outside priority, or uncertain.
5. Write one or two sentences explaining the judgment.
6. Save the calibration and then compare it with the matcher.

Recommended dashboard settings:

- **Human review:** Not yet reviewed
- **Sort:** Highest match score

Work through all ten jobs before changing the scoring weights. A disagreement is useful evidence; it is not automatically a failure by either the matcher or the human reviewer.

## Important limits

- The importer stores concise, structured summaries rather than complete copies of job descriptions.
- Job pages can close or change after the research date.
- No human calibration judgment is preloaded.
- Importing a posting is not a recommendation to apply.
- Work-authorization and export-control language must be reviewed carefully for each role.
