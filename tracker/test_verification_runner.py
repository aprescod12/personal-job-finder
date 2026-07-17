from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import JobPosting, ListingVerificationRun
from .services.listing_verification_runner import (
    VerificationAlreadyRunning,
    VerificationObservation,
    run_listing_verification,
)
from .services.page_retrieval import RetrievedPage


def retrieved_page(url="https://careers.example.com/jobs/123"):
    body = "<html><title>Test Engineer</title><a>Apply</a></html>"
    return RetrievedPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        charset="utf-8",
        bytes_read=len(body.encode()),
        body_sha256="a" * 64,
        body_text=body,
        body_stored=True,
        response_headers={"content_type": "text/html; charset=utf-8"},
    )


class CompletedTestVerifier:
    version = "test-completed-v1"

    def verify(self, job):
        return VerificationObservation(
            status=ListingVerificationRun.RunStatus.COMPLETED,
            final_url="https://careers.example.com/jobs/123",
            http_status_code=200,
            detected_job_title=job.title,
            detected_company=job.company,
            detected_listing_status=JobPosting.ListingStatus.OPEN,
            detected_deadline_status=JobPosting.DeadlineStatus.NOT_STATED,
            apply_action_found=True,
            confidence=ListingVerificationRun.Confidence.HIGH,
            review_status=ListingVerificationRun.ReviewStatus.NOT_REQUIRED,
            evidence="Direct role page and application action were found.",
            structured_evidence={"network_request_performed": True},
        )


class FailingTestVerifier:
    version = "test-failure-v1"

    def verify(self, job):
        raise RuntimeError("Synthetic verifier failure")


class ListingVerificationRunnerTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical",
            job_url="https://careers.example.com/jobs/123",
            listing_status=JobPosting.ListingStatus.UNVERIFIED,
            deadline_status=JobPosting.DeadlineStatus.UNKNOWN,
        )
        patcher = patch(
            "tracker.services.listing_verification_runner.ControlledHttpRetriever.retrieve",
            return_value=retrieved_page(),
        )
        self.retrieve_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_retrieval_records_transport_evidence_without_status_claim(self):
        run = run_listing_verification(self.job)

        self.assertEqual(
            run.status,
            ListingVerificationRun.RunStatus.NEEDS_REVIEW,
        )
        self.assertEqual(run.confidence, ListingVerificationRun.Confidence.MEDIUM)
        self.assertEqual(
            run.review_status,
            ListingVerificationRun.ReviewStatus.PENDING,
        )
        self.assertTrue(run.structured_evidence["network_request_performed"])
        self.assertTrue(run.structured_evidence["retrieval_only"])
        self.assertEqual(run.final_url, self.job.job_url)
        self.assertEqual(run.http_status_code, 200)
        self.assertEqual(run.detected_listing_status, JobPosting.ListingStatus.UNVERIFIED)
        self.assertEqual(run.detected_deadline_status, JobPosting.DeadlineStatus.UNKNOWN)
        self.assertIsNone(run.apply_action_found)
        self.assertIsNotNone(run.completed_at)

        self.job.refresh_from_db()
        self.assertEqual(
            self.job.listing_status,
            JobPosting.ListingStatus.UNVERIFIED,
        )
        self.assertEqual(
            self.job.deadline_status,
            JobPosting.DeadlineStatus.UNKNOWN,
        )
        self.assertIsNone(self.job.listing_last_verified)

    def test_default_retrieval_stores_bounded_page_text_for_later_interpretation(self):
        run = run_listing_verification(self.job)

        self.assertIn("Test Engineer", run.structured_evidence["page_text"])
        self.assertTrue(run.structured_evidence["body_stored"])
        self.assertEqual(run.structured_evidence["body_sha256"], "a" * 64)
        self.assertEqual(
            run.structured_evidence["next_required_capability"],
            "employer_page_interpretation",
        )

    def test_injected_verifier_can_complete_a_run(self):
        run = run_listing_verification(
            self.job,
            verifier=CompletedTestVerifier(),
        )

        self.assertEqual(run.status, ListingVerificationRun.RunStatus.COMPLETED)
        self.assertEqual(run.final_url, "https://careers.example.com/jobs/123")
        self.assertEqual(run.http_status_code, 200)
        self.assertEqual(
            run.detected_listing_status,
            JobPosting.ListingStatus.OPEN,
        )
        self.assertTrue(run.apply_action_found)
        self.assertEqual(run.verifier_version, "test-completed-v1")

        self.job.refresh_from_db()
        self.assertEqual(
            self.job.listing_status,
            JobPosting.ListingStatus.UNVERIFIED,
        )

    def test_missing_url_is_preserved_as_failed_run(self):
        self.job.job_url = ""
        self.job.save(update_fields=["job_url"])

        run = run_listing_verification(self.job)

        self.assertEqual(run.status, ListingVerificationRun.RunStatus.FAILED)
        self.assertIn("Add a direct employer job URL", run.error_message)
        self.assertEqual(
            run.review_status,
            ListingVerificationRun.ReviewStatus.PENDING,
        )
        self.retrieve_mock.assert_not_called()

    def test_verifier_exception_is_captured_on_run(self):
        run = run_listing_verification(
            self.job,
            verifier=FailingTestVerifier(),
        )

        self.assertEqual(run.status, ListingVerificationRun.RunStatus.FAILED)
        self.assertIn("Synthetic verifier failure", run.error_message)
        self.assertEqual(run.verifier_version, "test-failure-v1")
        self.assertEqual(
            run.structured_evidence["failure_type"],
            "RuntimeError",
        )
        self.assertIsNotNone(run.completed_at)

    def test_active_run_blocks_duplicate_execution(self):
        active = ListingVerificationRun.objects.create(
            job=self.job,
            status=ListingVerificationRun.RunStatus.RUNNING,
            requested_url=self.job.job_url,
        )

        with self.assertRaises(VerificationAlreadyRunning) as error:
            run_listing_verification(self.job)

        self.assertEqual(error.exception.run, active)
        self.assertEqual(self.job.verification_runs.count(), 1)


class ListingVerificationRunnerViewTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Test Engineer",
            company="Example Devices",
            job_url="https://jobs.example.com/test-engineer",
        )
        patcher = patch(
            "tracker.services.listing_verification_runner.ControlledHttpRetriever.retrieve",
            return_value=retrieved_page(
                "https://jobs.example.com/test-engineer"
            ),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_endpoint_is_post_only(self):
        response = self.client.get(
            reverse("run_job_verification", args=[self.job.id])
        )

        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.job.verification_runs.exists())

    def test_post_creates_run_and_redirects_to_result(self):
        response = self.client.post(
            reverse("run_job_verification", args=[self.job.id])
        )

        run = self.job.verification_runs.get()
        self.assertRedirects(
            response,
            reverse(
                "verification_run_detail",
                args=[self.job.id, run.id],
            ),
        )
        self.assertEqual(
            run.status,
            ListingVerificationRun.RunStatus.NEEDS_REVIEW,
        )
        self.assertEqual(run.http_status_code, 200)

    def test_existing_active_run_is_reused_instead_of_duplicated(self):
        active = ListingVerificationRun.objects.create(
            job=self.job,
            status=ListingVerificationRun.RunStatus.PENDING,
            requested_url=self.job.job_url,
        )

        response = self.client.post(
            reverse("run_job_verification", args=[self.job.id])
        )

        self.assertRedirects(
            response,
            reverse(
                "verification_run_detail",
                args=[self.job.id, active.id],
            ),
        )
        self.assertEqual(self.job.verification_runs.count(), 1)

    def test_run_detail_is_scoped_to_its_job(self):
        run = run_listing_verification(self.job)
        other_job = JobPosting.objects.create(
            title="Other Role",
            company="Other Company",
        )

        response = self.client.get(
            reverse(
                "verification_run_detail",
                args=[other_job.id, run.id],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_job_detail_shows_run_action_and_history(self):
        run = run_listing_verification(self.job)

        response = self.client.get(reverse("job_detail", args=[self.job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RUN VERIFICATION")
        self.assertContains(response, "AUDIT EVERY CHECK")
        self.assertContains(response, run.get_status_display())
        self.assertContains(
            response,
            reverse(
                "verification_run_detail",
                args=[self.job.id, run.id],
            ),
        )

    def test_result_page_explains_retrieval_limit(self):
        run = run_listing_verification(self.job)

        response = self.client.get(
            reverse(
                "verification_run_detail",
                args=[self.job.id, run.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CONTROLLED EMPLOYER-PAGE RETRIEVAL")
        self.assertContains(response, "NETWORK REQUEST COMPLETED")
        self.assertContains(response, "does not decide whether the role is open")
        self.assertContains(response, "HTTP STATUS")
        self.assertContains(response, "200")
