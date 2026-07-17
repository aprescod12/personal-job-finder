from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import JobPosting, ListingVerificationRun


class VerificationReviewWorkflowTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical",
            job_url="https://careers.example.com/jobs/123",
            listing_status=JobPosting.ListingStatus.UNVERIFIED,
            deadline_status=JobPosting.DeadlineStatus.UNKNOWN,
        )

    def create_run(self, **overrides):
        values = {
            "job": self.job,
            "status": ListingVerificationRun.RunStatus.NEEDS_REVIEW,
            "review_status": ListingVerificationRun.ReviewStatus.PENDING,
            "requested_url": self.job.job_url,
            "final_url": "https://careers.example.com/jobs/123",
            "detected_listing_status": JobPosting.ListingStatus.OPEN,
            "detected_deadline_status": JobPosting.DeadlineStatus.ROLLING,
            "confidence": ListingVerificationRun.Confidence.MEDIUM,
            "evidence": "Role and company matched and an application action was found.",
            "structured_evidence": {"interpretation_performed": True},
            "completed_at": timezone.now(),
        }
        values.update(overrides)
        return ListingVerificationRun.objects.create(**values)

    def review_url(self, run):
        return reverse(
            "review_verification_run",
            kwargs={"job_id": self.job.id, "run_id": run.id},
        )

    def test_review_screen_uses_detected_result_as_initial_suggestion(self):
        run = self.create_run()

        response = self.client.get(self.review_url(run))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REVIEW BEFORE APPLYING")
        self.assertEqual(
            response.context["form"].initial["listing_status"],
            JobPosting.ListingStatus.OPEN,
        )
        self.assertEqual(
            response.context["form"].initial["deadline_status"],
            JobPosting.DeadlineStatus.ROLLING,
        )

    def test_accepting_review_applies_values_to_job_and_marks_run_accepted(self):
        run = self.create_run()

        response = self.client.post(
            self.review_url(run),
            {
                "decision": "apply",
                "job_url": "https://careers.example.com/jobs/123",
                "listing_status": JobPosting.ListingStatus.OPEN,
                "deadline_status": JobPosting.DeadlineStatus.ROLLING,
                "application_deadline": "",
                "listing_verification_notes": "Confirmed manually on the employer site.",
            },
        )

        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))
        self.job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(self.job.listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(self.job.deadline_status, JobPosting.DeadlineStatus.ROLLING)
        self.assertEqual(self.job.listing_last_verified, timezone.localdate())
        self.assertEqual(
            self.job.listing_verification_notes,
            "Confirmed manually on the employer site.",
        )
        self.assertEqual(
            run.review_status,
            ListingVerificationRun.ReviewStatus.ACCEPTED,
        )
        self.assertTrue(run.structured_evidence["review_decision"]["job_record_changed"])

    def test_reviewer_can_correct_automated_result_before_applying(self):
        run = self.create_run(
            detected_listing_status=JobPosting.ListingStatus.OPEN,
            detected_deadline_status=JobPosting.DeadlineStatus.UNKNOWN,
        )

        response = self.client.post(
            self.review_url(run),
            {
                "decision": "apply",
                "job_url": self.job.job_url,
                "listing_status": JobPosting.ListingStatus.CLOSED,
                "deadline_status": JobPosting.DeadlineStatus.NOT_STATED,
                "application_deadline": "",
                "listing_verification_notes": "Employer page says applications are closed.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.job.refresh_from_db()
        self.assertEqual(self.job.listing_status, JobPosting.ListingStatus.CLOSED)
        self.assertEqual(
            self.job.deadline_status,
            JobPosting.DeadlineStatus.NOT_STATED,
        )

    def test_rejecting_suggestion_leaves_job_unchanged(self):
        run = self.create_run()

        response = self.client.post(
            self.review_url(run),
            {"decision": "reject"},
        )

        self.assertRedirects(
            response,
            reverse(
                "verification_run_detail",
                kwargs={"job_id": self.job.id, "run_id": run.id},
            ),
        )
        self.job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(
            self.job.listing_status,
            JobPosting.ListingStatus.UNVERIFIED,
        )
        self.assertIsNone(self.job.listing_last_verified)
        self.assertEqual(
            run.review_status,
            ListingVerificationRun.ReviewStatus.REJECTED,
        )
        self.assertFalse(run.structured_evidence["review_decision"]["job_record_changed"])

    def test_failed_run_can_be_bypassed_with_manual_review(self):
        run = self.create_run(
            status=ListingVerificationRun.RunStatus.FAILED,
            review_status=ListingVerificationRun.ReviewStatus.PENDING,
            detected_listing_status=JobPosting.ListingStatus.UNVERIFIED,
            error_message="Experimental auto-check failed.",
        )

        response = self.client.post(
            self.review_url(run),
            {
                "decision": "apply",
                "job_url": self.job.job_url,
                "listing_status": JobPosting.ListingStatus.OPEN,
                "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
                "application_deadline": "2026-08-15",
                "listing_verification_notes": "Checked manually after the beta run failed.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(self.job.listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(self.job.application_deadline, date(2026, 8, 15))
        self.assertEqual(
            run.review_status,
            ListingVerificationRun.ReviewStatus.ACCEPTED,
        )

    def test_confirmed_deadline_requires_a_date(self):
        run = self.create_run()

        response = self.client.post(
            self.review_url(run),
            {
                "decision": "apply",
                "job_url": self.job.job_url,
                "listing_status": JobPosting.ListingStatus.OPEN,
                "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
                "application_deadline": "",
                "listing_verification_notes": "Deadline claimed but no date entered.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "application_deadline",
            "Enter the confirmed application deadline.",
        )
        self.job.refresh_from_db()
        self.assertEqual(
            self.job.listing_status,
            JobPosting.ListingStatus.UNVERIFIED,
        )
