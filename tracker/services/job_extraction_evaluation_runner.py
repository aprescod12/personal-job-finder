from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .job_extraction import JobExtractionRequest, execute_job_extractor
from .job_extraction_evaluation import (
    DEFAULT_CASES_ROOT,
    JobExtractionEvaluationCase,
    discover_evaluation_cases,
)
from .job_intake import DeterministicJobExtractor


EVALUATION_RUNNER_VERSION = "job-extraction-evaluator-v1"
SUPPORTED_PROVIDER = "deterministic"

STATUS_EXACT = "exact"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"
STATUS_UNEXPECTED = "unexpected"
STATUS_INCORRECT = "incorrect"

STATUS_ORDER = (
    STATUS_EXACT,
    STATUS_PARTIAL,
    STATUS_MISSING,
    STATUS_UNEXPECTED,
    STATUS_INCORRECT,
)

JOB_FIELD_KINDS = {
    "title": "text",
    "company": "text",
    "location": "text",
    "employment_type": "typed",
    "work_arrangement": "typed",
    "salary_text": "text",
    "date_posted": "typed",
    "deadline_status": "typed",
    "application_deadline": "typed",
}

REQUIREMENT_FIELD_KINDS = {
    "role_family": "text",
    "seniority_level": "typed",
    "industry_tags": "list",
    "required_skills": "list",
    "preferred_skills": "list",
    "required_education": "list",
    "preferred_education": "list",
    "minimum_years_experience": "typed",
    "maximum_years_experience": "typed",
    "responsibilities": "list",
    "certifications": "list",
    "work_authorization_requirements": "list",
    "hard_disqualifiers": "list",
    "requirement_notes": "text",
}

# These fields can materially change whether a role is worth pursuing. The
# separate score is diagnostic only; it never becomes a candidate-job score.
ELIGIBILITY_SENSITIVE_FIELDS = {
    "job.title",
    "job.company",
    "job.location",
    "job.deadline_status",
    "job.application_deadline",
    "requirements.required_skills",
    "requirements.preferred_skills",
    "requirements.required_education",
    "requirements.minimum_years_experience",
    "requirements.maximum_years_experience",
    "requirements.work_authorization_requirements",
    "requirements.hard_disqualifiers",
}


@dataclass(frozen=True, slots=True)
class ItemMatch:
    expected: str
    actual: str
    similarity: float


@dataclass(slots=True)
class FieldComparison:
    path: str
    kind: str
    status: str
    score: float
    expected: Any
    actual: Any
    matched_items: list[ItemMatch] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    unexpected_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(self.score, 4)
        return payload


@dataclass(slots=True)
class CaseEvaluation:
    case_id: str
    title: str
    role_category: str
    provider_key: str
    provider_label: str
    provider_version: str
    extraction_mode: str
    field_agreement_percent: float
    eligibility_sensitive_agreement_percent: float
    status_counts: dict[str, int]
    comparisons: list[FieldComparison]
    extractor_warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "role_category": self.role_category,
            "provider": {
                "key": self.provider_key,
                "label": self.provider_label,
                "version": self.provider_version,
                "mode": self.extraction_mode,
            },
            "field_agreement_percent": round(self.field_agreement_percent, 2),
            "eligibility_sensitive_agreement_percent": round(
                self.eligibility_sensitive_agreement_percent,
                2,
            ),
            "status_counts": dict(self.status_counts),
            "comparisons": [comparison.to_dict() for comparison in self.comparisons],
            "extractor_warnings": list(self.extractor_warnings),
        }


@dataclass(slots=True)
class EvaluationRun:
    runner_version: str
    provider: str
    generated_at: str
    case_count: int
    field_count: int
    field_agreement_percent: float
    eligibility_sensitive_agreement_percent: float
    status_counts: dict[str, int]
    field_summary: dict[str, dict[str, Any]]
    cases: list[CaseEvaluation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runner_version": self.runner_version,
            "provider": self.provider,
            "generated_at": self.generated_at,
            "case_count": self.case_count,
            "field_count": self.field_count,
            "field_agreement_percent": round(self.field_agreement_percent, 2),
            "eligibility_sensitive_agreement_percent": round(
                self.eligibility_sensitive_agreement_percent,
                2,
            ),
            "status_counts": dict(self.status_counts),
            "field_summary": self.field_summary,
            "cases": [case.to_dict() for case in self.cases],
        }


