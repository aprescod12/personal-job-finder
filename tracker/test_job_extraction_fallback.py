from django.test import TestCase, override_settings
from django.urls import reverse

from .intake_views import INTAKE_SESSION_KEY
from .models import JobPosting, JobRequirement
from .services.job_extraction import (
    ERROR_AUTHENTICATION,
    ERROR_INVALID_RESPONSE,
    ERROR_TIMEOUT,
    BaseJobExtractor,
    JobExtractionError,
    JobExtractionRequest,
    JobExtractionResult,
)
from .services.job_extraction_coordinator import extract_job_with_fallback
from .services.job_intake import DeterministicJobExtractor


SIMPLE_LISTING = """
Job Title: Biomedical Test Engineer
Company: Example Medical
Location: Boston, MA

Required Qualifications
- Bachelor's degree in Biomedical Engineering
- Python
"""


class SuccessfulAIExtractor(BaseJobExtractor):
    provider_key = "successful_ai"
    provider_label = "Successful AI extractor"
    provider_version = "successful-ai-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        return self.result(
            job={
                "title": "Biomedical Test Engineer",
                "company": "Example Medical",
                "job_url": request.source_url,
                "source": request.source_label,
                "description": request.listing_text,
            },
            requirements={"required_skills": "Python"},
            evidence=["AI evidence"],
        )


class TimeoutExtractor(BaseJobExtractor):
    provider_key = "timeout_ai"
    provider_label = "Timeout AI extractor"
    provider_version = "timeout-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        raise JobExtractionError(
            "The AI extraction request timed out.",
            category=ERROR_TIMEOUT,
            retryable=True,
        )


class AuthenticationFailureExtractor(BaseJobExtractor):
    provider_key = "auth_ai"
    provider_label = "Authentication failure extractor"
    provider_version = "auth-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        raise JobExtractionError(
            "AI authentication failed.",
            category=ERROR_AUTHENTICATION,
        )


class InvalidResultExtractor(BaseJobExtractor):
    provider_key = "invalid_ai"
    provider_label = "Invalid result extractor"
    provider_version = "invalid-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest):
        return {"not": "a JobExtractionResult"}


class UnexpectedFailureExtractor(BaseJobExtractor):
    provider_key = "unexpected_ai"
    provider_label = "Unexpected failure extractor"
    provider_version = "unexpected-v1"
    extraction_mode = "ai"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        raise RuntimeError("private-provider-detail-should-not-escape")


class FailingFallbackExtractor(BaseJobExtractor):
    provider_key = "failing_fallback"
    provider_label = "Failing fallback extractor"
    provider_version = "failing-fallback-v1"
    extraction_mode = "deterministic"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        raise JobExtractionError(
            "Fallback output was invalid.",
            category=ERROR_INVALID_RESPONSE,
        )


class MustNotRunExtractor(BaseJobExtractor):
    provider_key = "must_not_run"
    provider_label = "Must not run"
    provider_version = "must-not-run-v1"
    extraction_mode = "test"

    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        raise AssertionError("Fallback should not run after primary success.")


