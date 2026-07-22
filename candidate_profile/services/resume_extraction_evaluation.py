from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from django.conf import settings

from .resume_deterministic import DeterministicResumeExtractor
from .resume_extraction import ResumeExtractionRequest, execute_resume_extractor


CASE_SCHEMA_VERSION = "resume-extraction-evaluation-case-v1"
RUNNER_VERSION = "resume-extraction-evaluator-v1"
DEFAULT_CASES_ROOT = (
    Path(settings.BASE_DIR) / "docs" / "evaluations" / "resume-extraction" / "cases"
)


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
    for field in ("links",):
        _require_list(identity[field], f"expected.identity.{field}")
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
    return [str(entry.get("heading", "")).strip() for entry in entries if entry.get("heading")]


def _list_score(expected: list[str], actual: list[str]) -> tuple[float, list[str], list[str]]:
    if not expected and not actual:
        return 1.0, [], []
    unused = set(range(len(actual)))
    scores = []
    missing = []
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


def evaluate_case(case: ResumeEvaluationCase) -> dict[str, Any]:
    request = ResumeExtractionRequest(
        document_text=case.resume_text,
        source_id=1,
        source_sha256="a" * 64,
        source_filename="resume.txt",
        source_label=case.title,
        document_parser_key="evaluation-text",
        document_parser_version="v1",
    )
    result = execute_resume_extractor(request, DeterministicResumeExtractor()).to_dict()
    identity = result["identity"]
    profile = result["profile"]
    actual = {
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
    expected_identity = case.expected["identity"]
    expected_profile = case.expected["profile"]
    expected = {
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
        "profile.certification_headings": expected_profile["certification_headings"],
        "profile.leadership_headings": expected_profile["leadership_headings"],
    }
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
    serialized = json.dumps(result, sort_keys=True).casefold()
    forbidden_hits = [claim for claim in case.forbidden_claims if claim.casefold() in serialized]
    critical_results = []
    comparison_map = {item["path"]: item for item in comparisons}
    for claim in case.critical_claims:
        comparison = comparison_map[claim["path"]]
        critical_results.append(
            {
                **claim,
                "score": comparison["score"],
                "passed": comparison["score"] >= 0.55,
            }
        )
    return {
        "case_id": case.case_id,
        "title": case.title,
        "category": case.category,
        "provider": result["provider"],
        "agreement_percent": round(
            100 * sum(item["score"] for item in comparisons) / len(comparisons), 2
        ),
        "critical_passed": sum(item["passed"] for item in critical_results),
        "critical_total": len(critical_results),
        "forbidden_hits": forbidden_hits,
        "comparisons": comparisons,
        "critical_claims": critical_results,
        "warnings": result["warnings"],
    }


def run_evaluation(root: str | Path = DEFAULT_CASES_ROOT) -> dict[str, Any]:
    results = [evaluate_case(case) for case in discover_cases(root)]
    return {
        "runner_version": RUNNER_VERSION,
        "provider": "deterministic",
        "case_count": len(results),
        "agreement_percent": round(
            sum(item["agreement_percent"] for item in results) / len(results), 2
        ),
        "critical_passed": sum(item["critical_passed"] for item in results),
        "critical_total": sum(item["critical_total"] for item in results),
        "forbidden_hit_count": sum(len(item["forbidden_hits"]) for item in results),
        "cases": results,
    }
