import json
import tempfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from tracker.models import JobPosting, JobRequirement

from .services.job_extraction import BaseJobExtractor, JobExtractionRequest
from .services.job_extraction_ai_evaluation import (
    AI_EVALUATION_RUNNER_VERSION,
    AI_PROMPT_VERSION,
    compare_evaluation_runs,
    evaluate_ai_cases,
    render_ai_json_report,
    render_ai_markdown_report,
    run_ai_comparison,
    write_ai_report,
)
from .services.job_extraction_evaluation_runner import evaluate_cases
from .services.job_intake import DeterministicJobExtractor


class FakeBackend:
    model = "fake-evaluation-model"


class GroundTruthAIExtractor(BaseJobExtractor):
    provider_key = "fake_ai"
    provider_label = "Fake AI extractor"
    provider_version = "fake-ai-v1"
    extraction_mode = "ai"

    def __init__(self):
        self.backend = FakeBackend()
        self.calls = 0

    def extract(self, request: JobExtractionRequest):
        self.calls += 1
        return self.result(
            job={
                "title": "Junior Embedded Firmware Engineer",
                "company": "Northstar Medical Systems",
                "location": "Minneapolis, Minnesota",
                "employment_type": "full_time",
                "work_arrangement": "hybrid",
                "salary_text": "",
                "date_posted": "",
                "deadline_status": "confirmed",
                "application_deadline": "2026-08-15",
                "description": request.listing_text,
            },
            requirements={
                "role_family": "Embedded Firmware Engineering",
                "seniority_level": "entry_level",
                "industry": (
                    "Medical devices\nWearable health technology\nPatient monitoring"
                ),
                "required_skills": (
                    "C programming\nMicrocontroller fundamentals\nUART\nI2C\nSPI\n"
                    "Git\nUnit testing\nHardware-software integration"
                ),
                "preferred_skills": (
                    "RTOS\nBluetooth Low Energy\nMedical-device development\n"
                    "IEC 62304 familiarity"
                ),
                "required_education": (
                    "Bachelor's degree in Electrical Engineering, Computer "
                    "Engineering, Computer Science, or a related field, completed "
                    "or expected by the start date"
                ),
                "preferred_education": "",
                "minimum_years_experience": 0,
                "maximum_years_experience": 2,
                "responsibilities": (
                    "Develop and debug embedded C firmware\n"
                    "Implement and test device interfaces\nWrite unit tests\n"
                    "Support hardware-software integration\n"
                    "Review code and document design decisions\n"
                    "Collaborate with electrical, systems, and verification engineers"
                ),
                "certifications": "",
                "work_authorization_requirements": (
                    "Authorized to work in the United States\n"
                    "Immigration sponsorship unavailable now or in the future"
                ),
                "hard_disqualifiers": "Immigration sponsorship unavailable",
                "requirement_notes": (
                    "The degree may be completed by the start date; relocation is "
                    "available and travel is under 10 percent."
                ),
            },
            evidence=["Synthetic test evidence"],
            warnings=[],
        )


class AIEvaluationGuardTests(SimpleTestCase):
    def test_live_ai_requires_explicit_permission(self):
        with self.assertRaisesMessage(ValueError, "Live AI evaluation is disabled"):
            evaluate_ai_cases(
                case_ids=["case-002-embedded-firmware-entry-level"],
            )

    def test_non_ai_extractor_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "mode is 'ai'"):
            evaluate_ai_cases(
                case_ids=["case-002-embedded-firmware-entry-level"],
                extractor=DeterministicJobExtractor(),
            )

    def test_command_refuses_to_run_without_live_flag(self):
        with self.assertRaisesMessage(CommandError, "--allow-live-ai"):
            call_command("evaluate_job_extraction_ai")


