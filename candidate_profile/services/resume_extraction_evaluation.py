from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Any

from django.conf import settings

from .resume_deterministic import DeterministicResumeExtractor
from .resume_extraction import (
    BaseResumeExtractor,
    ResumeExtractionRequest,
    execute_resume_extractor,
)


CASE_SCHEMA_VERSION = "resume-extraction-evaluation-case-v1"
RUNNER_VERSION = "resume-extraction-evaluator-v2"
COMPARISON_VERSION = "resume-extraction-provider-comparison-v1"
DEFAULT_CASES_ROOT = (
    Path(settings.BASE_DIR) / "docs" / "evaluations" / "resume-extraction" / "cases"
)

EVIDENCE_FIELD_BY_PATH = {
    "identity.full_name": "identity.full_name",
    "identity.email": "identity.email",
    "identity.phone": "identity.phone",
    "identity.location": "identity.location",
    "identity.links": "identity.links",
    "profile.professional_summary": "profile.professional_summary",
    "profile.education_headings": "profile.education",
    "profile.experience_headings": "profile.experience",
    "profile.project_headings": "profile.projects",
    "profile.skills": "profile.skills",
    "profile.certification_headings": "profile.certifications",
    "profile.leadership_headings": "profile.leadership",
}


class ResumeEvaluationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResumeEvaluationCase:
    case_id: str
    title: str
    category: str
    resume_text: str
    expected: dict[str, Any]
    critical_claims: list[dict[str, Any]]
    forbidden_claims: list[str]


_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(_WORD_RE.findall(text))


def similarity(expected: Any, actual: Any) -> float:
    left = normalize_text(expected)
    right = normalize_text(actual)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens)
    token_f1 = 0.0
    if overlap:
        precision = overlap / len(right_tokens)
        recall = overlap / len(left_tokens)
        token_f1 = 2 * precision * recall / (precision + recall)
    return max(token_f1, SequenceMatcher(None, left, right).ratio())


def _require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResumeEvaluationError(f"{context} must be an object.")
    return value


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResumeEvaluationError(f"{context} must be a list.")
    return value


def _require_text(value: Any, context: str, *, blank: bool = False) -> str:
    if not isinstance(value, str):
        raise ResumeEvaluationError(f"{context} must be text.")
    value = value.strip()
    if not value and not blank:
        raise ResumeEvaluationError(f"{context} cannot be blank.")
    return value


