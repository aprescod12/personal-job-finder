from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings

from tracker.models import JobPosting, JobRequirement


CASE_SCHEMA_VERSION = "job-extraction-evaluation-case-v1"
DEFAULT_CASES_ROOT = (
    Path(settings.BASE_DIR) / "docs" / "evaluations" / "job-processing" / "cases"
)
GROUND_TRUTH_FILENAME = "ground-truth.json"


class EvaluationCaseError(ValueError):
    """Raised when an extraction evaluation case is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class JobExtractionEvaluationCase:
    case_id: str
    title: str
    role_category: str
    directory: Path
    listing_text: str
    ground_truth: dict[str, Any]

    @property
    def expected_job(self) -> dict[str, Any]:
        return self.ground_truth["expected"]["job"]

    @property
    def expected_requirements(self) -> dict[str, Any]:
        return self.ground_truth["expected"]["requirements"]

    @property
    def critical_checks(self) -> list[dict[str, Any]]:
        return self.ground_truth["critical_checks"]


_TOP_LEVEL_KEYS = {
    "schema_version",
    "case_id",
    "title",
    "role_category",
    "source",
    "expected",
    "critical_checks",
    "known_traps",
}
_SOURCE_KEYS = {
    "company",
    "requisition_id",
    "captured_date",
    "listing_file",
    "notes_file",
    "source_url",
}
_EXPECTED_KEYS = {"job", "requirements", "supplemental"}
_JOB_KEYS = {
    "title",
    "company",
    "location",
    "employment_type",
    "work_arrangement",
    "salary_text",
    "date_posted",
    "deadline_status",
    "application_deadline",
}
_REQUIREMENT_KEYS = {
    "role_family",
    "seniority_level",
    "industry_tags",
    "required_skills",
    "preferred_skills",
    "required_education",
    "preferred_education",
    "minimum_years_experience",
    "maximum_years_experience",
    "responsibilities",
    "certifications",
    "work_authorization_requirements",
    "hard_disqualifiers",
    "requirement_notes",
}
_SUPPLEMENTAL_KEYS = {
    "employment_category",
    "schedule",
    "employment_term",
    "requisition_id",
    "openings",
    "relocation",
    "travel",
    "driving_license_required",
}
_CRITICAL_CHECK_KEYS = {
    "id",
    "severity",
    "description",
    "expected_behavior",
    "evidence_quotes",
}
_KNOWN_TRAP_KEYS = {"id", "description", "forbidden_interpretations"}
_ALLOWED_SEVERITIES = {"critical", "major", "minor"}


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationCaseError(f"{context} must be a JSON object.")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing:
        raise EvaluationCaseError(
            f"{context} is missing keys: {', '.join(sorted(missing))}."
        )
    if extra:
        raise EvaluationCaseError(
            f"{context} has unsupported keys: {', '.join(sorted(extra))}."
        )


def _text(value: Any, context: str, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise EvaluationCaseError(f"{context} must be text.")
    cleaned = value.strip()
    if not cleaned and not allow_blank:
        raise EvaluationCaseError(f"{context} cannot be blank.")
    return cleaned


def _text_list(value: Any, context: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise EvaluationCaseError(f"{context} must be a JSON array.")
    if not value and not allow_empty:
        raise EvaluationCaseError(f"{context} cannot be empty.")

    cleaned: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _text(item, f"{context}[{index}]")
        normalized = text.casefold()
        if normalized in seen:
            raise EvaluationCaseError(f"{context} contains duplicate value: {text}.")
        seen.add(normalized)
        cleaned.append(text)
    return cleaned


def _optional_years(value: Any, context: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 60:
        raise EvaluationCaseError(f"{context} must be null or an integer from 0 to 60.")
    return value


def _optional_iso_date(value: Any, context: str) -> str | None:
    if value is None:
        return None
    text = _text(value, context)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationCaseError(f"{context} must use YYYY-MM-DD or null.") from exc
    return text


def _safe_case_filename(value: Any, context: str) -> str:
    filename = _text(value, context)
    path = Path(filename)
    if path.is_absolute() or path.name != filename or ".." in path.parts:
        raise EvaluationCaseError(f"{context} must be a file inside the case directory.")
    return filename


def _validate_source(source: dict[str, Any]) -> tuple[str, str]:
    _exact_keys(source, _SOURCE_KEYS, "source")
    _text(source["company"], "source.company")
    _text(source["requisition_id"], "source.requisition_id", allow_blank=True)
    _optional_iso_date(source["captured_date"], "source.captured_date")
    listing_file = _safe_case_filename(source["listing_file"], "source.listing_file")
    notes_file = _safe_case_filename(source["notes_file"], "source.notes_file")
    _text(source["source_url"], "source.source_url", allow_blank=True)
    return listing_file, notes_file


def _validate_job(job: dict[str, Any]) -> None:
    _exact_keys(job, _JOB_KEYS, "expected.job")
    for key in ("title", "company", "location"):
        _text(job[key], f"expected.job.{key}")
    _text(job["salary_text"], "expected.job.salary_text", allow_blank=True)

    employment_types = set(JobPosting.EmploymentType.values)
    if job["employment_type"] not in employment_types:
        raise EvaluationCaseError("expected.job.employment_type is not a model enum.")

    work_arrangements = set(JobPosting.WorkArrangement.values)
    if job["work_arrangement"] not in work_arrangements:
        raise EvaluationCaseError("expected.job.work_arrangement is not a model enum.")

    deadline_statuses = set(JobPosting.DeadlineStatus.values)
    if job["deadline_status"] not in deadline_statuses:
        raise EvaluationCaseError("expected.job.deadline_status is not a model enum.")

    _optional_iso_date(job["date_posted"], "expected.job.date_posted")
    deadline = _optional_iso_date(
        job["application_deadline"],
        "expected.job.application_deadline",
    )
    if job["deadline_status"] == JobPosting.DeadlineStatus.CONFIRMED and not deadline:
        raise EvaluationCaseError(
            "A confirmed expected deadline must include application_deadline."
        )
    if job["deadline_status"] != JobPosting.DeadlineStatus.CONFIRMED and deadline:
        raise EvaluationCaseError(
            "An expected deadline date requires deadline_status=confirmed."
        )


def _validate_requirements(requirements: dict[str, Any]) -> None:
    _exact_keys(requirements, _REQUIREMENT_KEYS, "expected.requirements")
    _text(requirements["role_family"], "expected.requirements.role_family")
    if requirements["seniority_level"] not in set(JobRequirement.SeniorityLevel.values):
        raise EvaluationCaseError(
            "expected.requirements.seniority_level is not a model enum."
        )

    for key in (
        "industry_tags",
        "required_skills",
        "preferred_skills",
        "required_education",
        "preferred_education",
        "responsibilities",
        "certifications",
        "work_authorization_requirements",
        "hard_disqualifiers",
    ):
        _text_list(requirements[key], f"expected.requirements.{key}")

    minimum = _optional_years(
        requirements["minimum_years_experience"],
        "expected.requirements.minimum_years_experience",
    )
    maximum = _optional_years(
        requirements["maximum_years_experience"],
        "expected.requirements.maximum_years_experience",
    )
    if minimum is not None and maximum is not None and maximum < minimum:
        raise EvaluationCaseError("Expected maximum experience cannot be below minimum.")
    _text(
        requirements["requirement_notes"],
        "expected.requirements.requirement_notes",
        allow_blank=True,
    )


def _validate_supplemental(supplemental: dict[str, Any]) -> None:
    _exact_keys(supplemental, _SUPPLEMENTAL_KEYS, "expected.supplemental")
    for key in _SUPPLEMENTAL_KEYS - {"openings", "driving_license_required"}:
        _text(
            supplemental[key],
            f"expected.supplemental.{key}",
            allow_blank=True,
        )
    openings = supplemental["openings"]
    if isinstance(openings, bool) or not isinstance(openings, int) or openings < 0:
        raise EvaluationCaseError("expected.supplemental.openings must be zero or more.")
    if not isinstance(supplemental["driving_license_required"], bool):
        raise EvaluationCaseError(
            "expected.supplemental.driving_license_required must be true or false."
        )


def _validate_named_records(
    records: Any,
    *,
    context: str,
    expected_keys: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise EvaluationCaseError(f"{context} must be a nonempty JSON array.")
    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        record = _mapping(item, f"{context}[{index}]")
        _exact_keys(record, expected_keys, f"{context}[{index}]")
        record_id = _text(record["id"], f"{context}[{index}].id")
        if record_id in seen_ids:
            raise EvaluationCaseError(f"{context} contains duplicate id: {record_id}.")
        seen_ids.add(record_id)
        _text(record["description"], f"{context}[{index}].description")
        validated.append(record)
    return validated


def validate_evaluation_ground_truth(
    payload: dict[str, Any],
    *,
    case_directory: Path,
    listing_text: str,
) -> None:
    _exact_keys(payload, _TOP_LEVEL_KEYS, "root")
    if payload["schema_version"] != CASE_SCHEMA_VERSION:
        raise EvaluationCaseError(
            f"schema_version must be {CASE_SCHEMA_VERSION}."
        )

    case_id = _text(payload["case_id"], "case_id")
    if case_id != case_directory.name:
        raise EvaluationCaseError(
            "case_id must exactly match the case directory name."
        )
    _text(payload["title"], "title")
    _text(payload["role_category"], "role_category")

    source = _mapping(payload["source"], "source")
    _validate_source(source)

    expected = _mapping(payload["expected"], "expected")
    _exact_keys(expected, _EXPECTED_KEYS, "expected")
    _validate_job(_mapping(expected["job"], "expected.job"))
    _validate_requirements(
        _mapping(expected["requirements"], "expected.requirements")
    )
    _validate_supplemental(
        _mapping(expected["supplemental"], "expected.supplemental")
    )

    checks = _validate_named_records(
        payload["critical_checks"],
        context="critical_checks",
        expected_keys=_CRITICAL_CHECK_KEYS,
    )
    for index, check in enumerate(checks):
        severity = _text(check["severity"], f"critical_checks[{index}].severity")
        if severity not in _ALLOWED_SEVERITIES:
            raise EvaluationCaseError(
                f"critical_checks[{index}].severity is unsupported."
            )
        _text(
            check["expected_behavior"],
            f"critical_checks[{index}].expected_behavior",
        )
        quotes = _text_list(
            check["evidence_quotes"],
            f"critical_checks[{index}].evidence_quotes",
            allow_empty=False,
        )
        for quote in quotes:
            if quote not in listing_text:
                raise EvaluationCaseError(
                    f"Evidence quote for {check['id']} is absent from listing.txt: {quote}"
                )

    traps = _validate_named_records(
        payload["known_traps"],
        context="known_traps",
        expected_keys=_KNOWN_TRAP_KEYS,
    )
    for index, trap in enumerate(traps):
        _text_list(
            trap["forbidden_interpretations"],
            f"known_traps[{index}].forbidden_interpretations",
            allow_empty=False,
        )


def load_evaluation_case(case_directory: str | Path) -> JobExtractionEvaluationCase:
    directory = Path(case_directory).resolve()
    ground_truth_path = directory / GROUND_TRUTH_FILENAME
    if not ground_truth_path.is_file():
        raise EvaluationCaseError(f"Missing {GROUND_TRUTH_FILENAME} in {directory}.")

    try:
        payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationCaseError(
            f"Invalid JSON in {ground_truth_path}: {exc.msg}."
        ) from exc
    payload = _mapping(payload, "root")

    source = _mapping(payload.get("source"), "source")
    listing_filename, notes_filename = _validate_source(source)
    listing_path = directory / listing_filename
    notes_path = directory / notes_filename
    if not listing_path.is_file():
        raise EvaluationCaseError(f"Missing listing file: {listing_path}.")
    if not notes_path.is_file():
        raise EvaluationCaseError(f"Missing notes file: {notes_path}.")

    listing_text = listing_path.read_text(encoding="utf-8").strip()
    if not listing_text:
        raise EvaluationCaseError(f"Listing file is blank: {listing_path}.")

    validate_evaluation_ground_truth(
        payload,
        case_directory=directory,
        listing_text=listing_text,
    )
    return JobExtractionEvaluationCase(
        case_id=payload["case_id"],
        title=payload["title"],
        role_category=payload["role_category"],
        directory=directory,
        listing_text=listing_text,
        ground_truth=payload,
    )


def iter_evaluation_case_directories(
    root: str | Path | None = None,
) -> list[Path]:
    cases_root = Path(root or DEFAULT_CASES_ROOT).resolve()
    if not cases_root.is_dir():
        return []
    return sorted(
        path
        for path in cases_root.iterdir()
        if path.is_dir() and (path / GROUND_TRUTH_FILENAME).is_file()
    )


def discover_evaluation_cases(
    root: str | Path | None = None,
) -> list[JobExtractionEvaluationCase]:
    return [
        load_evaluation_case(directory)
        for directory in iter_evaluation_case_directories(root)
    ]