_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(_WORD_RE.findall(text))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _text_similarity(expected: Any, actual: Any) -> float:
    expected_text = normalize_text(expected)
    actual_text = normalize_text(actual)
    if not expected_text and not actual_text:
        return 1.0
    if not expected_text or not actual_text:
        return 0.0
    if expected_text == actual_text:
        return 1.0

    expected_tokens = set(expected_text.split())
    actual_tokens = set(actual_text.split())
    intersection = len(expected_tokens & actual_tokens)
    if not intersection:
        token_f1 = 0.0
    else:
        precision = intersection / len(actual_tokens)
        recall = intersection / len(expected_tokens)
        token_f1 = 2 * precision * recall / (precision + recall)

    sequence_ratio = SequenceMatcher(None, expected_text, actual_text).ratio()
    containment = 0.0
    if expected_text in actual_text or actual_text in expected_text:
        containment = min(len(expected_text), len(actual_text)) / max(
            len(expected_text),
            len(actual_text),
        )
    return max(token_f1, sequence_ratio, containment)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = value.splitlines()
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        values = list(value)
    else:
        values = [value]

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip()
        normalized = normalize_text(text)
        if text and normalized not in seen:
            cleaned.append(text)
            seen.add(normalized)
    return cleaned


def compare_typed_field(path: str, expected: Any, actual: Any) -> FieldComparison:
    expected_blank = _is_blank(expected)
    actual_blank = _is_blank(actual)
    if expected_blank and actual_blank:
        status, score = STATUS_EXACT, 1.0
    elif not expected_blank and actual_blank:
        status, score = STATUS_MISSING, 0.0
    elif expected_blank and not actual_blank:
        status, score = STATUS_UNEXPECTED, 0.0
    elif expected == actual:
        status, score = STATUS_EXACT, 1.0
    else:
        status, score = STATUS_INCORRECT, 0.0
    return FieldComparison(path, "typed", status, score, expected, actual)


def compare_text_field(path: str, expected: Any, actual: Any) -> FieldComparison:
    expected_blank = _is_blank(expected)
    actual_blank = _is_blank(actual)
    if expected_blank and actual_blank:
        return FieldComparison(path, "text", STATUS_EXACT, 1.0, expected, actual)
    if not expected_blank and actual_blank:
        return FieldComparison(path, "text", STATUS_MISSING, 0.0, expected, actual)
    if expected_blank and not actual_blank:
        return FieldComparison(path, "text", STATUS_UNEXPECTED, 0.0, expected, actual)

    similarity = _text_similarity(expected, actual)
    if similarity >= 0.98:
        status = STATUS_EXACT
    elif similarity >= 0.55:
        status = STATUS_PARTIAL
    else:
        status = STATUS_INCORRECT
    return FieldComparison(path, "text", status, similarity, expected, actual)


def compare_list_field(path: str, expected: Any, actual: Any) -> FieldComparison:
    expected_items = _as_list(expected)
    actual_items = _as_list(actual)
    if not expected_items and not actual_items:
        return FieldComparison(path, "list", STATUS_EXACT, 1.0, expected_items, actual_items)
    if expected_items and not actual_items:
        return FieldComparison(
            path,
            "list",
            STATUS_MISSING,
            0.0,
            expected_items,
            actual_items,
            missing_items=expected_items,
        )
    if not expected_items and actual_items:
        return FieldComparison(
            path,
            "list",
            STATUS_UNEXPECTED,
            0.0,
            expected_items,
            actual_items,
            unexpected_items=actual_items,
        )

    candidates: list[tuple[float, int, int]] = []
    for expected_index, expected_item in enumerate(expected_items):
        for actual_index, actual_item in enumerate(actual_items):
            similarity = _text_similarity(expected_item, actual_item)
            if similarity >= 0.55:
                candidates.append((similarity, expected_index, actual_index))
    candidates.sort(reverse=True)

    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    matches: list[ItemMatch] = []
    for similarity, expected_index, actual_index in candidates:
        if expected_index in matched_expected or actual_index in matched_actual:
            continue
        matched_expected.add(expected_index)
        matched_actual.add(actual_index)
        matches.append(
            ItemMatch(
                expected=expected_items[expected_index],
                actual=actual_items[actual_index],
                similarity=round(similarity, 4),
            )
        )

    missing_items = [
        item for index, item in enumerate(expected_items) if index not in matched_expected
    ]
    unexpected_items = [
        item for index, item in enumerate(actual_items) if index not in matched_actual
    ]
    matched_weight = sum(match.similarity for match in matches)
    precision = matched_weight / len(actual_items)
    recall = matched_weight / len(expected_items)
    score = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    normalized_expected = {normalize_text(item) for item in expected_items}
    normalized_actual = {normalize_text(item) for item in actual_items}
    if normalized_expected == normalized_actual:
        status = STATUS_EXACT
        score = 1.0
    elif matches:
        status = STATUS_PARTIAL
    else:
        status = STATUS_INCORRECT

    return FieldComparison(
        path,
        "list",
        status,
        score,
        expected_items,
        actual_items,
        matched_items=matches,
        missing_items=missing_items,
        unexpected_items=unexpected_items,
    )


