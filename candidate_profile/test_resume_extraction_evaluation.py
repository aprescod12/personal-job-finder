import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .services.resume_extraction import BaseResumeExtractor
from .services.resume_extraction_evaluation import (
    CASE_SCHEMA_VERSION,
    DEFAULT_CASES_ROOT,
    EVIDENCE_FIELD_BY_PATH,
    ResumeEvaluationError,
    compare_evaluation_runs,
    discover_cases,
    evaluate_case,
    load_case,
    run_comparison,
    run_evaluation,
)


class ExpectedCaseExtractor(BaseResumeExtractor):
    provider_key = "openai_test_double"
    provider_label = "Injected OpenAI evaluation test double"
    provider_version = "test-v1"
    extraction_mode = "ai"

    def __init__(self, cases=None):
        active_cases = cases or discover_cases()
        self.expected_by_title = {
            case.title: case.expected for case in active_cases
        }

    @staticmethod
    def _entries(headings):
        return [
            {
                "heading": heading,
                "subheading": "",
                "dates": "",
                "details": [],
                "source_text": heading,
            }
            for heading in headings
        ]

    @staticmethod
    def _source_text(value):
        if isinstance(value, list):
            return ", ".join(value)
        return str(value)

    def extract(self, request):
        expected = self.expected_by_title[request.source_label]
        identity = dict(expected["identity"])
        profile_expected = expected["profile"]
        profile = {
            "professional_summary": profile_expected["professional_summary"],
            "education": self._entries(profile_expected["education_headings"]),
            "experience": self._entries(profile_expected["experience_headings"]),
            "projects": self._entries(profile_expected["project_headings"]),
            "skills": list(profile_expected["skills"]),
            "certifications": self._entries(
                profile_expected["certification_headings"]
            ),
            "leadership": self._entries(profile_expected["leadership_headings"]),
        }
        expected_fields = {
            "identity.full_name": identity["full_name"],
            "identity.email": identity["email"],
            "identity.phone": identity["phone"],
            "identity.location": identity["location"],
            "identity.links": identity["links"],
            "profile.professional_summary": profile["professional_summary"],
            "profile.education_headings": profile_expected["education_headings"],
            "profile.experience_headings": profile_expected["experience_headings"],
            "profile.project_headings": profile_expected["project_headings"],
            "profile.skills": profile_expected["skills"],
            "profile.certification_headings": profile_expected[
                "certification_headings"
            ],
            "profile.leadership_headings": profile_expected[
                "leadership_headings"
            ],
        }
        evidence = [
            {
                "field": EVIDENCE_FIELD_BY_PATH[path],
                "source_text": self._source_text(value),
                "note": "Synthetic evidence emitted by the injected test double.",
            }
            for path, value in expected_fields.items()
            if value
        ]
        return self.result(
            identity=identity,
            profile=profile,
            evidence=evidence,
            warnings=[],
        )


class EmptyAIExtractor(BaseResumeExtractor):
    provider_key = "empty_ai_test_double"
    provider_label = "Empty AI evaluation test double"
    provider_version = "test-v1"
    extraction_mode = "ai"

    def extract(self, request):
        return self.result(identity={}, profile={}, evidence=[], warnings=[])


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
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertIn("coverage_percent", result["evidence_coverage"])
        self.assertTrue(result["comparisons"])

    def test_full_run_is_offline_and_has_no_forbidden_claims(self):
        report = run_evaluation()

        self.assertEqual(report["provider"], "deterministic")
        self.assertEqual(report["provider_metadata"]["mode"], "deterministic")
        self.assertGreaterEqual(report["case_count"], 3)
        self.assertEqual(report["critical_passed"], report["critical_total"])
        self.assertEqual(report["forbidden_hit_count"], 0)
        self.assertGreater(report["agreement_percent"], 65)
        self.assertGreaterEqual(report["evidence_coverage_percent"], 0)

    def test_injected_ai_provider_uses_same_cases_without_network(self):
        report = run_evaluation(extractor=ExpectedCaseExtractor())

        self.assertEqual(report["provider"], "openai_test_double")
        self.assertEqual(report["provider_metadata"]["mode"], "ai")
        self.assertEqual(report["agreement_percent"], 100.0)
        self.assertEqual(report["evidence_coverage_percent"], 100.0)
        self.assertEqual(report["under_extraction_count"], 0)
        self.assertEqual(report["over_extraction_count"], 0)
        self.assertEqual(report["forbidden_hit_count"], 0)

    def test_comparison_reports_provider_deltas_and_case_results(self):
        report = run_comparison(candidate_extractor=ExpectedCaseExtractor())

        self.assertEqual(report["baseline"]["provider"], "deterministic")
        self.assertEqual(report["candidate"]["provider"], "openai_test_double")
        self.assertGreaterEqual(report["summary"]["agreement_delta_percent"], 0)
        self.assertGreaterEqual(
            report["summary"]["evidence_coverage_delta_percent"],
            0,
        )
        self.assertEqual(len(report["cases"]), report["baseline"]["case_count"])

    def test_comparison_classifies_weaker_candidate_as_regression(self):
        baseline = run_evaluation(extractor=ExpectedCaseExtractor())
        candidate = run_evaluation(extractor=EmptyAIExtractor())

        report = compare_evaluation_runs(baseline, candidate)

        self.assertGreater(report["summary"]["regression_count"], 0)
        self.assertTrue(report["regressions"])
        self.assertLess(report["summary"]["agreement_delta_percent"], 0)

    def test_management_command_writes_default_offline_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "resume-evaluation.json"
            with patch(
                "candidate_profile.management.commands.evaluate_resume_extraction."
                "OpenAIResumeExtractor",
                side_effect=AssertionError("OpenAI must not initialize in default mode."),
            ):
                call_command(
                    "evaluate_resume_extraction",
                    output=str(output_path),
                    minimum_agreement=60,
                )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["provider"], "deterministic")
            self.assertGreaterEqual(report["case_count"], 3)

    def test_openai_modes_require_explicit_live_acknowledgement(self):
        with self.assertRaisesMessage(CommandError, "--allow-live-openai"):
            call_command(
                "evaluate_resume_extraction",
                provider="compare",
            )

    def test_compare_command_accepts_injected_provider_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "comparison.json"
            with patch(
                "candidate_profile.management.commands.evaluate_resume_extraction."
                "OpenAIResumeExtractor",
                return_value=ExpectedCaseExtractor(),
            ):
                call_command(
                    "evaluate_resume_extraction",
                    provider="compare",
                    allow_live_openai=True,
                    minimum_agreement=80,
                    output=str(output_path),
                )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["candidate"]["provider"], "openai_test_double")
            self.assertEqual(report["baseline"]["provider"], "deterministic")
