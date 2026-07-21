from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable

from .ai_job_extraction import AI_EXTRACTION_SCHEMA_VERSION
from .job_extraction import BaseJobExtractor
from .job_extraction_evaluation import (
    DEFAULT_CASES_ROOT,
    JobExtractionEvaluationCase,
    discover_evaluation_cases,
)
from .job_extraction_evaluation_runner import (
    ELIGIBILITY_SENSITIVE_FIELDS,
    EVALUATION_RUNNER_VERSION,
    STATUS_ORDER,
    CaseEvaluation,
    EvaluationRun,
    FieldComparison,
    evaluate_case,
    evaluate_cases,
)

AI_EVALUATION_RUNNER_VERSION = "job-extraction-ai-evaluator-v1"
AI_PROMPT_VERSION = "job-extraction-prompt-v1"
AI_PROVIDER = "ai"


@dataclass(frozen=True, slots=True)
class CaseTiming:
    case_id: str
    duration_ms: float


@dataclass(slots=True)
class AIEvaluationRun:
    evaluation: EvaluationRun
    model: str
    schema_version: str
    prompt_version: str
    total_duration_ms: float
    case_timings: list[CaseTiming]
    live_provider_calls: bool

    def to_dict(self) -> dict[str, Any]:
        payload = self.evaluation.to_dict()
        payload["ai_evaluation_runner_version"] = AI_EVALUATION_RUNNER_VERSION
        payload["ai_metadata"] = {
            "model": self.model,
            "schema_version": self.schema_version,
            "prompt_version": self.prompt_version,
            "live_provider_calls": self.live_provider_calls,
        }
        payload["timing"] = {
            "total_duration_ms": round(self.total_duration_ms, 2),
            "case_durations_ms": {
                item.case_id: round(item.duration_ms, 2) for item in self.case_timings
            },
        }
        return payload


@dataclass(frozen=True, slots=True)
class DeltaRow:
    key: str
    deterministic_percent: float
    ai_percent: float
    delta_points: float


@dataclass(slots=True)
class ExtractionEvaluationComparison:
    generated_at: str
    deterministic: EvaluationRun
    ai: AIEvaluationRun
    overall_delta_points: float
    sensitive_delta_points: float
    case_deltas: list[DeltaRow]
    field_deltas: list[DeltaRow]

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_version": AI_EVALUATION_RUNNER_VERSION,
            "generated_at": self.generated_at,
            "overall_delta_points": round(self.overall_delta_points, 2),
            "eligibility_sensitive_delta_points": round(
                self.sensitive_delta_points,
                2,
            ),
            "deterministic": self.deterministic.to_dict(),
            "ai": self.ai.to_dict(),
            "case_deltas": [asdict(row) for row in self.case_deltas],
            "field_deltas": [asdict(row) for row in self.field_deltas],
        }


def _select_cases(
    *,
    cases_root: str | Path,
    case_ids: Iterable[str] | None,
) -> list[JobExtractionEvaluationCase]:
    selected_ids = set(case_ids or [])
    discovered = discover_evaluation_cases(cases_root)
    if selected_ids:
        discovered = [case for case in discovered if case.case_id in selected_ids]
        missing = selected_ids - {case.case_id for case in discovered}
        if missing:
            raise ValueError(f"Unknown evaluation case(s): {', '.join(sorted(missing))}.")
    if not discovered:
        raise ValueError("No evaluation cases were selected.")
    return discovered


def _average_score(comparisons: list[FieldComparison]) -> float:
    if not comparisons:
        return 0.0
    return 100 * sum(item.score for item in comparisons) / len(comparisons)


def _status_counts(comparisons: list[FieldComparison]) -> dict[str, int]:
    return {
        status: sum(1 for item in comparisons if item.status == status)
        for status in STATUS_ORDER
    }


def _field_summary(cases: list[CaseEvaluation]) -> dict[str, dict[str, Any]]:
    ordered_paths: list[str] = []
    for case in cases:
        for comparison in case.comparisons:
            if comparison.path not in ordered_paths:
                ordered_paths.append(comparison.path)

    summary: dict[str, dict[str, Any]] = {}
    for path in ordered_paths:
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


def _model_name(extractor: BaseJobExtractor) -> str:
    backend = getattr(extractor, "backend", None)
    model = str(getattr(backend, "model", "") or "").strip()
    return model or "injected-test-backend"


def _load_live_ai_extractor() -> BaseJobExtractor:
    # Imported lazily so deterministic CI never initializes the OpenAI adapter.
    from .openai_job_extraction import OpenAIJobExtractor

    return OpenAIJobExtractor()


