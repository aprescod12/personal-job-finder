from django.test import TestCase, override_settings

from .services.resume_deterministic import DeterministicResumeExtractor
from .services.resume_extraction import (
    ERROR_PROVIDER_FAILURE,
    BaseResumeExtractor,
    ResumeExtractionError,
    ResumeExtractionRequest,
)
from .services.resume_extraction_coordinator import extract_resume_with_fallback


RESUME_TEXT = """Amiri Prescod
amiri@example.com

Education
Villanova University
B.S. Electrical Engineering | 2025

Technical Skills
Python, MATLAB, C
"""


def request_for_resume():
    return ResumeExtractionRequest(
        document_text=RESUME_TEXT,
        source_id=1,
        source_sha256="b" * 64,
        source_filename="resume.txt",
        source_label="Current resume",
        document_parser_key="plain-text",
        document_parser_version="plain-text-v1",
    )


class FailingResumeExtractor(BaseResumeExtractor):
    provider_key = "failing"
    provider_label = "Failing resume extractor"
    provider_version = "failure-v1"
    extraction_mode = "ai"

    def extract(self, request):
        raise ResumeExtractionError(
            "Safe synthetic provider failure.",
            category=ERROR_PROVIDER_FAILURE,
            retryable=True,
        )


class SecondFailingResumeExtractor(BaseResumeExtractor):
    provider_key = "second-failing"
    provider_label = "Second failing resume extractor"
    provider_version = "failure-v2"
    extraction_mode = "deterministic"

    def extract(self, request):
        raise RuntimeError("raw secret diagnostic")


class StepClock:
    def __init__(self, *values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


class ResumeExtractionFallbackTests(TestCase):
    @override_settings(
        RESUME_EXTRACTOR="tests.primary.Path",
        RESUME_FALLBACK_EXTRACTOR="tests.fallback.Path",
        RESUME_FALLBACK_ENABLED=True,
    )
    def test_deterministic_fallback_creates_disclosed_review_draft(self):
        result = extract_resume_with_fallback(
            request_for_resume(),
            primary_extractor=FailingResumeExtractor(),
            fallback_extractor=DeterministicResumeExtractor(),
            clock=StepClock(1.0, 1.010, 1.011, 1.020, 1.025, 1.030),
        )

        self.assertEqual(result["provider"]["key"], "deterministic")
        self.assertEqual(result["identity"]["full_name"], "Amiri Prescod")
        self.assertTrue(result["orchestration"]["fallback_used"])
        self.assertFalse(result["orchestration"]["manual_review_required"])
        self.assertEqual(result["orchestration"]["status"], "fallback_success")
        self.assertEqual(len(result["orchestration"]["attempts"]), 2)
        self.assertFalse(result["orchestration"]["attempts"][0]["success"])
        self.assertTrue(result["orchestration"]["attempts"][0]["retryable"])
        self.assertTrue(result["orchestration"]["attempts"][1]["success"])
        self.assertIn("deterministic fallback", result["warnings"][0])

    @override_settings(
        RESUME_EXTRACTOR="tests.primary.Path",
        RESUME_FALLBACK_EXTRACTOR="tests.fallback.Path",
        RESUME_FALLBACK_ENABLED=False,
    )
    def test_disabled_fallback_returns_manual_review_draft(self):
        result = extract_resume_with_fallback(
            request_for_resume(),
            primary_extractor=FailingResumeExtractor(),
            fallback_enabled=False,
            clock=StepClock(1.0, 1.005, 1.010, 1.015),
        )

        self.assertEqual(result["provider"]["key"], "manual_resume_review")
        self.assertEqual(result["provider"]["mode"], "manual")
        self.assertTrue(result["orchestration"]["manual_review_required"])
        self.assertFalse(result["orchestration"]["fallback_used"])
        self.assertEqual(len(result["orchestration"]["attempts"]), 1)
        self.assertIn("disabled", " ".join(result["warnings"]))

    @override_settings(
        RESUME_EXTRACTOR="tests.primary.Path",
        RESUME_FALLBACK_EXTRACTOR="tests.fallback.Path",
        RESUME_FALLBACK_ENABLED=True,
    )
    def test_double_failure_returns_manual_review_without_raw_exception(self):
        result = extract_resume_with_fallback(
            request_for_resume(),
            primary_extractor=FailingResumeExtractor(),
            fallback_extractor=SecondFailingResumeExtractor(),
            clock=StepClock(1.0, 1.004, 1.005, 1.008, 1.010, 1.012),
        )

        self.assertTrue(result["orchestration"]["manual_review_required"])
        self.assertEqual(len(result["orchestration"]["attempts"]), 2)
        warning_text = " ".join(result["warnings"])
        self.assertIn("failed unexpectedly", warning_text)
        self.assertNotIn("raw secret diagnostic", warning_text)
