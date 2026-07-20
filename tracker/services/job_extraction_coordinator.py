from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from django.conf import settings

from .job_extraction import (
    DEFAULT_EXTRACTOR_PATH,
    ERROR_ALL_EXTRACTORS_FAILED,
    ERROR_PROVIDER_FAILURE,
    BaseJobExtractor,
    JobExtractionError,
    JobExtractionRequest,
    JobExtractionResult,
    execute_job_extractor,
    get_job_extractor,
)


DEFAULT_FALLBACK_EXTRACTOR_PATH = DEFAULT_EXTRACTOR_PATH
MANUAL_REVIEW_VERSION = "manual-review-v1"


@dataclass(slots=True)
class ExtractionAttempt:
    provider_path: str
    provider_key: str = ""
    provider_label: str = ""
    provider_version: str = ""
    extraction_mode: str = "unknown"
    success: bool = False
    elapsed_ms: int = 0
    error_category: str = ""
    error_message: str = ""
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_path": self.provider_path,
            "provider": {
                "key": self.provider_key,
                "label": self.provider_label,
                "version": self.provider_version,
                "mode": self.extraction_mode,
            },
            "success": self.success,
            "elapsed_ms": self.elapsed_ms,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "retryable": self.retryable,
        }


def _elapsed_ms(started_at: float, clock: Callable[[], float]) -> int:
    return max(0, round((clock() - started_at) * 1000))


def _safe_failure(exc: Exception) -> JobExtractionError:
    if isinstance(exc, JobExtractionError):
        return exc
    return JobExtractionError(
        "The extraction provider failed unexpectedly.",
        category=ERROR_PROVIDER_FAILURE,
    )


def _attempt_extraction(
    request: JobExtractionRequest,
    *,
    provider_path: str,
    extractor: BaseJobExtractor | None,
    clock: Callable[[], float],
) -> tuple[dict[str, object] | None, ExtractionAttempt, BaseJobExtractor | None]:
    started_at = clock()
    attempt = ExtractionAttempt(provider_path=provider_path)

    try:
        active_extractor = extractor or get_job_extractor(provider_path)
        attempt.provider_key = active_extractor.provider_key
        attempt.provider_label = active_extractor.provider_label
        attempt.provider_version = active_extractor.provider_version
        attempt.extraction_mode = active_extractor.extraction_mode

        result = execute_job_extractor(request, active_extractor)
        payload = result.to_dict()
    except Exception as exc:  # Provider boundaries must not leak raw exceptions.
        failure = _safe_failure(exc)
        attempt.elapsed_ms = _elapsed_ms(started_at, clock)
        attempt.error_category = failure.category
        attempt.error_message = str(failure)
        attempt.retryable = failure.retryable
        return None, attempt, locals().get("active_extractor")

    attempt.success = True
    attempt.elapsed_ms = _elapsed_ms(started_at, clock)
    return payload, attempt, active_extractor


def _manual_review_payload(
    request: JobExtractionRequest,
    *,
    warnings: list[str],
) -> dict[str, object]:
    result = JobExtractionResult(
        provider_key="manual_review",
        provider_label="Manual review draft",
        provider_version=MANUAL_REVIEW_VERSION,
        extraction_mode="manual",
        job={
            "job_url": request.source_url,
            "source": request.source_label,
            "description": request.listing_text,
        },
        requirements={},
        evidence=[],
        warnings=warnings,
    )
    return result.to_dict()


def _orchestration_payload(
    *,
    status: str,
    primary_path: str,
    result_payload: dict[str, object],
    attempts: list[ExtractionAttempt],
    fallback_used: bool,
    manual_review_required: bool,
    total_elapsed_ms: int,
) -> dict[str, object]:
    return {
        "status": status,
        "primary_provider_path": primary_path,
        "result_provider": result_payload["provider"],
        "fallback_used": fallback_used,
        "manual_review_required": manual_review_required,
        "total_elapsed_ms": total_elapsed_ms,
        "attempts": [attempt.to_dict() for attempt in attempts],
    }