def _compare_field(path: str, kind: str, expected: Any, actual: Any) -> FieldComparison:
    if kind == "typed":
        return compare_typed_field(path, expected, actual)
    if kind == "list":
        return compare_list_field(path, expected, actual)
    return compare_text_field(path, expected, actual)


def _case_comparisons(
    case: JobExtractionEvaluationCase,
    extraction: dict[str, Any],
) -> list[FieldComparison]:
    comparisons: list[FieldComparison] = []
    actual_job = extraction.get("job", {})
    for name, kind in JOB_FIELD_KINDS.items():
        comparisons.append(
            _compare_field(
                f"job.{name}",
                kind,
                case.expected_job.get(name),
                actual_job.get(name),
            )
        )

    actual_requirements = extraction.get("requirements", {})
    for name, kind in REQUIREMENT_FIELD_KINDS.items():
        actual_name = "industry" if name == "industry_tags" else name
        comparisons.append(
            _compare_field(
                f"requirements.{name}",
                kind,
                case.expected_requirements.get(name),
                actual_requirements.get(actual_name),
            )
        )
    return comparisons


def _average_score(comparisons: list[FieldComparison]) -> float:
    if not comparisons:
        return 0.0
    return 100 * sum(item.score for item in comparisons) / len(comparisons)


def _status_counts(comparisons: list[FieldComparison]) -> dict[str, int]:
    return {
        status: sum(1 for item in comparisons if item.status == status)
        for status in STATUS_ORDER
    }


def evaluate_case(
    case: JobExtractionEvaluationCase,
    *,
    extractor: DeterministicJobExtractor | None = None,
) -> CaseEvaluation:
    active_extractor = extractor or DeterministicJobExtractor()
    request = JobExtractionRequest(listing_text=case.listing_text)
    extraction = execute_job_extractor(request, active_extractor).to_dict()
    comparisons = _case_comparisons(case, extraction)
    sensitive = [
        item for item in comparisons if item.path in ELIGIBILITY_SENSITIVE_FIELDS
    ]
    provider = extraction["provider"]
    return CaseEvaluation(
        case_id=case.case_id,
        title=case.title,
        role_category=case.role_category,
        provider_key=str(provider["key"]),
        provider_label=str(provider["label"]),
        provider_version=str(provider["version"]),
        extraction_mode=str(provider["mode"]),
        field_agreement_percent=_average_score(comparisons),
        eligibility_sensitive_agreement_percent=_average_score(sensitive),
        status_counts=_status_counts(comparisons),
        comparisons=comparisons,
        extractor_warnings=list(extraction.get("warnings", [])),
    )


def _field_summary(cases: list[CaseEvaluation]) -> dict[str, dict[str, Any]]:
    paths = [
        *(f"job.{name}" for name in JOB_FIELD_KINDS),
        *(f"requirements.{name}" for name in REQUIREMENT_FIELD_KINDS),
    ]
    summary: dict[str, dict[str, Any]] = {}
    for path in paths:
        comparisons = [
            comparison
            for case in cases
            for comparison in case.comparisons
            if comparison.path == path
        ]
        summary[path] = {
            "agreement_percent": round(_average_score(comparisons), 2),
            "status_counts": _status_counts(comparisons),
        }
    return summary


def evaluate_cases(
    *,
    provider: str = SUPPORTED_PROVIDER,
    cases_root: str | Path = DEFAULT_CASES_ROOT,
    case_ids: Iterable[str] | None = None,
    generated_at: datetime | None = None,
) -> EvaluationRun:
    if provider != SUPPORTED_PROVIDER:
        raise ValueError(
            f"Unsupported evaluation provider: {provider}. "
            f"Only {SUPPORTED_PROVIDER} is available in Step 3D.4."
        )

    selected_ids = set(case_ids or [])
    discovered = discover_evaluation_cases(cases_root)
    if selected_ids:
        discovered = [case for case in discovered if case.case_id in selected_ids]
        missing = selected_ids - {case.case_id for case in discovered}
        if missing:
            raise ValueError(f"Unknown evaluation case(s): {', '.join(sorted(missing))}.")
    if not discovered:
        raise ValueError("No evaluation cases were selected.")

    case_results = [evaluate_case(case) for case in discovered]
    comparisons = [
        comparison for case in case_results for comparison in case.comparisons
    ]
    sensitive = [
        comparison
        for comparison in comparisons
        if comparison.path in ELIGIBILITY_SENSITIVE_FIELDS
    ]
    timestamp = generated_at or datetime.now(timezone.utc)
    return EvaluationRun(
        runner_version=EVALUATION_RUNNER_VERSION,
        provider=provider,
        generated_at=timestamp.isoformat(),
        case_count=len(case_results),
        field_count=len(comparisons),
        field_agreement_percent=_average_score(comparisons),
        eligibility_sensitive_agreement_percent=_average_score(sensitive),
        status_counts=_status_counts(comparisons),
        field_summary=_field_summary(case_results),
        cases=case_results,
    )


