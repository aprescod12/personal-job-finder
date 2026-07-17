from tracker.models import JobPosting, JobRequirement


CALIBRATION_SOURCE = "Stage 2 Calibration Batch 01"
VALIDATION_SOURCE = "Stage 2 Validation Batch 01"
RESEARCHED_ON = "2026-07-17"


VALIDATION_BATCH = (
    {
        "job": {
            "title": "Edison Engineering Development Program",
            "company": "GE HealthCare",
            "location": "United States program locations",
            "job_url": "https://careers.gehealthcare.com/global/en/edison-engineering",
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "description": (
                "Two-year healthcare engineering rotation spanning product and software "
                "development, technical coursework, and regulated medical-device work."
            ),
        },
        "requirements": {
            "role_family": "Medical Device Product and Software Development Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Healthcare technology and medical devices",
            "required_skills": (
                "Engineering problem solving\nProduct development\nTechnical teamwork\n"
                "Medical device design and engineering"
            ),
            "preferred_skills": "Software development\nLeadership\nTechnical presentations",
            "required_education": (
                "Electrical Engineering\nBiomedical Engineering\nComputer Science\n"
                "Software Development\nRelated engineering discipline"
            ),
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Complete engineering rotations\nDevelop healthcare products or software\n"
                "Work in a regulated industry\nComplete advanced technical training"
            ),
            "work_authorization_requirements": (
                "Program-specific U.S. work-authorization terms must be verified on the live opening."
            ),
            "requirement_notes": "Holdout example: direct early-career MedTech development pathway.",
        },
    },
    {
        "job": {
            "title": "Quality & Regulatory Leadership Program",
            "company": "GE HealthCare",
            "location": "United States program locations",
            "job_url": "https://careers.gehealthcare.com/global/en/quality-%26-regulatory",
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "description": (
                "Twenty-four-month quality and regulatory rotation covering product quality, "
                "medical-device regulations, manufacturing processes, and patient safety."
            ),
        },
        "requirements": {
            "role_family": "Quality and Regulatory Engineering Leadership",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Healthcare technology and medical devices",
            "required_skills": (
                "Quality management systems\nRegulatory affairs\nAnalytical problem solving\n"
                "Medical device standards and regulations"
            ),
            "preferred_skills": "Manufacturing quality\nPatient safety\nBusiness acumen",
            "required_education": "Relevant master's or graduate degree",
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Complete quality and regulatory rotations\nSupport product compliance\n"
                "Build medical-device standards knowledge\nDevelop leadership capability"
            ),
            "work_authorization_requirements": (
                "Program-specific U.S. work-authorization terms must be verified on the live opening."
            ),
            "requirement_notes": "Holdout example: quality/regulatory entry path supported by graduate study.",
        },
    },
    {
        "job": {
            "title": "Software Engineer, Cloud",
            "company": "Stryker",
            "location": "Remote-US or selected U.S. offices",
            "job_url": (
                "https://careers.stryker.com/software-engineer-cloud/"
                "job/83CA700C1BCCA92DF6B18D56038EE714"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.REMOTE,
            "salary_text": "Verify current range on live posting",
            "description": (
                "Backend cloud engineering for digital-health and medical-device-classified "
                "applications, APIs, distributed systems, and clinical data pipelines."
            ),
        },
        "requirements": {
            "role_family": "Cloud Software Engineering for Digital Health",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Medical devices and digital health",
            "required_skills": (
                "Python, C#, or Java\nBackend services and APIs\nCloud platforms\n"
                "Distributed systems troubleshooting\nReact or Angular"
            ),
            "preferred_skills": (
                "Docker\nOAuth or SSL/TLS\nMedical device software\nRegulated environments"
            ),
            "required_education": "Computer Science\nSoftware Engineering\nRelated discipline",
            "minimum_years_experience": 2,
            "responsibilities": (
                "Build cloud APIs and backend services\nDevelop clinical data pipelines\n"
                "Support secure scalable systems\nContribute to regulated quality processes"
            ),
            "work_authorization_requirements": "Verify U.S. sponsorship availability directly.",
            "requirement_notes": "Holdout example: desirable MedTech software path with a two-year experience ask.",
        },
    },
    {
        "job": {
            "title": "Hardware Test Engineer 2",
            "company": "Intuitive",
            "location": "Sunnyvale, CA",
            "job_url": (
                "https://careers.intuitive.com/jp/jobs/744000123915361/"
                "JOB214296/hardware-test-engineer-2/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "salary_text": "$93,800–$149,300 depending on region and level",
            "description": (
                "New-product verification role creating V&V plans, protocols, test methods, "
                "fixtures, acceptance criteria, and reports for robotic surgical products."
            ),
        },
        "requirements": {
            "role_family": "Hardware Test and Verification Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "Verification and validation planning\nTest protocol development\n"
                "Electromechanical test equipment\nAcceptance criteria\nTechnical reporting"
            ),
            "preferred_skills": "MATLAB\nPython\nArduino\nSolidWorks\nOscilloscopes",
            "required_education": "Mechanical Engineering\nBiomedical Engineering\nRelated discipline",
            "minimum_years_experience": 2,
            "responsibilities": (
                "Create V&V plans and protocols\nDevelop test methods\nTrain technicians\n"
                "Support new product quality"
            ),
            "work_authorization_requirements": "Verify export-control and sponsorship terms directly.",
            "requirement_notes": "Holdout example: strong adjacent verification role with a modest experience gap.",
        },
    },
    {
        "job": {
            "title": "Mechanical Design Engineer - Mechatronics",
            "company": "Intuitive",
            "location": "Blacksburg, VA",
            "job_url": (
                "https://careers.intuitive.com/de/jobs/744000137994659/"
                "JOB216936/mechanical-design-engineer-mechatronics/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "description": (
                "Designs mechatronic manufacturing equipment for surgical robots using CAD, "
                "sensing, actuation, test fixtures, design controls, and reliability methods."
            ),
        },
        "requirements": {
            "role_family": "Mechanical and Mechatronics Design Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.MID_LEVEL,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "Mechanical design\nMechatronics\nCAD\nKinematics and actuation\n"
                "Test fixture design\nDesign controls"
            ),
            "preferred_skills": "Sensing systems\nReliability engineering\nManufacturing equipment",
            "required_education": "Mechanical Engineering",
            "minimum_years_experience": 5,
            "responsibilities": (
                "Design manufacturing equipment\nCreate mechatronic mechanisms\n"
                "Develop fixtures and tests\nSupport quality and reliability"
            ),
            "work_authorization_requirements": "Verify export-control and sponsorship terms directly.",
            "hard_disqualifiers": "Five years of directly relevant mechanical-design experience is requested.",
            "requirement_notes": "Holdout example: relevant industry but deliberately overqualified and mechanically specialized.",
        },
    },
    {
        "job": {
            "title": "Field Service/Support Engineer 2",
            "company": "Intuitive",
            "location": "Allentown, PA region",
            "job_url": (
                "https://careers.intuitive.com/en/jobs/744000097313286/"
                "JOB210453/field-servicesupport-engineer-2/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "description": (
                "Hospital field-service role installing, maintaining, troubleshooting, and "
                "repairing robotic surgical systems while training customers."
            ),
        },
        "requirements": {
            "role_family": "Medical Device Field Service Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Robotic surgical medical devices",
            "required_skills": (
                "Electromechanical troubleshooting\nEquipment installation and repair\n"
                "Customer training\nTechnical documentation\nIndependent field work"
            ),
            "preferred_skills": "Hospital or operating-room support\nRobotics service",
            "required_education": "Technical or engineering education",
            "minimum_years_experience": 1,
            "maximum_years_experience": 3,
            "responsibilities": (
                "Install and maintain surgical systems\nDiagnose equipment failures\n"
                "Train clinical customers\nTravel throughout the service region"
            ),
            "certifications": "Valid driver's license",
            "work_authorization_requirements": "Verify U.S. work authorization directly.",
            "hard_disqualifiers": "Up to approximately 75% travel may be required.",
            "requirement_notes": "Holdout example: credible industry-entry route with substantial travel.",
        },
    },
    {
        "job": {
            "title": "Design Quality Engineer",
            "company": "BD",
            "location": "Warwick, RI",
            "job_url": (
                "https://jobs.bd.com/en/job/warwick/"
                "advanced-manufacturing-quality-engineer/159/90795938704"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.ONSITE,
            "description": (
                "Design-quality work for implantable medical devices covering design controls, "
                "V&V, risk management, CAPA, biocompatibility, and quality-system compliance."
            ),
        },
        "requirements": {
            "role_family": "Medical Device Design Quality Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Implantable medical devices",
            "required_skills": (
                "Design controls\nVerification and validation\nRisk management\nCAPA\n"
                "Quality systems\nTechnical documentation"
            ),
            "preferred_skills": "ISO 10993\nISO 13485\nISO 14971\nFDA quality system regulation",
            "required_education": "Engineering or scientific bachelor's or master's degree",
            "minimum_years_experience": 1,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Support design teams\nReview V&V evidence\nMaintain risk files\n"
                "Support CAPA and product-quality decisions"
            ),
            "certifications": "ISO 13485\nISO 14971\nFDA design controls",
            "work_authorization_requirements": "Verify sponsorship availability directly.",
            "requirement_notes": "Holdout example: adjacent design-quality path with highly relevant regulated-development work.",
        },
    },
    {
        "job": {
            "title": "Software Engineer",
            "company": "BD",
            "location": "San Diego, CA",
            "job_url": (
                "https://jobs.bd.com/en/job/san-diego/"
                "software-engineer/159/91194748720"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "description": (
                "Enterprise healthcare software development supporting the Pyxis medication-"
                "management ecosystem using C#/.NET and software-engineering practices."
            ),
        },
        "requirements": {
            "role_family": "Healthcare Software Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Healthcare technology and medication management",
            "required_skills": (
                "C# and .NET\nObject-oriented software development\nSoftware testing\n"
                "Debugging\nEnterprise application development"
            ),
            "preferred_skills": "Healthcare software\nAgile development\nSQL",
            "required_education": "Computer Science\nSoftware Engineering\nRelated technical degree",
            "minimum_years_experience": 1,
            "maximum_years_experience": 3,
            "responsibilities": (
                "Develop healthcare software\nWrite maintainable tested code\n"
                "Troubleshoot application issues\nCollaborate with product teams"
            ),
            "work_authorization_requirements": "Verify sponsorship availability directly.",
            "requirement_notes": "Holdout example: healthcare software path with a language-stack gap.",
        },
    },
    {
        "job": {
            "title": "Manufacturing Engineer I",
            "company": "Boston Scientific",
            "location": "Maple Grove, MN",
            "job_url": (
                "https://jobs.bostonscientific.com/job/Maple-Grove-"
                "Manufacturing-Engineer-I-MN-55311/1361379900/"
            ),
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "description": (
                "Entry manufacturing-engineering work involving regulated production support, "
                "troubleshooting, root-cause analysis, quality improvements, and process data."
            ),
        },
        "requirements": {
            "role_family": "Medical Device Manufacturing Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Medical devices",
            "required_skills": (
                "Manufacturing troubleshooting\nRoot cause analysis\nProcess improvement\n"
                "Quality systems\nEngineering documentation"
            ),
            "preferred_skills": "Minitab\nSQL\nSolidWorks\nRegulated manufacturing",
            "required_education": "Engineering bachelor's degree",
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Support manufacturing processes\nInvestigate production issues\n"
                "Analyze process data\nImplement quality improvements"
            ),
            "work_authorization_requirements": (
                "The posting states that employment-visa sponsorship is not available."
            ),
            "hard_disqualifiers": "Employer states that it will not sponsor an employment visa for this position.",
            "requirement_notes": "Holdout example: strong technical industry fit with an explicit authorization condition.",
        },
    },
    {
        "job": {
            "title": "Software Engineer I - Full Time",
            "company": "Cisco",
            "location": "Multiple U.S. locations or remote",
            "job_url": "https://jobs.cisco.com/jobs/SearchJobs/Software%2BEngineering",
            "status": JobPosting.Status.SAVED,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "description": (
                "General early-career software-engineering opportunity outside healthcare, "
                "included to test whether industry-first prioritization remains intact."
            ),
        },
        "requirements": {
            "role_family": "General Software Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            "industry": "Enterprise networking and technology",
            "required_skills": (
                "Software development\nProgramming\nDebugging\nData structures\n"
                "Collaborative engineering"
            ),
            "preferred_skills": "Python\nC or C++\nCloud systems\nNetworking",
            "required_education": "Computer Science\nComputer Engineering\nRelated technical degree",
            "minimum_years_experience": 0,
            "maximum_years_experience": 2,
            "responsibilities": (
                "Develop production software\nTest and debug systems\n"
                "Collaborate with engineering teams\nMaintain technical documentation"
            ),
            "work_authorization_requirements": "Verify authorization terms for the specific live opening.",
            "requirement_notes": "Holdout example: valid general-software option outside the preferred MedTech industry.",
        },
    },
)


def is_validation_job(job):
    return bool(job and job.source == VALIDATION_SOURCE)


def is_blind_validation(job, calibration=None):
    return is_validation_job(job) and calibration is None
