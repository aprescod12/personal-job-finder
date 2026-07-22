from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from tracker.intake_views import INTAKE_SESSION_KEY
from tracker.models import JobPosting, JobRequirement

from .models import JobExtractionRun
from .services import (
    DUPLICATE_REASON_EXACT_URL,
    DUPLICATE_REASON_SAME_ROLE,
    analyze_job_duplicates,
    listing_text_sha256,
    normalize_source_url,
)


SAMPLE_LISTING = """
Job Title: Embedded Software Engineer
Company: Example Medical Devices
Location: Philadelphia, PA
Employment Type: Full-time
Work arrangement: Hybrid

Responsibilities
- Develop embedded software for connected medical devices
- Create unit and integration tests

Required Qualifications
- Bachelor's degree in Electrical Engineering or Computer Science
- Python
- C
- Embedded systems
"""

SOURCE_URL = "https://example.com/jobs/embedded-software-engineer"


def review_payload(*, confirm_duplicate=False):
    payload = {
        "title": "Embedded Software Engineer",
        "company": "Example Medical Devices",
        "location": "Philadelphia, PA",
        "job_url": SOURCE_URL,
        "source": "Company website",
        "employment_type": JobPosting.EmploymentType.FULL_TIME,
        "work_arrangement": JobPosting.WorkArrangement.HYBRID,
        "deadline_status": JobPosting.DeadlineStatus.NOT_STATED,
        "application_deadline": "",
        "next_action": "Verify listing and review requirements",
        "description": SAMPLE_LISTING,
        "role_family": "Embedded Software Engineering",
        "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
        "industry": "Medical devices",
        "required_skills": "Python\nC\nEmbedded systems",
        "preferred_skills": "",
        "required_education": "Electrical Engineering\nComputer Science",
        "preferred_education": "",
        "minimum_years_experience": "0",
        "maximum_years_experience": "2",
        "responsibilities": "Develop embedded software\nCreate integration tests",
        "certifications": "",
        "work_authorization_requirements": "",
        "hard_disqualifiers": "",
        "requirement_notes": "Reviewed against the original listing.",
    }
    if confirm_duplicate:
        payload["confirm_duplicate"] = "on"
    return payload


class DuplicateFingerprintTests(TestCase):
    def test_url_normalization_ignores_tracking_and_fragment(self):
        left = normalize_source_url(
            "HTTPS://Example.COM/jobs/123/?utm_source=linkedin&job=abc#details"
        )
        right = normalize_source_url(
            "https://example.com/jobs/123?job=abc&utm_medium=social"
        )

        self.assertEqual(left, right)
        self.assertEqual(left, "https://example.com/jobs/123?job=abc")

    def test_text_fingerprint_is_whitespace_and_case_stable(self):
        self.assertEqual(
            listing_text_sha256("Embedded  Engineer\nPython"),
            listing_text_sha256(" embedded engineer python "),
        )

    def test_same_role_candidate_is_warning_not_blocking(self):
        job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical Devices",
            location="Philadelphia, PA",
        )

        analysis = analyze_job_duplicates(
            source_url="",
            raw_text="A different listing body with enough text for comparison.",
            extracted_job={
                "title": job.title,
                "company": job.company,
                "location": job.location,
            },
        )

        self.assertTrue(analysis["has_candidates"])
        self.assertFalse(analysis["blocking"])
        self.assertEqual(
            analysis["candidates"][0]["reason"],
            DUPLICATE_REASON_SAME_ROLE,
        )


