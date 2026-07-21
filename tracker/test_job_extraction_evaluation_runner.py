import json
import tempfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from tracker.models import JobPosting, JobRequirement

from .services.job_extraction_evaluation_runner import (
    EVALUATION_RUNNER_VERSION,
    STATUS_EXACT,
    STATUS_INCORRECT,
    STATUS_MISSING,
    STATUS_PARTIAL,
    STATUS_UNEXPECTED,
    compare_list_field,
    compare_text_field,
    compare_typed_field,
    evaluate_cases,
    render_json_report,
    render_markdown_report,
    write_report,
)


class JobExtractionComparisonTests(SimpleTestCase):
    def test_typed_comparison_requires_exact_values(self):
        exact = compare_typed_field("job.employment_type", "full_time", "full_time")
        incorrect = compare_typed_field(
            "job.employment_type",
            "full_time",
            "internship",
        )
        missing = compare_typed_field("job.application_deadline", "2026-08-15", "")
        unexpected = compare_typed_field("job.application_deadline", None, "2026-08-15")

        self.assertEqual(exact.status, STATUS_EXACT)
        self.assertEqual(exact.score, 1.0)
        self.assertEqual(incorrect.status, STATUS_INCORRECT)
        self.assertEqual(missing.status, STATUS_MISSING)
        self.assertEqual(unexpected.status, STATUS_UNEXPECTED)

    def test_text_comparison_normalizes_case_and_punctuation(self):
        exact = compare_text_field(
            "job.title",
            "Software Engineer I — Connected Medical Devices",
            "software engineer i - connected medical devices",
        )
        partial = compare_text_field(
            "requirements.role_family",
            "Medical Device Software Engineering",
            "Software Engineer I Connected Medical Devices",
        )

        self.assertEqual(exact.status, STATUS_EXACT)
        self.assertEqual(exact.score, 1.0)
        self.assertEqual(partial.status, STATUS_PARTIAL)
        self.assertGreaterEqual(partial.score, 0.55)

    def test_list_comparison_uses_one_to_one_matching(self):
        comparison = compare_list_field(
            "requirements.required_skills",
            ["C programming", "UART", "I2C"],
            "C programming.\nFamiliarity with UART, I2C, and SPI.",
        )

        self.assertEqual(comparison.status, STATUS_PARTIAL)
        self.assertEqual(len(comparison.matched_items), 2)
        self.assertEqual(len(comparison.missing_items), 1)
        self.assertIn(comparison.missing_items[0], {"UART", "I2C"})
        self.assertFalse(comparison.unexpected_items)
        self.assertGreater(comparison.score, 0)
        self.assertLess(comparison.score, 1)

    def test_empty_expected_list_flags_unexpected_output(self):
        comparison = compare_list_field(
            "requirements.certifications",
            [],
            "ISO 13485 certification",
        )

        self.assertEqual(comparison.status, STATUS_UNEXPECTED)
        self.assertEqual(
            comparison.unexpected_items,
            ["ISO 13485 certification"],
        )


class JobExtractionEvaluationRunnerTests(TestCase):
    def test_runner_evaluates_all_seven_cases_without_database_writes(self):
        run = evaluate_cases(
            generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc)
        )

        self.assertEqual(run.runner_version, EVALUATION_RUNNER_VERSION)
        self.assertEqual(run.provider, "deterministic")
        self.assertEqual(run.case_count, 7)
        self.assertEqual(run.field_count, 7 * 23)
        self.assertEqual(len(run.cases), 7)
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobRequirement.objects.count(), 0)
        self.assertGreaterEqual(run.field_agreement_percent, 0)
        self.assertLessEqual(run.field_agreement_percent, 100)
        self.assertGreaterEqual(run.eligibility_sensitive_agreement_percent, 0)
        self.assertLessEqual(run.eligibility_sensitive_agreement_percent, 100)

    def test_runner_can_select_one_case(self):
        run = evaluate_cases(
            case_ids=["case-002-embedded-firmware-entry-level"],
            generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        )

        self.assertEqual(run.case_count, 1)
        self.assertEqual(
            run.cases[0].case_id,
            "case-002-embedded-firmware-entry-level",
        )
        self.assertEqual(
            run.cases[0].provider_version,
            "deterministic-intake-v1",
        )

    def test_unknown_case_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "Unknown evaluation case"):
            evaluate_cases(case_ids=["case-999-does-not-exist"])

    def test_json_report_is_machine_readable(self):
        run = evaluate_cases(
            case_ids=["case-003-quality-validation-engineer"],
            generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        )

        payload = json.loads(render_json_report(run))

        self.assertEqual(payload["case_count"], 1)
        self.assertEqual(payload["runner_version"], EVALUATION_RUNNER_VERSION)
        self.assertEqual(
            payload["cases"][0]["provider"]["version"],
            "deterministic-intake-v1",
        )
        self.assertIn("job.title", payload["field_summary"])

    def test_markdown_report_states_interpretation_boundary(self):
        run = evaluate_cases(
            case_ids=["case-006-ambiguous-sponsorship"],
            generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        )

        report = render_markdown_report(run)

        self.assertIn("# Deterministic Job Extraction Baseline", report)
        self.assertIn("not candidate-job match scores", report)
        self.assertIn("case-006-ambiguous-sponsorship", report)
        self.assertIn("## Interpretation boundary", report)

    def test_write_report_creates_parent_directory(self):
        run = evaluate_cases(
            case_ids=["case-007-citizenship-clearance"],
            generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = (
                Path(temporary_directory)
                / "nested"
                / "deterministic-baseline.json"
            )

            written = write_report(run, output=destination, report_format="json")

            self.assertEqual(written, destination)
            self.assertTrue(destination.is_file())
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["case_count"], 1)


class JobExtractionEvaluationCommandTests(SimpleTestCase):
    def test_command_prints_json_for_selected_case(self):
        stdout = StringIO()

        call_command(
            "evaluate_job_extraction",
            "--format",
            "json",
            "--case",
            "case-005-general-software-poor-format",
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["case_count"], 1)
        self.assertEqual(
            payload["cases"][0]["case_id"],
            "case-005-general-software-poor-format",
        )

    def test_command_writes_markdown_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "baseline.md"
            stdout = StringIO()

            call_command(
                "evaluate_job_extraction",
                "--format",
                "markdown",
                "--output",
                str(destination),
                stdout=stdout,
            )

            self.assertTrue(destination.is_file())
            self.assertIn(
                "Wrote 7-case markdown evaluation report",
                stdout.getvalue(),
            )
            self.assertIn(
                "# Deterministic Job Extraction Baseline",
                destination.read_text(encoding="utf-8"),
            )

    def test_command_rejects_unknown_case(self):
        with self.assertRaises(CommandError):
            call_command(
                "evaluate_job_extraction",
                "--case",
                "case-999-does-not-exist",
            )
