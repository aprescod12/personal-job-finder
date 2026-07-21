import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from .services.job_extraction_evaluation import (
    CASE_SCHEMA_VERSION,
    DEFAULT_CASES_ROOT,
    EvaluationCaseError,
    discover_evaluation_cases,
    load_evaluation_case,
)


CASE_ID = "case-001-organon-medical-device-coop"
EXPECTED_CASE_IDS = {
    CASE_ID,
    "case-002-embedded-firmware-entry-level",
    "case-003-quality-validation-engineer",
    "case-004-medical-device-software",
    "case-005-general-software-poor-format",
    "case-006-ambiguous-sponsorship",
    "case-007-citizenship-clearance",
}


class JobExtractionEvaluationCaseTests(SimpleTestCase):
    @property
    def case_directory(self):
        return DEFAULT_CASES_ROOT / CASE_ID

    def _copy_case(self, root: Path) -> Path:
        destination = root / CASE_ID
        shutil.copytree(self.case_directory, destination)
        return destination

    @staticmethod
    def _read_ground_truth(directory: Path) -> dict:
        return json.loads(
            (directory / "ground-truth.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def _write_ground_truth(directory: Path, payload: dict) -> None:
        (directory / "ground-truth.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_organon_case_loads_as_machine_readable_ground_truth(self):
        case = load_evaluation_case(self.case_directory)

        self.assertEqual(case.case_id, CASE_ID)
        self.assertEqual(
            case.ground_truth["schema_version"],
            CASE_SCHEMA_VERSION,
        )
        self.assertEqual(case.expected_job["company"], "Organon")
        self.assertEqual(case.expected_job["employment_type"], "internship")
        self.assertEqual(case.expected_job["deadline_status"], "not_stated")
        self.assertIsNone(
            case.expected_requirements["minimum_years_experience"]
        )
        self.assertIn(
            "VISA Sponsorship: No",
            case.expected_requirements["work_authorization_requirements"],
        )
        self.assertIn("Requisition ID:R540092", case.listing_text)
        self.assertGreaterEqual(len(case.critical_checks), 8)

    def test_discovery_returns_the_complete_initial_dataset(self):
        cases = discover_evaluation_cases()
        case_ids = {case.case_id for case in cases}

        self.assertEqual(case_ids, EXPECTED_CASE_IDS)
        self.assertEqual(len(cases), 7)

    def test_dataset_preserves_authorization_contrasts(self):
        cases = {case.case_id: case for case in discover_evaluation_cases()}

        no_policy = cases["case-003-quality-validation-engineer"]
        ambiguous = cases["case-006-ambiguous-sponsorship"]
        explicit = cases["case-007-citizenship-clearance"]

        self.assertEqual(
            no_policy.expected_requirements["work_authorization_requirements"],
            [],
        )
        self.assertEqual(
            ambiguous.expected_requirements["hard_disqualifiers"],
            [],
        )
        self.assertIn(
            "Sponsorship decisions are case by case and not guaranteed",
            ambiguous.expected_requirements["work_authorization_requirements"],
        )
        self.assertIn(
            "United States citizenship required",
            explicit.expected_requirements["hard_disqualifiers"],
        )
        self.assertIn(
            "Visa sponsorship unavailable",
            explicit.expected_requirements["hard_disqualifiers"],
        )

    def test_management_command_validates_the_case_library(self):
        stdout = StringIO()

        call_command("validate_job_extraction_cases", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn(CASE_ID, output)
        self.assertIn("Validated 7 job extraction evaluation case(s).", output)

    def test_evidence_quote_must_exist_in_the_source_listing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            case_directory = self._copy_case(Path(temporary_directory))
            payload = self._read_ground_truth(case_directory)
            payload["critical_checks"][0]["evidence_quotes"] = [
                "This sentence is not in the listing."
            ]
            self._write_ground_truth(case_directory, payload)

            with self.assertRaisesMessage(
                EvaluationCaseError,
                "is absent from listing.txt",
            ):
                load_evaluation_case(case_directory)

    def test_case_id_must_match_the_directory_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            case_directory = self._copy_case(Path(temporary_directory))
            payload = self._read_ground_truth(case_directory)
            payload["case_id"] = "case-999-wrong-name"
            self._write_ground_truth(case_directory, payload)

            with self.assertRaisesMessage(
                EvaluationCaseError,
                "case_id must exactly match",
            ):
                load_evaluation_case(case_directory)

    def test_model_enum_values_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            case_directory = self._copy_case(Path(temporary_directory))
            payload = self._read_ground_truth(case_directory)
            payload["expected"]["job"]["employment_type"] = "co_op"
            self._write_ground_truth(case_directory, payload)

            with self.assertRaisesMessage(
                EvaluationCaseError,
                "employment_type is not a model enum",
            ):
                load_evaluation_case(case_directory)

    def test_case_files_cannot_escape_the_case_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            case_directory = self._copy_case(Path(temporary_directory))
            payload = self._read_ground_truth(case_directory)
            payload["source"]["listing_file"] = "../listing.txt"
            self._write_ground_truth(case_directory, payload)

            with self.assertRaisesMessage(
                EvaluationCaseError,
                "must be a file inside the case directory",
            ):
                load_evaluation_case(case_directory)

    def test_duplicate_expected_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            case_directory = self._copy_case(Path(temporary_directory))
            payload = self._read_ground_truth(case_directory)
            payload["expected"]["requirements"]["preferred_skills"] = [
                "SolidWorks",
                "solidworks",
            ]
            self._write_ground_truth(case_directory, payload)

            with self.assertRaisesMessage(
                EvaluationCaseError,
                "contains duplicate value",
            ):
                load_evaluation_case(case_directory)