def load_case(directory: str | Path) -> ResumeEvaluationCase:
    directory = Path(directory)
    truth_path = directory / "ground-truth.json"
    resume_path = directory / "resume.txt"
    if not truth_path.is_file() or not resume_path.is_file():
        raise ResumeEvaluationError(f"Incomplete evaluation case: {directory}.")
    try:
        payload = json.loads(truth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResumeEvaluationError(f"Invalid JSON in {truth_path}: {exc.msg}.") from exc
    payload = _require_object(payload, "root")
    required = {
        "schema_version",
        "case_id",
        "title",
        "category",
        "expected",
        "critical_claims",
        "forbidden_claims",
    }
    if set(payload) != required:
        raise ResumeEvaluationError("Evaluation case has missing or unsupported root keys.")
    if payload["schema_version"] != CASE_SCHEMA_VERSION:
        raise ResumeEvaluationError(f"schema_version must be {CASE_SCHEMA_VERSION}.")
    case_id = _require_text(payload["case_id"], "case_id")
    if case_id != directory.name:
        raise ResumeEvaluationError("case_id must match its directory name.")
    resume_text = resume_path.read_text(encoding="utf-8").strip()
    if not resume_text:
        raise ResumeEvaluationError("resume.txt cannot be blank.")
    expected = _require_object(payload["expected"], "expected")
    if set(expected) != {"identity", "profile"}:
        raise ResumeEvaluationError("expected must contain identity and profile.")
    identity = _require_object(expected["identity"], "expected.identity")
    profile = _require_object(expected["profile"], "expected.profile")
    if set(identity) != {"full_name", "email", "phone", "location", "links"}:
        raise ResumeEvaluationError("expected.identity has invalid keys.")
    if set(profile) != {
        "professional_summary",
        "education_headings",
        "experience_headings",
        "project_headings",
        "skills",
        "certification_headings",
        "leadership_headings",
    }:
        raise ResumeEvaluationError("expected.profile has invalid keys.")
    _require_list(identity["links"], "expected.identity.links")
    for field in (
        "education_headings",
        "experience_headings",
        "project_headings",
        "skills",
        "certification_headings",
        "leadership_headings",
    ):
        _require_list(profile[field], f"expected.profile.{field}")
    critical_claims = _require_list(payload["critical_claims"], "critical_claims")
    for index, claim in enumerate(critical_claims):
        claim = _require_object(claim, f"critical_claims[{index}]")
        if set(claim) != {"path", "expected_text", "source_quote"}:
            raise ResumeEvaluationError("critical claim has invalid keys.")
        path = _require_text(claim["path"], "critical claim path")
        if path not in EVIDENCE_FIELD_BY_PATH:
            raise ResumeEvaluationError(f"Critical claim path is unsupported: {path}")
        quote = _require_text(claim["source_quote"], "critical claim source_quote")
        if quote not in resume_text:
            raise ResumeEvaluationError(f"Critical source quote is absent: {quote}")
    forbidden = [
        _require_text(item, f"forbidden_claims[{index}]")
        for index, item in enumerate(
            _require_list(payload["forbidden_claims"], "forbidden_claims")
        )
    ]
    return ResumeEvaluationCase(
        case_id=case_id,
        title=_require_text(payload["title"], "title"),
        category=_require_text(payload["category"], "category"),
        resume_text=resume_text,
        expected=expected,
        critical_claims=critical_claims,
        forbidden_claims=forbidden,
    )


def discover_cases(root: str | Path = DEFAULT_CASES_ROOT) -> list[ResumeEvaluationCase]:
    root = Path(root)
    if not root.is_dir():
        raise ResumeEvaluationError(f"Evaluation case directory does not exist: {root}.")
    cases = [load_case(path) for path in sorted(root.iterdir()) if path.is_dir()]
    if not cases:
        raise ResumeEvaluationError("No resume evaluation cases were found.")
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ResumeEvaluationError("Evaluation case IDs must be unique.")
    return cases


def _headings(entries: list[dict[str, Any]]) -> list[str]:
    return [
        str(entry.get("heading", "")).strip()
        for entry in entries
        if entry.get("heading")
    ]


def _list_score(
    expected: list[str],
    actual: list[str],
) -> tuple[float, list[str], list[str]]:
    if not expected and not actual:
        return 1.0, [], []
    unused = set(range(len(actual)))
    scores: list[float] = []
    missing: list[str] = []
    for expected_item in expected:
        candidates = [(similarity(expected_item, actual[i]), i) for i in unused]
        if not candidates:
            missing.append(expected_item)
            continue
        score, index = max(candidates)
        if score < 0.55:
            missing.append(expected_item)
            continue
        unused.remove(index)
        scores.append(score)
    unexpected = [actual[i] for i in sorted(unused)]
    denominator = max(len(expected), len(actual), 1)
    return sum(scores) / denominator, missing, unexpected


def _expected_fields(case: ResumeEvaluationCase) -> dict[str, Any]:
    expected_identity = case.expected["identity"]
    expected_profile = case.expected["profile"]
    return {
        "identity.full_name": expected_identity["full_name"],
        "identity.email": expected_identity["email"],
        "identity.phone": expected_identity["phone"],
        "identity.location": expected_identity["location"],
        "identity.links": expected_identity["links"],
        "profile.professional_summary": expected_profile["professional_summary"],
        "profile.education_headings": expected_profile["education_headings"],
        "profile.experience_headings": expected_profile["experience_headings"],
        "profile.project_headings": expected_profile["project_headings"],
        "profile.skills": expected_profile["skills"],
        "profile.certification_headings": expected_profile[
            "certification_headings"
        ],
        "profile.leadership_headings": expected_profile["leadership_headings"],
    }


def _actual_fields(result: dict[str, Any]) -> dict[str, Any]:
    identity = result["identity"]
    profile = result["profile"]
    return {
        "identity.full_name": identity["full_name"],
        "identity.email": identity["email"],
        "identity.phone": identity["phone"],
        "identity.location": identity["location"],
        "identity.links": identity["links"],
        "profile.professional_summary": profile["professional_summary"],
        "profile.education_headings": _headings(profile["education"]),
        "profile.experience_headings": _headings(profile["experience"]),
        "profile.project_headings": _headings(profile["projects"]),
        "profile.skills": profile["skills"],
        "profile.certification_headings": _headings(profile["certifications"]),
        "profile.leadership_headings": _headings(profile["leadership"]),
    }


def _compare_fields(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[dict[str, Any]]:
    comparisons = []
    for path, expected_value in expected.items():
        actual_value = actual[path]
        if isinstance(expected_value, list):
            score, missing, unexpected = _list_score(expected_value, actual_value)
        else:
            score = similarity(expected_value, actual_value)
            missing = [expected_value] if expected_value and score < 0.55 else []
            unexpected = [actual_value] if not expected_value and actual_value else []
        comparisons.append(
            {
                "path": path,
                "score": round(score, 4),
                "expected": expected_value,
                "actual": actual_value,
                "missing": missing,
                "unexpected": unexpected,
            }
        )
    return comparisons


def _has_expected_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _evidence_coverage(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    required_fields = {
        EVIDENCE_FIELD_BY_PATH[path]
        for path, value in expected.items()
        if _has_expected_value(value)
    }
    evidence_fields = {
        str(item.get("field", "")).strip()
        for item in result.get("evidence", [])
        if isinstance(item, dict)
        and str(item.get("field", "")).strip()
        and str(item.get("source_text", "")).strip()
    }
    covered_fields = required_fields & evidence_fields
    required_count = len(required_fields)
    coverage = 100.0 if not required_count else 100 * len(covered_fields) / required_count
    return {
        "required_count": required_count,
        "covered_count": len(covered_fields),
        "coverage_percent": round(coverage, 2),
        "covered_fields": sorted(covered_fields),
        "missing_fields": sorted(required_fields - covered_fields),
    }


def _evaluation_request(case: ResumeEvaluationCase) -> ResumeExtractionRequest:
    return ResumeExtractionRequest(
        document_text=case.resume_text,
        source_id=1,
        source_sha256="a" * 64,
        source_filename="resume.txt",
        source_label=case.title,
        document_parser_key="evaluation-text",
        document_parser_version="v1",
    )


def evaluate_case(
    case: ResumeEvaluationCase,
    *,
    extractor: BaseResumeExtractor | None = None,
) -> dict[str, Any]:
    active_extractor = extractor or DeterministicResumeExtractor()
    started = perf_counter()
    result = execute_resume_extractor(
        _evaluation_request(case),
        active_extractor,
    ).to_dict()
    latency_ms = 1000 * (perf_counter() - started)

    expected = _expected_fields(case)
    actual = _actual_fields(result)
    comparisons = _compare_fields(expected, actual)
    serialized = json.dumps(result, sort_keys=True).casefold()
    forbidden_hits = [
        claim for claim in case.forbidden_claims if claim.casefold() in serialized
    ]
    comparison_map = {item["path"]: item for item in comparisons}
    critical_results = []
    for claim in case.critical_claims:
        comparison = comparison_map[claim["path"]]
        critical_results.append(
            {
                **claim,
                "score": comparison["score"],
                "passed": comparison["score"] >= 0.55,
            }
        )

    evidence_coverage = _evidence_coverage(result, expected)
    return {
        "case_id": case.case_id,
        "title": case.title,
        "category": case.category,
        "provider": result["provider"],
        "latency_ms": round(latency_ms, 2),
        "agreement_percent": round(
            100 * sum(item["score"] for item in comparisons) / len(comparisons),
            2,
        ),
        "evidence_coverage": evidence_coverage,
        "under_extraction_count": sum(
            len(item["missing"]) for item in comparisons
        ),
        "over_extraction_count": sum(
            len(item["unexpected"]) for item in comparisons
        ),
        "critical_passed": sum(item["passed"] for item in critical_results),
        "critical_total": len(critical_results),
        "forbidden_hits": forbidden_hits,
        "comparisons": comparisons,
        "critical_claims": critical_results,
        "warnings": result["warnings"],
    }


def run_evaluation(
    root: str | Path = DEFAULT_CASES_ROOT,
    *,
    extractor: BaseResumeExtractor | None = None,
) -> dict[str, Any]:
    active_extractor = extractor or DeterministicResumeExtractor()
    results = [
        evaluate_case(case, extractor=active_extractor)
        for case in discover_cases(root)
    ]
    provider_metadata = results[0]["provider"]
    if any(result["provider"] != provider_metadata for result in results):
        raise ResumeEvaluationError(
            "One evaluation run cannot contain multiple provider identities."
        )

    evidence_required = sum(
        item["evidence_coverage"]["required_count"] for item in results
    )
    evidence_covered = sum(
        item["evidence_coverage"]["covered_count"] for item in results
    )
    total_latency_ms = sum(item["latency_ms"] for item in results)
    return {
        "runner_version": RUNNER_VERSION,
        "provider": provider_metadata["key"],
        "provider_metadata": provider_metadata,
        "case_count": len(results),
        "agreement_percent": round(
            sum(item["agreement_percent"] for item in results) / len(results),
            2,
        ),
        "evidence_coverage_percent": round(
            100.0 if not evidence_required else 100 * evidence_covered / evidence_required,
            2,
        ),
        "evidence_required_count": evidence_required,
        "evidence_covered_count": evidence_covered,
        "average_latency_ms": round(total_latency_ms / len(results), 2),
        "total_latency_ms": round(total_latency_ms, 2),
        "under_extraction_count": sum(
            item["under_extraction_count"] for item in results
        ),
        "over_extraction_count": sum(
            item["over_extraction_count"] for item in results
        ),
        "critical_passed": sum(item["critical_passed"] for item in results),
        "critical_total": sum(item["critical_total"] for item in results),
        "forbidden_hit_count": sum(
            len(item["forbidden_hits"]) for item in results
        ),
        "cases": results,
    }


def evaluation_failures(
    report: dict[str, Any],
    *,
    minimum_agreement: float = 0.0,
) -> list[str]:
    failures = []
    if report["forbidden_hit_count"]:
        failures.append("Resume evaluation produced forbidden claims.")
    if report["critical_passed"] != report["critical_total"]:
        failures.append("Resume evaluation missed one or more critical claims.")
    if report["agreement_percent"] < minimum_agreement:
        failures.append(
            f"Agreement {report['agreement_percent']}% is below the required "
            f"{minimum_agreement}%."
        )
    return failures


def compare_evaluation_runs(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_cases = {item["case_id"]: item for item in baseline["cases"]}
    candidate_cases = {item["case_id"]: item for item in candidate["cases"]}
    if set(baseline_cases) != set(candidate_cases):
        raise ResumeEvaluationError(
            "Provider comparison requires identical evaluation case IDs."
        )

    case_comparisons = []
    regressions = []
    improvements = []
    for case_id in sorted(baseline_cases):
        baseline_case = baseline_cases[case_id]
        candidate_case = candidate_cases[case_id]
        agreement_delta = round(
            candidate_case["agreement_percent"]
            - baseline_case["agreement_percent"],
            2,
        )
        evidence_delta = round(
            candidate_case["evidence_coverage"]["coverage_percent"]
            - baseline_case["evidence_coverage"]["coverage_percent"],
            2,
        )
        under_delta = (
            candidate_case["under_extraction_count"]
            - baseline_case["under_extraction_count"]
        )
        over_delta = (
            candidate_case["over_extraction_count"]
            - baseline_case["over_extraction_count"]
        )
        critical_delta = (
            candidate_case["critical_passed"] - baseline_case["critical_passed"]
        )
        forbidden_delta = len(candidate_case["forbidden_hits"]) - len(
            baseline_case["forbidden_hits"]
        )
        reasons = []
        if agreement_delta < 0:
            reasons.append("agreement_decreased")
        if evidence_delta < 0:
            reasons.append("evidence_coverage_decreased")
        if under_delta > 0:
            reasons.append("under_extraction_increased")
        if over_delta > 0:
            reasons.append("over_extraction_increased")
        if critical_delta < 0:
            reasons.append("critical_claims_decreased")
        if forbidden_delta > 0:
            reasons.append("forbidden_claims_increased")

        comparison = {
            "case_id": case_id,
            "title": candidate_case["title"],
            "category": candidate_case["category"],
            "agreement_delta_percent": agreement_delta,
            "evidence_coverage_delta_percent": evidence_delta,
            "latency_delta_ms": round(
                candidate_case["latency_ms"] - baseline_case["latency_ms"],
                2,
            ),
            "under_extraction_delta": under_delta,
            "over_extraction_delta": over_delta,
            "critical_pass_delta": critical_delta,
            "forbidden_hit_delta": forbidden_delta,
            "regression_reasons": reasons,
        }
        case_comparisons.append(comparison)
        if reasons:
            regressions.append(comparison)
        elif agreement_delta > 0 or evidence_delta > 0 or under_delta < 0 or over_delta < 0:
            improvements.append(comparison)

    summary = {
        "agreement_delta_percent": round(
            candidate["agreement_percent"] - baseline["agreement_percent"],
            2,
        ),
        "evidence_coverage_delta_percent": round(
            candidate["evidence_coverage_percent"]
            - baseline["evidence_coverage_percent"],
            2,
        ),
        "average_latency_delta_ms": round(
            candidate["average_latency_ms"] - baseline["average_latency_ms"],
            2,
        ),
        "under_extraction_delta": (
            candidate["under_extraction_count"]
            - baseline["under_extraction_count"]
        ),
        "over_extraction_delta": (
            candidate["over_extraction_count"]
            - baseline["over_extraction_count"]
        ),
        "critical_pass_delta": (
            candidate["critical_passed"] - baseline["critical_passed"]
        ),
        "forbidden_hit_delta": (
            candidate["forbidden_hit_count"] - baseline["forbidden_hit_count"]
        ),
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
    }
    return {
        "comparison_version": COMPARISON_VERSION,
        "baseline": baseline,
        "candidate": candidate,
        "summary": summary,
        "cases": case_comparisons,
        "regressions": regressions,
        "improvements": improvements,
    }


def run_comparison(
    root: str | Path = DEFAULT_CASES_ROOT,
    *,
    candidate_extractor: BaseResumeExtractor,
    baseline_extractor: BaseResumeExtractor | None = None,
) -> dict[str, Any]:
    baseline = run_evaluation(
        root,
        extractor=baseline_extractor or DeterministicResumeExtractor(),
    )
    candidate = run_evaluation(root, extractor=candidate_extractor)
    return compare_evaluation_runs(baseline, candidate)
