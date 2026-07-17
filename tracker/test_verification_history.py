from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import JobPosting, ListingVerificationRun


class ListingVerificationRunTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical",
            job_url="https://careers.example.com/jobs/embedded-software-engineer",
            listing_status=JobPosting.ListingStatus.OPEN,
            deadline_status=JobPosting.DeadlineStatus.NOT_STATED,
            listing_last_verified=date(2026, 7, 17),
            listing_verification_notes="Previously verified manually.",
        )

    def test_run_stores_agent_evidence_without_overwriting_job(self):
        run = ListingVerificationRun.objects.create(
            job=self.job,
            trigger=ListingVerificationRun.Trigger.AGENT,
            status=ListingVerificationRun.RunStatus.COMPLETED,
            requested_url=self.job.job_url,
            final_url=self.job.job_url,
            http_status_code=200,
            detected_job_title="Embedded Software Engineer",
            detected_company="Example Medical",
            detected_listing_status=JobPosting.ListingStatus.CLOSED,
            detected_deadline_status=JobPosting.DeadlineStatus.NOT_STATED,
            apply_action_found=False,
            confidence=ListingVerificationRun.Confidence.HIGH,
            evidence="The employer page states that the position is no longer available.",
            structured_evidence={
                "closed_message_found": True,
                "apply_button_found": False,
            },
            verifier_version="stage3-step1-test",
            completed_at=timezone.now(),
        )

        self.job.refresh_from_db()

        self.assertEqual(run.job, self.job)
        self.assertEqual(run.structured_evidence["closed_message_found"], True)
        self.assertEqual(self.job.listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(
            self.job.listing_verification_notes,
            "Previously verified manually.",
        )

    def test_job_preserves_multiple_runs_in_newest_first_order(self):
        first = ListingVerificationRun.objects.create(
            job=self.job,
            requested_url=self.job.job_url,
        )
        second = ListingVerificationRun.objects.create(
            job=self.job,
            requested_url=self.job.job_url,
            trigger=ListingVerificationRun.Trigger.SCHEDULED,
        )

        runs = list(self.job.verification_runs.all())

        self.assertEqual(runs, [second, first])

    def test_confirmed_detected_deadline_requires_a_date(self):
        run = ListingVerificationRun(
            job=self.job,
            detected_deadline_status=JobPosting.DeadlineStatus.CONFIRMED,
        )

        with self.assertRaises(ValidationError) as error:
            run.full_clean()

        self.assertIn("detected_deadline", error.exception.message_dict)

    def test_manual_review_property_covers_uncertain_runs(self):
        run = ListingVerificationRun.objects.create(
            job=self.job,
            status=ListingVerificationRun.RunStatus.NEEDS_REVIEW,
            review_status=ListingVerificationRun.ReviewStatus.PENDING,
            confidence=ListingVerificationRun.Confidence.LOW,
        )

        self.assertTrue(run.is_finished)
        self.assertTrue(run.needs_manual_review)

    def test_completed_run_reports_duration(self):
        started_at = timezone.now()
        run = ListingVerificationRun.objects.create(
            job=self.job,
            status=ListingVerificationRun.RunStatus.COMPLETED,
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=12.5),
        )

        self.assertEqual(run.duration_seconds, 12.5)

    def test_deleting_job_cascades_verification_history(self):
        ListingVerificationRun.objects.create(job=self.job)

        self.job.delete()

        self.assertEqual(ListingVerificationRun.objects.count(), 0)