def evaluate_ai_cases(
    *,
    cases_root: str | Path = DEFAULT_CASES_ROOT,
    case_ids: Iterable[str] | None = None,
    generated_at: datetime | None = None,
    extractor: BaseJobExtractor | None = None,
    allow_live_ai: bool = False,
    clock: Callable[[], float] = perf_counter,
) -> AIEvaluationRun:
    """Evaluate the AI extractor directly, without fallback or database writes."""

    live_provider_calls = extractor is None
    if live_provider_calls and not allow_live_ai:
        raise ValueError(
            "Live AI evaluation is disabled by default. Re-run with explicit "
            "permission after confirming local API configuration and expected cost."
        )

    active_extractor = extractor or _load_live_ai_extractor()
    if active_extractor.extraction_mode != "ai":
        raise ValueError("AI evaluation requires an extractor whose mode is 'ai'.")

    cases = _select_cases(cases_root=cases_root, case_ids=case_ids)
    case_results: list[CaseEvaluation] = []
    timings: list[CaseTiming] = []
    run_started = clock()
    for case in cases:
        case_started = clock()
        result = evaluate_case(case, extractor=active_extractor)
        duration_ms = max(0.0, (clock() - case_started) * 1000)
        case_results.append(result)
        timings.append(CaseTiming(case.case_id, duration_ms))
    total_duration_ms = max(0.0, (clock() - run_started) * 1000)

    comparisons = [
        comparison for case in case_results for comparison in case.comparisons
    ]
    sensitive = [
        comparison
        for comparison in comparisons
        if comparison.path in ELIGIBILITY_SENSITIVE_FIELDS
    ]
    timestamp = generated_at or datetime.now(timezone.utc)
    evaluation = EvaluationRun(
        runner_version=EVALUATION_RUNNER_VERSION,
        provider=AI_PROVIDER,
        generated_at=timestamp.isoformat(),
        case_count=len(case_results),
        field_count=len(comparisons),
        field_agreement_percent=_average_score(comparisons),
        eligibility_sensitive_agreement_percent=_average_score(sensitive),
        status_counts=_status_counts(comparisons),
        field_summary=_field_summary(case_results),
        cases=case_results,
    )
    return AIEvaluationRun(
        evaluation=evaluation,
        model=_model_name(active_extractor),
        schema_version=AI_EXTRACTION_SCHEMA_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        total_duration_ms=total_duration_ms,
        case_timings=timings,
        live_provider_calls=live_provider_calls,
    )


def compare_evaluation_runs(
    deterministic: EvaluationRun,
    ai: AIEvaluationRun,
    *,
    generated_at: datetime | None = None,
) -> ExtractionEvaluationComparison:
    ai_run = ai.evaluation
    deterministic_ids = {case.case_id for case in deterministic.cases}
    ai_ids = {case.case_id for case in ai_run.cases}
    if deterministic_ids != ai_ids:
        raise ValueError("Deterministic and AI runs must contain the same case IDs.")

    deterministic_cases = {case.case_id: case for case in deterministic.cases}
    ai_cases = {case.case_id: case for case in ai_run.cases}
    case_deltas = [
        DeltaRow(
            key=case_id,
            deterministic_percent=round(
                deterministic_cases[case_id].field_agreement_percent,
                2,
            ),
            ai_percent=round(ai_cases[case_id].field_agreement_percent, 2),
            delta_points=round(
                ai_cases[case_id].field_agreement_percent
                - deterministic_cases[case_id].field_agreement_percent,
                2,
            ),
        )
        for case_id in sorted(deterministic_ids)
    ]

    deterministic_fields = set(deterministic.field_summary)
    ai_fields = set(ai_run.field_summary)
    if deterministic_fields != ai_fields:
        raise ValueError("Deterministic and AI runs must compare the same fields.")
    field_deltas = [
        DeltaRow(
            key=path,
            deterministic_percent=float(
                deterministic.field_summary[path]["agreement_percent"]
            ),
            ai_percent=float(ai_run.field_summary[path]["agreement_percent"]),
            delta_points=round(
                float(ai_run.field_summary[path]["agreement_percent"])
                - float(deterministic.field_summary[path]["agreement_percent"]),
                2,
            ),
        )
        for path in deterministic.field_summary
    ]

    timestamp = generated_at or datetime.now(timezone.utc)
    return ExtractionEvaluationComparison(
        generated_at=timestamp.isoformat(),
        deterministic=deterministic,
        ai=ai,
        overall_delta_points=round(
            ai_run.field_agreement_percent - deterministic.field_agreement_percent,
            2,
        ),
        sensitive_delta_points=round(
            ai_run.eligibility_sensitive_agreement_percent
            - deterministic.eligibility_sensitive_agreement_percent,
            2,
        ),
        case_deltas=case_deltas,
        field_deltas=field_deltas,
    )


