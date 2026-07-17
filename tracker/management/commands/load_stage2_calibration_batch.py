from django.core.management.base import BaseCommand

from tracker.models import JobPosting, JobRequirement


SOURCE_NAME = "Stage 2 Calibration Batch 01"
RESEARCHED_ON = "2026-07-16"


CALIBRATION_BATCH = (
    {
        "job": {
            "title": "Product Safety Engineer",
            "company": "Stryker",
            "location": "Portage or Grand Rapids, MI",
            "job_url": (
                "https://careers.stryker.com/product-safety-engineer/"
                "job/ACEC20C0BD698F7CD7A4CB633D697BE3"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "salary_text": "$69,500–$110,900",
            "description": (
                "Early-career medical-device product-safety role focused on electrical "
                "testing, bench work, safety planning, engineering specifications, and "
                "regulated design documentation."
            ),
        },
        "requirements": {
            "role_family": "Product Safety Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Medical devices",
            "required_skills": (
                "Electrical system testing\n"
                "Circuit analysis\n"
                "Bench testing and prototyping\n"
                "Engineering specifications\n"
                "Technical documentation"
            ),
            "preferred_skills": (
                "CAD, CAE, or simulation tools\n"
                "Statistical analysis\n"
                "Medical electrical equipment safety\n"
                "Electromagnetic compatibility testing"
            ),
            "required_education": "Electrical Engineering or related discipline",
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Create product-safety test plans\n"
                "Conduct circuit and electrical-system testing\n"
                "Support prototyping and bench evaluation\n"
                "Maintain design-history documentation"
            ),
            "certifications": (
                "IEC 60601-1\n"
                "IEC 60601-1-2\n"
                "IEC 60529\n"
                "IEC 61000 series\n"
                "IEC 61010-1\n"
                "ISO 17025"
            ),
            "work_authorization_requirements": (
                "Sponsorship support is not stated in the posting; verify before applying."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Priority-role calibration candidate. The posting explicitly accepts "
                "a bachelor's degree in electrical engineering with zero years of work experience."
            ),
        },
    },
    {
        "job": {
            "title": "Engineering Intern",
            "company": "BD",
            "location": "Canaan, CT",
            "job_url": "https://jobs.bd.com/en/job/canaan/engineering-intern/159/97591406352",
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.INTERNSHIP,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "",
            "description": (
                "Medical-device manufacturing internship supporting production equipment, "
                "troubleshooting, CAD work, validation, and short engineering projects."
            ),
        },
        "requirements": {
            "role_family": "Manufacturing and Process Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.INTERNSHIP,
            "industry": "Medical devices",
            "required_skills": (
                "Production equipment troubleshooting\n"
                "Engineering problem solving\n"
                "Technical documentation\n"
                "Team collaboration"
            ),
            "preferred_skills": (
                "Solid modeling\n"
                "Equipment improvement\n"
                "Validation principles\n"
                "Manufacturing support"
            ),
            "required_education": "High school diploma or GED",
            "preferred_education": "Engineering degree in progress",
            "minimum_years_experience": 0,
            "maximum_years_experience": 1,
            "responsibilities": (
                "Support engineering and operations projects\n"
                "Improve production equipment\n"
                "Assist with design and solid modeling\n"
                "Apply validation methods under supervision"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "Work-authorization and internship-eligibility terms are not stated; verify directly."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Priority internship calibration candidate for hands-on manufacturing, "
                "validation, and equipment experience."
            ),
        },
    },
    {
        "job": {
            "title": "BD Quality Engineering Development Program Associate",
            "company": "BD",
            "location": "Multiple U.S. locations",
            "job_url": (
                "https://jobs.bd.com/en/job/franklin-lakes/"
                "bd-quality-engineering-development-program-associate/159/95583040176"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "",
            "description": (
                "Three-year early-career quality rotation across new product development, "
                "manufacturing quality, post-market quality, and quality systems."
            ),
        },
        "requirements": {
            "role_family": "Quality Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Medical devices",
            "required_skills": (
                "Technical aptitude\n"
                "Written communication\n"
                "Organization and time management\n"
                "Learning agility\n"
                "Relocation flexibility"
            ),
            "preferred_skills": (
                "Quality engineering internship\n"
                "Manufacturing internship\n"
                "Engineering internship"
            ),
            "required_education": (
                "Biomedical Engineering\n"
                "Mechanical Engineering\n"
                "Life Sciences\n"
                "Quality Sciences\n"
                "Related major"
            ),
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Rotate through three quality functions\n"
                "Support product design and manufacturing\n"
                "Collaborate with R&D and regulatory teams\n"
                "Relocate among U.S. sites"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "Must be authorized to work for any U.S. employer without restriction; "
                "the employer states that sponsorship is unavailable."
            ),
            "hard_disqualifiers": (
                "Employer states it cannot sponsor or take over employment visa sponsorship."
            ),
            "requirement_notes": (
                "Technically strong early-career fit, but intentionally included to test "
                "work-authorization blocker handling."
            ),
        },
    },
    {
        "job": {
            "title": "Manufacturing Engineer",
            "company": "Intuitive",
            "location": "Blacksburg, VA",
            "job_url": (
                "https://careers.intuitive.com/en/jobs/744000137748379/"
                "JOB215676/manufacturing-engineer/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "$87,500–$139,200 depending on region",
            "description": (
                "Manufacturing engineering role for robotic-surgery sensing platforms, "
                "covering fixtures, process validation, PFMEA, line support, and failure analysis."
            ),
        },
        "requirements": {
            "role_family": "Manufacturing Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "Manufacturing process development\n"
                "Technical troubleshooting\n"
                "Fixture and equipment design\n"
                "PFMEA\n"
                "IQ/OQ/PQ\n"
                "Process validation"
            ),
            "preferred_skills": (
                "SolidWorks\n"
                "Programming\n"
                "ISO 13485\n"
                "Lean manufacturing\n"
                "Six Sigma"
            ),
            "required_education": (
                "Mechanical Engineering\n"
                "Mechatronics\n"
                "Electrical Engineering\n"
                "Industrial Systems Engineering"
            ),
            "minimum_years_experience": 2,
            "responsibilities": (
                "Develop and improve manufacturing lines\n"
                "Qualify fixtures and equipment\n"
                "Execute process validation\n"
                "Support failure analysis and production issues"
            ),
            "certifications": "ISO 13485 preferred\nISO 9001 preferred",
            "work_authorization_requirements": (
                "The posting notes that export-control review or a technology-control plan may apply."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Adjacent early-career role. The posting accepts an advanced degree as an "
                "alternative to two years of experience."
            ),
        },
    },
    {
        "job": {
            "title": "Engineering Technician 1",
            "company": "Intuitive",
            "location": "Peachtree Corners, GA",
            "job_url": (
                "https://careers.intuitive.com/en/jobs/744000130626199/"
                "JOB215499/engineering-technician-1/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "$23–$37 per hour depending on region",
            "description": (
                "Hands-on robotic-equipment role involving fixture qualification, assembly, "
                "soldering, troubleshooting, engineering tests, and controlled documentation."
            ),
        },
        "requirements": {
            "role_family": "Engineering Technician and Test Fixture Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "Electromechanical assembly\n"
                "Troubleshooting\n"
                "Fixture qualification\n"
                "Soldering\n"
                "Root cause analysis\n"
                "Technical documentation"
            ),
            "preferred_skills": (
                "PLM systems\n"
                "SAP\n"
                "Engineering change orders\n"
                "GD&T\n"
                "Medical-device quality systems"
            ),
            "required_education": (
                "Mechanical Engineering\n"
                "Electrical Engineering\n"
                "Mechatronics Engineering"
            ),
            "minimum_years_experience": 3,
            "responsibilities": (
                "Qualify and service functional test fixtures\n"
                "Assemble and rework robotic equipment\n"
                "Assist engineering tests and data collection\n"
                "Support manufacturing and design engineers"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "The posting notes that export-control review or a technology-control plan may apply."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Adjacent hands-on role. Included to test whether transferable lab and "
                "electrical experience offsets the stated experience expectation."
            ),
        },
    },
    {
        "job": {
            "title": "Manufacturing Engineer",
            "company": "Intuitive",
            "location": "Sunnyvale, CA",
            "job_url": (
                "https://careers.intuitive.com/en/jobs/744000130292504/"
                "JOB214727/manufacturing-engineer/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "",
            "description": (
                "Medical-device manufacturing role supporting a high-volume line, PFMEA, "
                "fixtures, process qualification, V&V, quality systems, and supplier issues."
            ),
        },
        "requirements": {
            "role_family": "Manufacturing Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "High-volume manufacturing\n"
                "Statistical process control\n"
                "DFM assessment\n"
                "BOM development\n"
                "PFMEA\n"
                "IQ/OQ/PQ\n"
                "ISO 13485"
            ),
            "preferred_skills": "SolidWorks\nSterilized medical-device manufacturing",
            "required_education": (
                "Mechanical Engineering\n"
                "Manufacturing Engineering\n"
                "Mechatronics Engineering"
            ),
            "minimum_years_experience": 2,
            "responsibilities": (
                "Support manufacturing-line issues\n"
                "Design and document assembly fixtures\n"
                "Perform process qualification\n"
                "Support V&V and quality-system compliance"
            ),
            "certifications": "ISO 13485",
            "work_authorization_requirements": (
                "The posting notes that export-control review or a technology-control plan may apply."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Adjacent role with meaningful vocabulary overlap but a mechanical and "
                "manufacturing emphasis that may reduce priority alignment."
            ),
        },
    },
    {
        "job": {
            "title": "Associate Territory Manager - Charlotte",
            "company": "BD",
            "location": "Charlotte, NC",
            "job_url": (
                "https://jobs.bd.com/en/job/charlotte/"
                "associate-territory-manager-charlotte-nc/159/95677431920"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "",
            "description": (
                "Field-based medical-device sales and clinical-support role providing product "
                "training, surgical-case support, account development, and physician education."
            ),
        },
        "requirements": {
            "role_family": "Clinical Sales and Field Applications",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Medical devices",
            "required_skills": (
                "Sales\n"
                "Clinical training\n"
                "Customer support\n"
                "Presentation skills\n"
                "Organization\n"
                "Extensive travel"
            ),
            "preferred_skills": (
                "Medical-device product knowledge\n"
                "Operating-room support\n"
                "Healthcare relationship management"
            ),
            "required_education": "Bachelor's degree",
            "minimum_years_experience": 1,
            "responsibilities": (
                "Support clinical cases and customer training\n"
                "Educate hospital staff\n"
                "Develop territory accounts\n"
                "Travel throughout the assigned region"
            ),
            "certifications": "Valid driver's license",
            "work_authorization_requirements": (
                "Sponsorship support is not stated in the posting; verify before applying."
            ),
            "hard_disqualifiers": (
                "Approximately 80% travel is required.\n"
                "Willingness to relocate for a future territory-manager opening is required."
            ),
            "requirement_notes": (
                "Deliberate adjacent-opportunity candidate. Technical healthcare knowledge is "
                "relevant, but the role is primarily commercial rather than engineering."
            ),
        },
    },
    {
        "job": {
            "title": "Quality Engineer I",
            "company": "Philips",
            "location": "Plymouth, MN",
            "job_url": (
                "https://philips.wd3.myworkdayjobs.com/jobs-and-careers/"
                "job/Plymouth-Minnesota-United-States/Quality-Engineer-I_578778-1"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "$69,500–$92,500",
            "description": (
                "Factory quality-engineering role covering nonconformances, CAPA, PFMEA, "
                "design transfer, supplier quality, data analysis, and new-product introduction."
            ),
        },
        "requirements": {
            "role_family": "Quality Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Health technology and medical devices",
            "required_skills": (
                "Nonconformance management\n"
                "Corrective and preventive action\n"
                "PFMEA\n"
                "Manufacturing quality\n"
                "Data analysis\n"
                "Technical documentation"
            ),
            "preferred_skills": (
                "Process engineering\n"
                "Design transfer\n"
                "Supplier quality engineering\n"
                "New product introduction"
            ),
            "required_education": (
                "Mechanical Engineering\n"
                "Electronics Engineering\n"
                "Science or equivalent"
            ),
            "minimum_years_experience": 4,
            "responsibilities": (
                "Review and disposition nonconformances\n"
                "Support CAPA and PFMEA updates\n"
                "Monitor manufacturing-quality performance\n"
                "Support NPI and product transfers"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "The employer states that U.S. work authorization is required and "
                "candidates needing present or future visa sponsorship will not be considered."
            ),
            "hard_disqualifiers": (
                "Employer states it will not consider candidates requiring visa sponsorship now or later."
            ),
            "requirement_notes": (
                "Included to test both an experience gap and a clearly stated sponsorship blocker."
            ),
        },
    },
    {
        "job": {
            "title": "Engineering Intern - Documentation",
            "company": "BD",
            "location": "Sumter, SC",
            "job_url": (
                "https://jobs.bd.com/en/job/sumter/"
                "engineering-intern-documentation/159/94224739104"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.INTERNSHIP,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "",
            "description": (
                "Engineering-documentation internship focused on drawings, CAD updates, "
                "document control, dimensional verification, and file-quality checks."
            ),
        },
        "requirements": {
            "role_family": "Engineering Documentation and CAD",
            "seniority_level": JobRequirement.SeniorityLevel.INTERNSHIP,
            "industry": "Medical devices",
            "required_skills": (
                "Technical drawings\n"
                "Document control\n"
                "Dimensional verification\n"
                "File organization\n"
                "Quality checks"
            ),
            "preferred_skills": "SolidWorks\nAutoCAD",
            "required_education": "",
            "minimum_years_experience": 0,
            "maximum_years_experience": 1,
            "responsibilities": (
                "Digitize engineering documents\n"
                "Update CAD drawings\n"
                "Verify dimensions and specifications\n"
                "Maintain document-management records"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "Work-authorization and internship-eligibility terms are not stated; verify directly."
            ),
            "hard_disqualifiers": "",
            "requirement_notes": (
                "Useful calibration example for a technically relevant internship that may "
                "be narrower than the user's main product-development goals."
            ),
        },
    },
    {
        "job": {
            "title": "Staff Embedded Software & Controls Engineer",
            "company": "Stryker",
            "location": "Flower Mound, TX",
            "job_url": (
                "https://careers.stryker.com/staff-embedded-software-controls-engineer/"
                "job/1A11A3FBEC5903C0FBE89BA51D30EAA2"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "salary_text": "$112,900–$188,100",
            "description": (
                "Mid-level embedded software and controls role for complex electromechanical "
                "medical devices, including firmware, RTOS, control algorithms, and V&V."
            ),
        },
        "requirements": {
            "role_family": "Embedded Software and Controls Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.MID_LEVEL,
            "industry": "Medical devices",
            "required_skills": (
                "Embedded C or C++\n"
                "Bare-metal or RTOS development\n"
                "Firmware development\n"
                "Real-time control systems\n"
                "Hardware-software debugging\n"
                "Verification and validation"
            ),
            "preferred_skills": (
                "PID control\n"
                "State machines\n"
                "Motor control\n"
                "Sensor integration\n"
                "Regulated product development"
            ),
            "required_education": (
                "Electrical Engineering\n"
                "Computer Engineering\n"
                "Computer Science\n"
                "Software Engineering"
            ),
            "minimum_years_experience": 4,
            "responsibilities": (
                "Develop embedded software and control algorithms\n"
                "Integrate firmware with electromechanical systems\n"
                "Debug system-level issues\n"
                "Maintain requirements and verification documentation"
            ),
            "certifications": "",
            "work_authorization_requirements": (
                "Sponsorship support is not stated in the posting; verify before applying."
            ),
            "hard_disqualifiers": "Four or more years of embedded-software development experience is required.",
            "requirement_notes": (
                "Deliberate stretch role used to test whether strong vocabulary overlap is "
                "properly outweighed by the experience requirement."
            ),
        },
    },
)


class Command(BaseCommand):
    help = (
        "Load ten curated real-world postings for Stage 2 human calibration. "
        "The command never creates human calibration judgments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the curated jobs without changing the database.",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "Refresh jobs previously created by this batch. Records imported from "
                "another source are never overwritten."
            ),
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            self.stdout.write(f"{SOURCE_NAME} ({RESEARCHED_ON})")
            for index, entry in enumerate(CALIBRATION_BATCH, start=1):
                job_data = entry["job"]
                self.stdout.write(
                    f"{index:02d}. {job_data['title']} — {job_data['company']}"
                )
            self.stdout.write("Dry run complete. No database records were changed.")
            return

        created_count = 0
        refreshed_count = 0
        unchanged_count = 0
        skipped_count = 0

        for entry in CALIBRATION_BATCH:
            job_data = entry["job"].copy()
            requirements_data = entry["requirements"].copy()
            job_url = job_data.pop("job_url")
            job_data.update(
                {
                    "job_url": job_url,
                    "source": SOURCE_NAME,
                    "next_action": "Review posting and save an independent calibration",
                    "notes": (
                        f"Curated for {SOURCE_NAME} on {RESEARCHED_ON}. "
                        "Verify that the external posting is still open before applying. "
                        "Human calibration is intentionally blank."
                    ),
                }
            )

            job, created = JobPosting.objects.get_or_create(
                job_url=job_url,
                defaults=job_data,
            )
            managed_by_batch = created or job.source == SOURCE_NAME

            if created:
                created_count += 1
            elif not managed_by_batch:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped existing non-batch record: {job.title} at {job.company}"
                    )
                )
                continue
            elif options["refresh"]:
                for field_name, value in job_data.items():
                    setattr(job, field_name, value)
                job.save()
                refreshed_count += 1
            else:
                unchanged_count += 1

            requirements, requirements_created = JobRequirement.objects.get_or_create(job=job)
            if created or requirements_created or options["refresh"]:
                for field_name, value in requirements_data.items():
                    setattr(requirements, field_name, value)
                requirements.full_clean()
                requirements.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Calibration batch ready: "
                f"{created_count} created, {refreshed_count} refreshed, "
                f"{unchanged_count} unchanged, {skipped_count} skipped."
            )
        )
        self.stdout.write(
            "Open the dashboard, filter HUMAN REVIEW to NOT YET REVIEWED, and sort by "
            "HIGHEST MATCH SCORE. Record your judgment before reading the agreement label."
        )