class ExtractionCoordinatorTests(TestCase):
    def test_primary_success_returns_one_attempt_without_fallback(self):
        payload = extract_job_with_fallback(
            SIMPLE_LISTING,
            primary_extractor=SuccessfulAIExtractor(),
            fallback_extractor=MustNotRunExtractor(),
        )

        orchestration = payload["orchestration"]
        self.assertEqual(payload["provider"]["key"], "successful_ai")
        self.assertEqual(orchestration["status"], "primary_success")
        self.assertFalse(orchestration["fallback_used"])
        self.assertFalse(orchestration["manual_review_required"])
        self.assertEqual(len(orchestration["attempts"]), 1)
        self.assertTrue(orchestration["attempts"][0]["success"])
        self.assertGreaterEqual(orchestration["total_elapsed_ms"], 0)
        self.assertEqual(JobPosting.objects.count(), 0)

    def test_timeout_uses_deterministic_fallback_and_preserves_failure_metadata(self):
        payload = extract_job_with_fallback(
            SIMPLE_LISTING,
            source_url="https://example.com/job",
            source_label="Company website",
            primary_extractor=TimeoutExtractor(),
            fallback_extractor=DeterministicJobExtractor(),
        )

        orchestration = payload["orchestration"]
        self.assertEqual(payload["provider"]["key"], "deterministic")
        self.assertEqual(orchestration["status"], "fallback_success")
        self.assertTrue(orchestration["fallback_used"])
        self.assertFalse(orchestration["manual_review_required"])
        self.assertEqual(len(orchestration["attempts"]), 2)
        self.assertEqual(
            orchestration["attempts"][0]["error_category"],
            ERROR_TIMEOUT,
        )
        self.assertTrue(orchestration["attempts"][0]["retryable"])
        self.assertTrue(orchestration["attempts"][1]["success"])
        self.assertIn("deterministic fallback", " ".join(payload["warnings"]))
        self.assertEqual(payload["job"]["job_url"], "https://example.com/job")
        self.assertEqual(JobPosting.objects.count(), 0)

    def test_known_primary_failure_categories_can_fall_back(self):
        for extractor, category in (
            (AuthenticationFailureExtractor(), ERROR_AUTHENTICATION),
            (InvalidResultExtractor(), ERROR_INVALID_RESPONSE),
        ):
            with self.subTest(category=category):
                payload = extract_job_with_fallback(
                    SIMPLE_LISTING,
                    primary_extractor=extractor,
                    fallback_extractor=DeterministicJobExtractor(),
                )
                self.assertTrue(payload["orchestration"]["fallback_used"])
                self.assertEqual(
                    payload["orchestration"]["attempts"][0]["error_category"],
                    category,
                )

    def test_unexpected_provider_exception_is_sanitized_before_fallback(self):
        payload = extract_job_with_fallback(
            SIMPLE_LISTING,
            primary_extractor=UnexpectedFailureExtractor(),
            fallback_extractor=DeterministicJobExtractor(),
        )

        serialized = str(payload)
        self.assertNotIn("private-provider-detail-should-not-escape", serialized)
        self.assertIn("failed unexpectedly", serialized)
        self.assertTrue(payload["orchestration"]["fallback_used"])

    def test_both_extractors_failing_produces_manual_review_draft(self):
        payload = extract_job_with_fallback(
            SIMPLE_LISTING,
            source_url="https://example.com/job",
            source_label="Company website",
            primary_extractor=TimeoutExtractor(),
            fallback_extractor=FailingFallbackExtractor(),
        )

        orchestration = payload["orchestration"]
        self.assertEqual(payload["provider"]["key"], "manual_review")
        self.assertTrue(orchestration["manual_review_required"])
        self.assertFalse(orchestration["fallback_used"])
        self.assertEqual(len(orchestration["attempts"]), 2)
        self.assertEqual(payload["job"]["description"], SIMPLE_LISTING)
        self.assertEqual(payload["job"]["job_url"], "https://example.com/job")
        self.assertEqual(payload["job"]["source"], "Company website")
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobRequirement.objects.count(), 0)

    def test_disabled_fallback_goes_directly_to_manual_review(self):
        payload = extract_job_with_fallback(
            SIMPLE_LISTING,
            primary_extractor=TimeoutExtractor(),
            fallback_extractor=DeterministicJobExtractor(),
            fallback_enabled=False,
        )

        self.assertTrue(payload["orchestration"]["manual_review_required"])
        self.assertEqual(len(payload["orchestration"]["attempts"]), 1)
        self.assertIn("fallback is disabled", " ".join(payload["warnings"]).lower())


class ExtractionCoordinatorViewTests(TestCase):
    @override_settings(
        JOB_INTAKE_EXTRACTOR=(
            "tracker.test_job_extraction_fallback.TimeoutExtractor"
        ),
        JOB_INTAKE_FALLBACK_ENABLED=True,
        JOB_INTAKE_FALLBACK_EXTRACTOR=(
            "tracker.services.job_intake.DeterministicJobExtractor"
        ),
    )
    def test_intake_view_discloses_deterministic_fallback(self):
        response = self.client.post(
            reverse("job_intake_start"),
            {
                "raw_text": SIMPLE_LISTING,
                "source_url": "https://example.com/job",
                "source_label": "Company website",
            },
        )

        self.assertRedirects(response, reverse("job_intake_review"))
        draft = self.client.session[INTAKE_SESSION_KEY]
        self.assertTrue(draft["extraction"]["orchestration"]["fallback_used"])
        self.assertEqual(draft["extraction"]["provider"]["key"], "deterministic")
        self.assertEqual(JobPosting.objects.count(), 0)

        review = self.client.get(reverse("job_intake_review"))
        self.assertContains(review, "FALLBACK USED")
        self.assertContains(review, "TIMEOUT")
        self.assertContains(review, "DETERMINISTIC")
        self.assertContains(review, "Nothing is saved until approval")

    @override_settings(
        JOB_INTAKE_EXTRACTOR=(
            "tracker.test_job_extraction_fallback.TimeoutExtractor"
        ),
        JOB_INTAKE_FALLBACK_ENABLED=True,
        JOB_INTAKE_FALLBACK_EXTRACTOR=(
            "tracker.test_job_extraction_fallback.FailingFallbackExtractor"
        ),
    )
    def test_intake_view_preserves_listing_when_both_extractors_fail(self):
        response = self.client.post(
            reverse("job_intake_start"),
            {
                "raw_text": SIMPLE_LISTING,
                "source_url": "https://example.com/job",
                "source_label": "Company website",
            },
        )

        self.assertRedirects(response, reverse("job_intake_review"))
        draft = self.client.session[INTAKE_SESSION_KEY]
        extraction = draft["extraction"]
        self.assertTrue(extraction["orchestration"]["manual_review_required"])
        self.assertEqual(extraction["job"]["description"], SIMPLE_LISTING)
        self.assertEqual(JobPosting.objects.count(), 0)

        review = self.client.get(reverse("job_intake_review"))
        self.assertContains(review, "MANUAL REVIEW REQUIRED")
        self.assertContains(review, "NO EXTRACTOR PRODUCED A STRUCTURED DRAFT")
        self.assertContains(review, "VIEW ORIGINAL PASTED LISTING")
