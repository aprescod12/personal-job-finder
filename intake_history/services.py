from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tracker.models import JobPosting

from .models import JobExtractionRun


DUPLICATE_REASON_EXACT_URL = "exact_url"
DUPLICATE_REASON_EXACT_TEXT = "exact_text"
DUPLICATE_REASON_SAME_ROLE = "same_role"

DUPLICATE_REASON_LABELS = {
    DUPLICATE_REASON_EXACT_URL: "Same normalized job URL",
    DUPLICATE_REASON_EXACT_TEXT: "Same pasted listing text",
    DUPLICATE_REASON_SAME_ROLE: "Same title, company, and location",
}

_REASON_PRIORITY = {
    DUPLICATE_REASON_SAME_ROLE: 1,
    DUPLICATE_REASON_EXACT_TEXT: 2,
    DUPLICATE_REASON_EXACT_URL: 3,
}

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.casefold().split())


def normalize_source_url(value: str) -> str:
    """Normalize a job URL without discarding job-identifying query values."""

    raw_url = (value or "").strip()
    if not raw_url:
        return ""

    parsed = urlsplit(raw_url)
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    query_pairs = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.casefold()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, item_value))
    query_pairs.sort(key=lambda item: (item[0].casefold(), item[1]))

    return urlunsplit(
        (
            scheme,
            hostname,
            path,
            urlencode(query_pairs, doseq=True),
            "",
        )
    )


def listing_text_sha256(raw_text: str) -> str:
    normalized = _normalized_text(raw_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def role_identity_sha256(*, title: str, company: str, location: str = "") -> str:
    normalized_title = _normalized_text(title)
    normalized_company = _normalized_text(company)
    if not normalized_title or not normalized_company:
        return ""
    normalized_location = _normalized_text(location)
    identity = "\x1f".join(
        (normalized_title, normalized_company, normalized_location)
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _candidate_payload(job: JobPosting, reason: str) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "status": job.status,
        "reason": reason,
        "reason_label": DUPLICATE_REASON_LABELS[reason],
        "blocking": reason in {
            DUPLICATE_REASON_EXACT_URL,
            DUPLICATE_REASON_EXACT_TEXT,
        },
    }


def _remember_candidate(
    candidates: dict[int, dict[str, Any]],
    job: JobPosting,
    reason: str,
) -> None:
    existing = candidates.get(job.id)
    if existing and _REASON_PRIORITY[existing["reason"]] >= _REASON_PRIORITY[reason]:
        return
    candidates[job.id] = _candidate_payload(job, reason)


def analyze_job_duplicates(
    *,
    source_url: str,
    raw_text: str,
    extracted_job: dict[str, Any] | None = None,
    exclude_job_id: int | None = None,
) -> dict[str, Any]:
    """Return conservative duplicate candidates without creating or changing records."""

    normalized_url = normalize_source_url(source_url)
    text_hash = listing_text_sha256(raw_text)
    extracted_job = extracted_job or {}
    role_hash = role_identity_sha256(
        title=str(extracted_job.get("title", "")),
        company=str(extracted_job.get("company", "")),
        location=str(extracted_job.get("location", "")),
    )

    jobs = JobPosting.objects.all().only(
        "id",
        "title",
        "company",
        "location",
        "job_url",
        "status",
    )
    if exclude_job_id is not None:
        jobs = jobs.exclude(pk=exclude_job_id)

    candidates: dict[int, dict[str, Any]] = {}
    cached_jobs = list(jobs)

    if normalized_url:
        for job in cached_jobs:
            if normalize_source_url(job.job_url) == normalized_url:
                _remember_candidate(candidates, job, DUPLICATE_REASON_EXACT_URL)

        historical_url_runs = JobExtractionRun.objects.filter(
            normalized_source_url=normalized_url
        ).select_related("job")
        if exclude_job_id is not None:
            historical_url_runs = historical_url_runs.exclude(job_id=exclude_job_id)
        for run in historical_url_runs:
            _remember_candidate(candidates, run.job, DUPLICATE_REASON_EXACT_URL)

    historical_text_runs = JobExtractionRun.objects.filter(
        raw_text_sha256=text_hash
    ).select_related("job")
    if exclude_job_id is not None:
        historical_text_runs = historical_text_runs.exclude(job_id=exclude_job_id)
    for run in historical_text_runs:
        _remember_candidate(candidates, run.job, DUPLICATE_REASON_EXACT_TEXT)

    if role_hash:
        for job in cached_jobs:
            existing_role_hash = role_identity_sha256(
                title=job.title,
                company=job.company,
                location=job.location,
            )
            if existing_role_hash == role_hash:
                _remember_candidate(candidates, job, DUPLICATE_REASON_SAME_ROLE)

    ordered_candidates = sorted(
        candidates.values(),
        key=lambda item: (
            -_REASON_PRIORITY[item["reason"]],
            item["company"].casefold(),
            item["title"].casefold(),
            item["job_id"],
        ),
    )
    return {
        "blocking": any(item["blocking"] for item in ordered_candidates),
        "has_candidates": bool(ordered_candidates),
        "candidates": ordered_candidates,
        "fingerprints": {
            "normalized_source_url": normalized_url,
            "raw_text_sha256": text_hash,
            "role_identity_sha256": role_hash,
        },
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def record_extraction_run(
    *,
    job: JobPosting,
    intake_draft: dict[str, Any],
    reviewed_data: dict[str, Any],
    duplicate_analysis: dict[str, Any] | None = None,
) -> JobExtractionRun:
    """Persist provenance only after the human-reviewed job is created."""

    extraction = intake_draft.get("extraction", {})
    provider = extraction.get("provider", {})
    orchestration = extraction.get("orchestration", {})
    source_url = str(intake_draft.get("source_url", ""))
    raw_text = str(intake_draft.get("raw_text", ""))
    duplicate_analysis = duplicate_analysis or intake_draft.get(
        "duplicate_analysis",
        {},
    )

    return JobExtractionRun.objects.create(
        job=job,
        source_url=source_url,
        normalized_source_url=normalize_source_url(source_url),
        source_label=str(intake_draft.get("source_label", "")),
        raw_text=raw_text,
        raw_text_sha256=listing_text_sha256(raw_text),
        role_identity_sha256=role_identity_sha256(
            title=str(reviewed_data.get("title", "")),
            company=str(reviewed_data.get("company", "")),
            location=str(reviewed_data.get("location", "")),
        ),
        provider_key=str(provider.get("key", "")),
        provider_label=str(provider.get("label", "")),
        provider_version=str(
            provider.get("version", extraction.get("parser_version", ""))
        ),
        extraction_mode=str(provider.get("mode", "")),
        orchestration_status=str(orchestration.get("status", "")),
        fallback_used=bool(orchestration.get("fallback_used", False)),
        manual_review_required=bool(
            orchestration.get("manual_review_required", False)
        ),
        total_elapsed_ms=max(0, int(orchestration.get("total_elapsed_ms", 0) or 0)),
        attempts=_json_safe(orchestration.get("attempts", [])),
        evidence=_json_safe(extraction.get("evidence", [])),
        warnings=_json_safe(extraction.get("warnings", [])),
        extracted_payload=_json_safe(extraction),
        reviewed_payload=_json_safe(
            {
                key: value
                for key, value in reviewed_data.items()
                if key not in {"confirm_duplicate"}
            }
        ),
        duplicate_candidates=_json_safe(
            duplicate_analysis.get("candidates", [])
        ),
        duplicate_override=bool(reviewed_data.get("confirm_duplicate", False)),
    )