def run_ai_comparison(
    *,
    cases_root: str | Path = DEFAULT_CASES_ROOT,
    case_ids: Iterable[str] | None = None,
    generated_at: datetime | None = None,
    extractor: BaseJobExtractor | None = None,
    allow_live_ai: bool = False,
    clock: Callable[[], float] = perf_counter,
) -> ExtractionEvaluationComparison:
    timestamp = generated_at or datetime.now(timezone.utc)
    ai = evaluate_ai_cases(
        cases_root=cases_root,
        case_ids=case_ids,
        generated_at=timestamp,
        extractor=extractor,
        allow_live_ai=allow_live_ai,
        clock=clock,
    )
    deterministic = evaluate_cases(
        cases_root=cases_root,
        case_ids=case_ids,
        generated_at=timestamp,
    )
    return compare_evaluation_runs(deterministic, ai, generated_at=timestamp)


def render_ai_json_report(comparison: ExtractionEvaluationComparison) -> str:
    return json.dumps(comparison.to_dict(), indent=2, sort_keys=True) + "\n"


def _signed(value: float) -> str:
    return f"{value:+.2f}"


def render_ai_markdown_report(comparison: ExtractionEvaluationComparison) -> str:
    deterministic = comparison.deterministic
    ai = comparison.ai
    ai_run = ai.evaluation
    lines = [
        "# AI vs Deterministic Job Extraction Evaluation",
        "",
        f"- Comparison version: `{AI_EVALUATION_RUNNER_VERSION}`",
        f"- Official scorer: `{ai_run.runner_version}`",
        f"- Generated: `{comparison.generated_at}`",
        f"- Cases: **{ai_run.case_count}**",
        f"- AI provider: `{ai_run.cases[0].provider_version}`",
        f"- Model: `{ai.model}`",
        f"- Schema: `{ai.schema_version}`",
        f"- Prompt: `{ai.prompt_version}`",
        f"- Total AI duration: **{ai.total_duration_ms:.2f} ms**",
        "",
        "> This report compares extraction agreement against stored ground truth. "
        "It does not rank jobs or decide candidate eligibility.",
        "",
        "## Overall comparison",
        "",
        "| Measure | Deterministic | AI | Delta |",
        "|---|---:|---:|---:|",
        (
            f"| Field agreement | {deterministic.field_agreement_percent:.2f}% | "
            f"{ai_run.field_agreement_percent:.2f}% | "
            f"{_signed(comparison.overall_delta_points)} points |"
        ),
        (
            "| Eligibility-sensitive agreement | "
            f"{deterministic.eligibility_sensitive_agreement_percent:.2f}% | "
            f"{ai_run.eligibility_sensitive_agreement_percent:.2f}% | "
            f"{_signed(comparison.sensitive_delta_points)} points |"
        ),
        "",
        "## Case comparison",
        "",
        "| Case | Deterministic | AI | Delta | AI duration |",
        "|---|---:|---:|---:|---:|",
    ]
    timing_by_case = {item.case_id: item.duration_ms for item in ai.case_timings}
    for row in comparison.case_deltas:
        lines.append(
            f"| `{row.key}` | {row.deterministic_percent:.2f}% | "
            f"{row.ai_percent:.2f}% | {_signed(row.delta_points)} | "
            f"{timing_by_case[row.key]:.2f} ms |"
        )

    lines.extend(
        [
            "",
            "## Field comparison",
            "",
            "| Field | Deterministic | AI | Delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in comparison.field_deltas:
        lines.append(
            f"| `{row.key}` | {row.deterministic_percent:.2f}% | "
            f"{row.ai_percent:.2f}% | {_signed(row.delta_points)} |"
        )

    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "- The AI extractor is evaluated directly; deterministic fallback is disabled.",
            "- Nothing is written to `JobPosting` or `JobRequirement`.",
            "- Live calls require explicit command-line permission.",
            "- CI uses fake injected extractors and never calls a paid provider.",
            "- Results still require human interpretation before prompt changes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_ai_report(
    comparison: ExtractionEvaluationComparison,
    *,
    output: str | Path,
    report_format: str,
) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if report_format == "json":
        content = render_ai_json_report(comparison)
    elif report_format == "markdown":
        content = render_ai_markdown_report(comparison)
    else:
        raise ValueError(f"Unsupported report format: {report_format}.")
    destination.write_text(content, encoding="utf-8")
    return destination
