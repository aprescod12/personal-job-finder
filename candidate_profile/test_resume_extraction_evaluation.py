import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from .services.resume_extraction_evaluation import (
    CASE_SCHEMA_VERSION,
    DEFAULT_CASES_ROOT,
    ResumeEvaluationError,
    discover_cases,
    evaluate_case,
    load_case,
    run_evaluation,
)


class ResumeEvaluationCaseTests(SimpleTestCase):
    def test_repository_cases_are_valid_and_diverse(self):
        cases = discover_cases()

        self.assertGreaterEqual(len(cases), 3)
        self.assertEqual(len({case.case_id for case in cases}), len(cases))
        self.assertIn("standard_sections", {case.category for case in cases})
        self.assertIn("heading_variation", {case.category for case in cases})
        self.assertIn("missing_sections", {case.category for case in cases})

    def test_case_rejects_source_quote_absent_from_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory) / "case-invalid"
            case_dir.mkdir()
            (case_dir / "resume.txt").write_text("Case Person\n", encoding="utf-8")
            payload = {
                "schema_version": CASE_SCHEMA_VERSION,
                "case_id": "case-invalid",
                "title": "Invalid case",
                "category": "test",
                "expected": {
                    "identity": {
                        "full_name": "Case Person",
                        "email": "",
                        "phone": "",
                        "location": "",
                        "links": [],
                    },
                    "profile": {
                        "professional_summary": "",
                        "education_headings": [],
                        "experience_headings": [],
                        "project_headings": [],
                        "skills": [],
                        "certification_headings": [],
                        "leadership_headings": [],
                    },
                },
                "critical_claims": [
                    {
                        "path": "identity.full_name",
                        "expected_text": "Case Person",
                        "source_quote": "Absent quote",
                    }
                ],
                "forbidden_claims": [],
            }
            (case_dir / "ground-truth.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            with self.assertRaisesMessage(ResumeEvaluationError, "absent"):
                load_case(case_dir)


class ResumeEvaluationRunnerTests(SimpleTestCase):
    def test_standard_case_produces_structured_comparisons(self):
        case = load_case(DEFAULT_CASES_ROOT / "case-001-standard-engineering")
        result = evaluate_case(case)

        self.assertEqual(result["provider"]["key"], "deterministic")
        self.assertEqual(result["critical_passed"], result["critical_total"])
        self.assertEqual(result["forbidden_hits"], [])
        self.assertGreater(result["agreement_percent"], 70)
        self.assertTrue(result["comparisons"])

    def test_full_run_is_offline_and_has_no_forbidden_claims(self):
        report = run_evaluation()

        self.assertEqual(report["provider"], "deterministic")
        self.assertGreaterEqual(report["case_count"], 3)
        self.assertEqual(report["critical_passed"], report["critical_total"])
        self.assertEqual(report["forbidden_hit_count"], 0)
        self.assertGreater(report["agreement_percent"], 65)

    def test_management_command_writes_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "resume-evaluation.json"
            call_command(
                "evaluate_resume_extraction",
                output=str(output_path),
                minimum_agreement=60,
            )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["provider"], "deterministic")
            self.assertGreaterEqual(report["case_count"], 3)