class AIEvaluationTests(TestCase):
    case_id = "case-002-embedded-firmware-entry-level"
    timestamp = datetime(2026, 7, 21, tzinfo=timezone.utc)

    def test_injected_ai_evaluation_records_versions_and_latency(self):
        extractor = GroundTruthAIExtractor()
        clock_values = iter([10.0, 10.1, 10.35, 10.5])

        run = evaluate_ai_cases(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=extractor,
            clock=lambda: next(clock_values),
        )

        self.assertEqual(extractor.calls, 1)
        self.assertFalse(run.live_provider_calls)
        self.assertEqual(run.model, "fake-evaluation-model")
        self.assertEqual(run.prompt_version, AI_PROMPT_VERSION)
        self.assertEqual(run.evaluation.provider, "ai")
        self.assertEqual(run.evaluation.case_count, 1)
        self.assertEqual(run.evaluation.cases[0].provider_version, "fake-ai-v1")
        self.assertAlmostEqual(run.case_timings[0].duration_ms, 250.0)
        self.assertAlmostEqual(run.total_duration_ms, 500.0)
        self.assertGreater(run.evaluation.field_agreement_percent, 95)
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobRequirement.objects.count(), 0)

    def test_comparison_uses_same_cases_and_official_scorer(self):
        comparison = run_ai_comparison(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=GroundTruthAIExtractor(),
            clock=lambda: 1.0,
        )

        self.assertEqual(
            comparison.ai.evaluation.runner_version,
            comparison.deterministic.runner_version,
        )
        self.assertEqual(comparison.ai.evaluation.case_count, 1)
        self.assertEqual(comparison.deterministic.case_count, 1)
        self.assertGreater(comparison.overall_delta_points, 0)
        self.assertGreater(comparison.sensitive_delta_points, 0)
        self.assertEqual(len(comparison.case_deltas), 1)
        self.assertEqual(
            {row.key for row in comparison.field_deltas},
            set(comparison.deterministic.field_summary),
        )

    def test_comparison_rejects_different_case_sets(self):
        ai = evaluate_ai_cases(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=GroundTruthAIExtractor(),
            clock=lambda: 1.0,
        )
        deterministic = evaluate_cases(
            case_ids=["case-003-quality-validation-engineer"],
            generated_at=self.timestamp,
        )

        with self.assertRaisesMessage(ValueError, "same case IDs"):
            compare_evaluation_runs(deterministic, ai, generated_at=self.timestamp)

    def test_reports_include_safety_and_provider_metadata(self):
        comparison = run_ai_comparison(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=GroundTruthAIExtractor(),
            clock=lambda: 1.0,
        )

        payload = json.loads(render_ai_json_report(comparison))
        markdown = render_ai_markdown_report(comparison)

        self.assertEqual(
            payload["comparison_version"],
            AI_EVALUATION_RUNNER_VERSION,
        )
        self.assertEqual(
            payload["ai"]["ai_metadata"]["model"],
            "fake-evaluation-model",
        )
        self.assertFalse(
            payload["ai"]["ai_metadata"]["live_provider_calls"]
        )
        self.assertIn("AI vs Deterministic", markdown)
        self.assertIn("deterministic fallback is disabled", markdown)
        self.assertIn("does not rank jobs", markdown)

    def test_write_report_creates_json_file(self):
        comparison = run_ai_comparison(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=GroundTruthAIExtractor(),
            clock=lambda: 1.0,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "nested" / "comparison.json"
            written = write_ai_report(
                comparison,
                output=destination,
                report_format="json",
            )

            self.assertEqual(written, destination)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["ai"]["case_count"], 1)

    @patch(
        "tracker.management.commands.evaluate_job_extraction_ai.run_ai_comparison"
    )
    def test_command_can_render_fake_comparison_without_live_call(self, mocked_run):
        comparison = run_ai_comparison(
            case_ids=[self.case_id],
            generated_at=self.timestamp,
            extractor=GroundTruthAIExtractor(),
            clock=lambda: 1.0,
        )
        mocked_run.return_value = comparison
        stdout = StringIO()

        call_command(
            "evaluate_job_extraction_ai",
            "--allow-live-ai",
            "--format",
            "json",
            "--case",
            self.case_id,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["ai"]["case_count"], 1)
        mocked_run.assert_called_once()
