from django.test import TestCase
from django.urls import reverse

from .intake_forms import JobIntakeReviewForm
from .intake_views import INTAKE_SESSION_KEY
from .models import JobPosting, JobRequirement
from .services.job_intake import extract_job_intake


SAMPLE_LISTING = """
Job Title: Embedded Software Engineer
Company: Example Medical Devices
Location: Philadelphia, PA
Employment Type: Full-time
Work arrangement: Hybrid
Application deadline: July 30, 2026

Responsibilities
- Develop embedded software for connected medical devices
- Create unit and integration tests

Required Qualifications
- Bachelor's degree in Electrical Engineering or Computer Science
- Python
- C
- Embedded systems
- Authorized to work in the United States; no sponsorship available

Preferred Qualifications
- Medical-device experience
- IEC 62304 familiarity
"""


class JobIntakeExtractionTests(TestCase):
    def test_labeled_listing_extracts_reviewable_hints(self):
        result = extract_job_intake(
            SAMPLE_LISTING,
            source_url="https://example.com/jobs/embedded-software-engineer",
            source_label="Company website",
        )

        self.assertEqual(result["job"]["title"], "Embedded Software Engineer")
        self.assertEqual(result["job"]["company"], "Example Medical Devices")
        self.assertEqual(result["job"]["location"], "Philadelphia, PA")
        self.assertEqual(
            result["job"]["employment_type"],
            JobPosting.EmploymentType.FULL_TIME,
        )
        self.assertEqual(
            result["job"]["work_arrangement"],
            JobPosting.WorkArrangement.HYBRID,
        )
        self.assertEqual(
            result["job"]["deadline_status"],
            JobPosting.DeadlineStatus.CONFIRMED,
        )
        self.assertEqual(result["job"]["application_deadline"], "2026-07-30")
        self.assertIn("Embedded systems", result["requirements"]["required_skills"])
        self.assertIn("Medical-device experience", result["requirements"]["preferred_skills"])
        self.assertIn("Bachelor", result["requirements"]["required_education"])
        self.assertIn("no sponsorship", result["requirements"]["hard_disqualifiers"])

    def test_missing_company_is_left_for_human_review(self):
        result = extract_job_intake("Biomedical Engineer\nRemote\nBuild test fixtures and analyze signals.")

        self.assertEqual(result["job"]["title"], "Biomedical Engineer")
        self.assertEqual(result["job"]["company"], "")
        self.assertTrue(any("Company" in warning for warning in result["warnings"]))


class JobIntakeWorkflowTests(TestCase):
    def _start_draft(self):
        return self.client.post(
            reverse("job_intake_start"),
            {
                "source_url": "https://example.com/jobs/embedded-software-engineer",
                "source_label": "Company website",
                "raw_text": SAMPLE_LISTING,
            },
        )

    def test_paste_step_creates_session_draft_without_creating_job(self):
        response = self._start_draft()

        self.assertRedirects(response, reverse("job_intake_review"))
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertIn(INTAKE_SESSION_KEY, self.client.session)

    def test_review_page_contains_extracted_fields(self):
        self._start_draft()

        response = self.client.get(reverse("job_intake_review"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Embedded Software Engineer")
        self.assertContains(response, "Example Medical Devices")
        self.assertContains(response, "HUMAN REVIEW GATE")
        self.assertContains(response, "No job has been created yet")

    def test_approved_review_creates_job_and_structured_requirements(self):
        self._start_draft()
        response = self.client.post(
            reverse("job_intake_review"),
            {
                "title": "Embedded Software Engineer",
                "company": "Example Medical Devices",
                "location": "Philadelphia, PA",
                "job_url": "https://example.com/jobs/embedded-software-engineer",
                "source": "Company website",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.HYBRID,
                "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
                "application_deadline": "2026-07-30",
                "next_action": "Verify listing and review requirements",
                "description": SAMPLE_LISTING,
                "role_family": "Embedded Software Engineering",
                "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
                "industry": "Medical devices",
                "required_skills": "Python\nC\nEmbedded systems",
                "preferred_skills": "IEC 62304\nMedical-device experience",
                "required_education": "Electrical Engineering\nComputer Science",
                "preferred_education": "",
                "minimum_years_experience": "0",
                "maximum_years_experience": "2",
                "responsibilities": "Develop embedded software\nCreate integration tests",
                "certifications": "IEC 62304",
                "work_authorization_requirements": "Authorized to work in the United States",
                "hard_disqualifiers": "No sponsorship available",
                "requirement_notes": "Reviewed against the original listing.",
            },
        )

        job = JobPosting.objects.get()
        requirements = JobRequirement.objects.get(job=job)
        self.assertRedirects(response, reverse("job_detail", args=[job.id]))
        self.assertEqual(job.listing_status, JobPosting.ListingStatus.UNVERIFIED)
        self.assertEqual(job.location, "Philadelphia, PA")
        self.assertEqual(requirements.industry, "Medical devices")
        self.assertIn("Embedded systems", requirements.required_skills)
        self.assertNotIn(INTAKE_SESSION_KEY, self.client.session)

    def test_discard_draft_creates_no_job(self):
        self._start_draft()

        response = self.client.post(reverse("job_intake_clear"))

        self.assertRedirects(response, reverse("job_intake_start"))
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertNotIn(INTAKE_SESSION_KEY, self.client.session)

    def test_review_route_requires_an_active_draft(self):
        response = self.client.get(reverse("job_intake_review"))

        self.assertRedirects(response, reverse("job_intake_start"))


class JobIntakeFormTests(TestCase):
    def test_confirmed_deadline_requires_date(self):
        form = JobIntakeReviewForm(
            data={
                "title": "Test Engineer",
                "company": "Example Medical",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.ONSITE,
                "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
                "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("application_deadline", form.errors)


class DashboardLocationPlacementTests(TestCase):
    def test_location_is_presented_below_company_before_match_score(self):
        job = JobPosting.objects.create(
            title="Biomedical Engineer",
            company="Example Medical",
            location="Boston, MA",
        )

        response = self.client.get(reverse("job_list"))
        content = response.content.decode()

        self.assertContains(response, "dashboard_location.css")
        self.assertLess(content.index("Example Medical"), content.index("Boston, MA"))
        self.assertLess(content.index("Boston, MA"), content.index("dashboard-match-strip"))
        self.assertContains(response, reverse("job_detail", args=[job.id]))