def extract_job_with_fallback(
    listing_text: str,
    *,
    source_url: str = "",
    source_label: str = "",
    primary_extractor: BaseJobExtractor | None = None,
    fallback_extractor: BaseJobExtractor | None = None,
    fallback_enabled: bool | None = None,
    clock: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    """Produce a review draft while disclosing fallback and failure behavior."""

    request = JobExtractionRequest(
        listing_text=listing_text,
        source_url=source_url,
        source_label=source_label,
    )
    started_at = clock()
    primary_path = getattr(
        settings,
        "JOB_INTAKE_EXTRACTOR",
        DEFAULT_EXTRACTOR_PATH,
    )
    fallback_path = getattr(
        settings,
        "JOB_INTAKE_FALLBACK_EXTRACTOR",
        DEFAULT_FALLBACK_EXTRACTOR_PATH,
    )
    use_fallback = (
        getattr(settings, "JOB_INTAKE_FALLBACK_ENABLED", True)
        if fallback_enabled is None
        else fallback_enabled
    )

    attempts: list[ExtractionAttempt] = []
    primary_payload, primary_attempt, loaded_primary = _attempt_extraction(
        request,
        provider_path=primary_path,
        extractor=primary_extractor,
        clock=clock,
    )
    attempts.append(primary_attempt)

    if primary_payload is not None:
        primary_payload["orchestration"] = _orchestration_payload(
            status="primary_success",
            primary_path=primary_path,
            result_payload=primary_payload,
            attempts=attempts,
            fallback_used=False,
            manual_review_required=False,
            total_elapsed_ms=_elapsed_ms(started_at, clock),
        )
        return primary_payload

    same_configured_provider = (
        primary_extractor is None
        and fallback_extractor is None
        and primary_path == fallback_path
    )
    same_injected_provider = (
        loaded_primary is not None
        and fallback_extractor is not None
        and loaded_primary.__class__ is fallback_extractor.__class__
    )
    should_try_fallback = (
        use_fallback
        and not same_configured_provider
        and not same_injected_provider
    )

    if should_try_fallback:
        fallback_payload, fallback_attempt, _ = _attempt_extraction(
            request,
            provider_path=fallback_path,
            extractor=fallback_extractor,
            clock=clock,
        )
        attempts.append(fallback_attempt)

        if fallback_payload is not None:
            fallback_payload["warnings"] = [
                (
                    "The primary extractor was unavailable. This draft was produced "
                    "by the deterministic fallback and requires careful review."
                ),
                (
                    f"Primary extractor issue ({primary_attempt.error_category}): "
                    f"{primary_attempt.error_message}"
                ),
                *fallback_payload.get("warnings", []),
            ]
            fallback_payload["orchestration"] = _orchestration_payload(
                status="fallback_success",
                primary_path=primary_path,
                result_payload=fallback_payload,
                attempts=attempts,
                fallback_used=True,
                manual_review_required=False,
                total_elapsed_ms=_elapsed_ms(started_at, clock),
            )
            return fallback_payload

    failure_warnings = [
        (
            "No configured extractor produced a structured draft. The original "
            "listing was preserved for manual review, and nothing has been saved."
        ),
        (
            f"Primary extractor issue ({primary_attempt.error_category}): "
            f"{primary_attempt.error_message}"
        ),
    ]
    if len(attempts) > 1:
        fallback_attempt = attempts[-1]
        failure_warnings.append(
            f"Fallback extractor issue ({fallback_attempt.error_category}): "
            f"{fallback_attempt.error_message}"
        )
    elif not use_fallback:
        failure_warnings.append("Automatic fallback is disabled by configuration.")
    elif same_configured_provider or same_injected_provider:
        failure_warnings.append(
            "Fallback was skipped because it matched the failed primary extractor."
        )

    manual_payload = _manual_review_payload(request, warnings=failure_warnings)
    manual_payload["orchestration"] = _orchestration_payload(
        status=ERROR_ALL_EXTRACTORS_FAILED,
        primary_path=primary_path,
        result_payload=manual_payload,
        attempts=attempts,
        fallback_used=False,
        manual_review_required=True,
        total_elapsed_ms=_elapsed_ms(started_at, clock),
    )
    return manual_payload