class IntakeDuplicatePreflightTests(TestCase):
    def test_exact_url_stops_before_extractor_call(self):
        existing = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical Devices",
            location="Philadelphia, PA",
            job_url=SOURCE_URL,
        )

        with patch("tracker.intake_views.extract_job_with_fallback") as extractor:
            response = self.client.post(
                reverse("job_intake_start"),
                {
                    "source_url": f"{SOURCE_URL}/?utm_source=test#apply",
                    "source_label": "Company website",
                    "raw_text": SAMPLE_LISTING,
                },
            )

        self.assertEqual(response.status_code, 200)
        extractor.assert_not_called()
        self.assertContains(response, "NO EXTRACTION REQUEST MADE")
        self.assertContains(response, existing.title)
        self.assertEqual(JobPosting.objects.count(), 1)
        self.assertEqual(JobExtractionRun.objects.count(), 0)
        self.assertNotIn(INTAKE_SESSION_KEY, self.client.session)

    def test_preflight_identifies_exact_url_reason(self):
        JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical Devices",
            job_url=SOURCE_URL,
        )

        analysis = analyze_job_duplicates(
            source_url=f"{SOURCE_URL}?utm_campaign=jobs",
            raw_text="A new listing body that does not match the stored text.",
        )

        self.assertTrue(analysis["blocking"])
        self.assertEqual(
            analysis["candidates"][0]["reason"],
            DUPLICATE_REASON_EXACT_URL,
        )


class IntakeProvenanceWorkflowTests(TestCase):
    def _start_draft(self, *, continue_duplicate=False):
        data = {
            "source_url": SOURCE_URL,
            "source_label": "Company website",
            "raw_text": SAMPLE_LISTING,
        }
        if continue_duplicate:
            data["continue_duplicate"] = "on"
        return self.client.post(reverse("job_intake_start"), data)

    def test_history_is_created_only_after_approved_review(self):
        response = self._start_draft()

        self.assertRedirects(response, reverse("job_intake_review"))
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobExtractionRun.objects.count(), 0)

        response = self.client.post(
            reverse("job_intake_review"),
            review_payload(),
        )

        job = JobPosting.objects.get()
        run = JobExtractionRun.objects.get(job=job)
        self.assertRedirects(response, reverse("job_detail", args=[job.id]))
        self.assertEqual(run.source_url, SOURCE_URL)
        self.assertEqual(run.normalized_source_url, SOURCE_URL)
        self.assertEqual(run.raw_text_sha256, listing_text_sha256(SAMPLE_LISTING))
        self.assertEqual(run.provider_key, "deterministic")
        self.assertEqual(run.provider_version, "deterministic-intake-v1")
        self.assertEqual(run.extraction_mode, "deterministic")
        self.assertEqual(run.reviewed_payload["title"], job.title)
        self.assertEqual(run.reviewed_payload["application_deadline"], None)
        self.assertFalse(run.duplicate_override)
        self.assertNotIn(INTAKE_SESSION_KEY, self.client.session)

    def test_exact_duplicate_requires_second_confirmation_before_save(self):
        existing = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical Devices",
            location="Philadelphia, PA",
            job_url=SOURCE_URL,
        )
        response = self._start_draft(continue_duplicate=True)
        self.assertRedirects(response, reverse("job_intake_review"))

        response = self.client.post(
            reverse("job_intake_review"),
            review_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EXPLICIT OVERRIDE REQUIRED")
        self.assertEqual(JobPosting.objects.count(), 1)
        self.assertEqual(JobExtractionRun.objects.count(), 0)

        response = self.client.post(
            reverse("job_intake_review"),
            review_payload(confirm_duplicate=True),
        )

        created = JobPosting.objects.exclude(pk=existing.pk).get()
        run = JobExtractionRun.objects.get(job=created)
        self.assertRedirects(response, reverse("job_detail", args=[created.id]))
        self.assertTrue(run.duplicate_override)
        self.assertEqual(run.duplicate_candidates[0]["job_id"], existing.id)
        self.assertEqual(
            run.duplicate_candidates[0]["reason"],
            DUPLICATE_REASON_EXACT_URL,
        )

    def test_discarded_draft_creates_no_history(self):
        self._start_draft()

        response = self.client.post(reverse("job_intake_clear"))

        self.assertRedirects(response, reverse("job_intake_start"))
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobExtractionRun.objects.count(), 0)