def render_json_report(run: EvaluationRun) -> str:
    return json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n"


def _display(value: Any) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value).replace("\n", "; ")


def render_markdown_report(run: EvaluationRun) -> str:
    lines = [
        "# Deterministic Job Extraction Baseline",
        "",
        f"- Runner: `{run.runner_version}`",
        f"- Provider: `{run.provider}`",
        f"- Generated: `{run.generated_at}`",
        f"- Cases: **{run.case_count}**",
        f"- Compared fields: **{run.field_count}**",
        f"- Field agreement: **{run.field_agreement_percent:.2f}%**",
        (
            "- Eligibility-sensitive field agreement: "
            f"**{run.eligibility_sensitive_agreement_percent:.2f}%**"
        ),
        "",
        "> These percentages are deterministic benchmark agreement measures, not "
        "statistical accuracy claims and not candidate-job match scores.",
        "",
        "## Status totals",
        "",
        "| Exact | Partial | Missing | Unexpected | Incorrect |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {run.status_counts[STATUS_EXACT]} | "
            f"{run.status_counts[STATUS_PARTIAL]} | "
            f"{run.status_counts[STATUS_MISSING]} | "
            f"{run.status_counts[STATUS_UNEXPECTED]} | "
            f"{run.status_counts[STATUS_INCORRECT]} |"
        ),
        "",
        "## Case summary",
        "",
        "| Case | Role category | Field agreement | Sensitive agreement | Exact | Partial | Missing | Unexpected | Incorrect |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in run.cases:
        counts = case.status_counts
        lines.append(
            f"| `{case.case_id}` | {case.role_category} | "
            f"{case.field_agreement_percent:.2f}% | "
            f"{case.eligibility_sensitive_agreement_percent:.2f}% | "
            f"{counts[STATUS_EXACT]} | {counts[STATUS_PARTIAL]} | "
            f"{counts[STATUS_MISSING]} | {counts[STATUS_UNEXPECTED]} | "
            f"{counts[STATUS_INCORRECT]} |"
        )

    lines.extend(
        [
            "",
            "## Field summary",
            "",
            "| Field | Agreement | Exact | Partial | Missing | Unexpected | Incorrect |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for path, summary in run.field_summary.items():
        counts = summary["status_counts"]
        lines.append(
            f"| `{path}` | {summary['agreement_percent']:.2f}% | "
            f"{counts[STATUS_EXACT]} | {counts[STATUS_PARTIAL]} | "
            f"{counts[STATUS_MISSING]} | {counts[STATUS_UNEXPECTED]} | "
            f"{counts[STATUS_INCORRECT]} |"
        )

    lines.extend(["", "## Case details", ""])
    for case in run.cases:
        lines.extend(
            [
                f"### {case.case_id}",
                "",
                f"**{case.title}**",
                "",
                f"Extractor: `{case.provider_version}`",
                "",
                "| Field | Status | Score | Expected | Actual |",
                "|---|---|---:|---|---|",
            ]
        )
        for comparison in case.comparisons:
            lines.append(
                f"| `{comparison.path}` | {comparison.status} | "
                f"{comparison.score:.2f} | {_display(comparison.expected)} | "
                f"{_display(comparison.actual)} |"
            )
        if case.extractor_warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning}" for warning in case.extractor_warnings)
        lines.append("")

    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "This report evaluates extraction output against stored ground truth. It does not:",
            "",
            "- decide candidate eligibility,",
            "- rank jobs,",
            "- change the production matcher,",
            "- approve an intake draft,",
            "- or call an external model provider.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(run: EvaluationRun, *, output: str | Path, report_format: str) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if report_format == "json":
        content = render_json_report(run)
    elif report_format == "markdown":
        content = render_markdown_report(run)
    else:
        raise ValueError(f"Unsupported report format: {report_format}.")
    destination.write_text(content, encoding="utf-8")
    return destination
