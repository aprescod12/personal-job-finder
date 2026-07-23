from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone

from intake_history.services import (
    DUPLICATE_REASON_EXACT_TEXT,
    DUPLICATE_REASON_EXACT_URL,
    DUPLICATE_REASON_SAME_ROLE,
    analyze_job_duplicates,
    listing_text_sha256,
    normalize_source_url,
    role_identity_sha256,
)
from tracker.models import CareerProfile, JobPosting
from tracker.services.job_extraction import JobExtractionError
from tracker.services.job_extraction_coordinator import extract_job_with_fallback

from .models import DiscoveryRun, RawJobOpportunity
from .providers import (
    DiscoveryProvider,
    DiscoveryQuery,
    DiscoveredOpportunity,
    FixtureDiscoveryProvider,
)


APPROVED_DISCOVERY_PROVIDERS: dict[str, type[DiscoveryProvider]] = {
    FixtureDiscoveryProvider.key: FixtureDiscoveryProvider,
}


class DiscoveryError(RuntimeError):
    pass


class DiscoveryProviderError(DiscoveryError):
    pass


class DiscoveryHandoffError(DiscoveryError):
    pass


def _split_lines(value: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in (value or "").splitlines() if line.strip())


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def approved_provider_choices():
    return tuple(
        (key, provider_type.label)
        for key, provider_type in sorted(APPROVED_DISCOVERY_PROVIDERS.items())
    )


def get_discovery_provider(provider_key: str) -> DiscoveryProvider:
    provider_type = APPROVED_DISCOVERY_PROVIDERS.get(provider_key)
    if provider_type is None:
        raise DiscoveryProviderError(
            f"Discovery provider {provider_key!r} is not in the approved provider registry."
        )
    return provider_type()


def build_discovery_query(profile: CareerProfile) -> DiscoveryQuery:
    return DiscoveryQuery(
        target_roles=_split_lines(profile.target_roles),
        target_industries=_split_lines(profile.target_industries),
        preferred_locations=_split_lines(profile.preferred_locations),
        preferred_work_arrangement=profile.preferred_work_arrangement,
        preferred_employment_type=profile.preferred_employment_type,
        experience_level=profile.experience_level,
    )


def _validate_opportunity(item: DiscoveredOpportunity) -> None:
    if not isinstance(item, DiscoveredOpportunity):
        raise DiscoveryProviderError(
            "Approved providers must return DiscoveredOpportunity records."
        )
    if not item.external_id.strip() and not item.source_url.strip():
        raise DiscoveryProviderError(
            "A provider result must include an external identifier or source URL."
        )
    if item.source_url:
        parsed = urlsplit(item.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DiscoveryProviderError(
                f"Provider returned an invalid source URL: {item.source_url!r}."
            )
    if len(item.raw_listing_text.strip()) < 40:
        raise DiscoveryProviderError(
            "Provider results must preserve enough raw listing text for Job Processing."
        )


def _contains_phrase(haystack: str, phrase: str) -> bool:
    haystack = _normalize(haystack)
    phrase = _normalize(phrase)
    if not haystack or not phrase:
        return False
    return phrase in haystack or haystack in phrase


def assess_broad_relevance(item: DiscoveredOpportunity, query: DiscoveryQuery):
    reasons = []
    primary_preferences_present = bool(query.target_roles or query.target_industries)

    role_match = any(
        _contains_phrase(item.title_hint, target) for target in query.target_roles
    )
    if role_match:
        reasons.append("Title overlaps a target role.")

    industry_match = any(
        _contains_phrase(item.industry_hint, target)
        for target in query.target_industries
    )
    if industry_match:
        reasons.append("Industry overlaps a target industry.")

    location_match = any(
        _contains_phrase(item.location_hint, target)
        for target in query.preferred_locations
    )
    if location_match:
        reasons.append("Location overlaps a preferred location.")

    arrangement = _normalize(query.preferred_work_arrangement)
    arrangement_match = arrangement in {"", "flexible"} or _contains_phrase(
        item.work_arrangement_hint,
        arrangement,
    )
    if arrangement and arrangement != "flexible" and arrangement_match:
        reasons.append("Work arrangement matches the manual preference.")

    employment = _normalize(query.preferred_employment_type).replace("_", " ")
    employment_match = not employment or _contains_phrase(
        item.employment_type_hint,
        employment,
    )
    if employment and employment_match:
        reasons.append("Employment type matches the manual preference.")

    if role_match or industry_match:
        return RawJobOpportunity.BroadRelevance.BROAD_MATCH, reasons

    any_preferences = bool(
        primary_preferences_present
        or query.preferred_locations
        or arrangement not in {"", "flexible"}
        or employment
    )
    if not any_preferences:
        return RawJobOpportunity.BroadRelevance.UNKNOWN, [
            "No search preferences were available for a broad discovery label."
        ]

    if not primary_preferences_present and (
        location_match or (arrangement_match and employment_match)
    ):
        return RawJobOpportunity.BroadRelevance.BROAD_MATCH, reasons

    reasons.append(
        "No target-role or target-industry overlap was found; retain only for broad review."
    )
    return RawJobOpportunity.BroadRelevance.OUTSIDE, reasons


def _prior_discovery_duplicate(
    *,
    provider_key: str,
    external_id: str,
    normalized_url: str,
    text_hash: str,
):
    queryset = RawJobOpportunity.objects.all()
    if external_id:
        match = queryset.filter(
            provider_key=provider_key,
            external_id=external_id,
        ).first()
        if match:
            return match, "provider_external_id", "Same provider listing identifier"
    if normalized_url:
        match = queryset.filter(normalized_source_url=normalized_url).first()
        if match:
            return match, DUPLICATE_REASON_EXACT_URL, "Same normalized job URL"
    if text_hash:
        match = queryset.filter(raw_text_sha256=text_hash).first()
        if match:
            return match, DUPLICATE_REASON_EXACT_TEXT, "Same raw listing text"
    return None, "", ""


def _duplicate_state(item: DiscoveredOpportunity):
    normalized_url = normalize_source_url(item.source_url)
    text_hash = listing_text_sha256(item.raw_listing_text)
    role_hash = role_identity_sha256(
        title=item.title_hint,
        company=item.company_hint,
        location=item.location_hint,
    )
    details = []
    duplicate_of_opportunity = None
    duplicate_of_job = None

    prior, reason, label = _prior_discovery_duplicate(
        provider_key="fixture" if not item.metadata.get("provider_key") else str(item.metadata["provider_key"]),
        external_id=item.external_id.strip(),
        normalized_url=normalized_url,
        text_hash=text_hash,
    )
    if prior:
        duplicate_of_opportunity = prior
        details.append(
            {
                "scope": "discovery",
                "reason": reason,
                "reason_label": label,
                "blocking": True,
                "opportunity_id": prior.id,
                "title": prior.title_hint,
                "company": prior.company_hint,
            }
        )

    tracked_analysis = analyze_job_duplicates(
        source_url=item.source_url,
        raw_text=item.raw_listing_text,
        extracted_job={
            "title": item.title_hint,
            "company": item.company_hint,
            "location": item.location_hint,
        },
    )
    for candidate in tracked_analysis.get("candidates", []):
        details.append(
            {
                "scope": "tracked_job",
                **candidate,
            }
        )
        if candidate.get("blocking") and duplicate_of_job is None:
            duplicate_of_job = JobPosting.objects.filter(pk=candidate["job_id"]).first()

    blocking = any(bool(detail.get("blocking")) for detail in details)
    return {
        "normalized_url": normalized_url,
        "text_hash": text_hash,
        "role_hash": role_hash,
        "details": details,
        "blocking": blocking,
        "duplicate_of_opportunity": duplicate_of_opportunity,
        "duplicate_of_job": duplicate_of_job,
    }


def _save_provider_results(
    *,
    run: DiscoveryRun,
    provider: DiscoveryProvider,
    query: DiscoveryQuery,
    results: Iterable[DiscoveredOpportunity],
):
    opportunities = []
    for item in results:
        _validate_opportunity(item)
        metadata = dict(item.metadata)
        metadata.setdefault("provider_key", provider.key)
        item = DiscoveredOpportunity(
            external_id=item.external_id,
            source_url=item.source_url,
            title_hint=item.title_hint,
            company_hint=item.company_hint,
            location_hint=item.location_hint,
            raw_listing_text=item.raw_listing_text,
            employment_type_hint=item.employment_type_hint,
            work_arrangement_hint=item.work_arrangement_hint,
            industry_hint=item.industry_hint,
            seniority_hint=item.seniority_hint,
            metadata=metadata,
        )
        duplicate = _duplicate_state(item)
        relevance, relevance_reasons = assess_broad_relevance(item, query)
        status = (
            RawJobOpportunity.Status.DUPLICATE
            if duplicate["blocking"]
            else RawJobOpportunity.Status.NEW
        )
        opportunities.append(
            RawJobOpportunity.objects.create(
                run=run,
                provider_key=provider.key,
                provider_label=provider.label,
                provider_version=provider.version,
                external_id=item.external_id.strip(),
                source_url=item.source_url.strip(),
                normalized_source_url=duplicate["normalized_url"],
                title_hint=item.title_hint.strip(),
                company_hint=item.company_hint.strip(),
                location_hint=item.location_hint.strip(),
                employment_type_hint=item.employment_type_hint.strip(),
                work_arrangement_hint=item.work_arrangement_hint.strip(),
                industry_hint=item.industry_hint.strip(),
                seniority_hint=item.seniority_hint.strip(),
                raw_listing_text=item.raw_listing_text.strip(),
                raw_text_sha256=duplicate["text_hash"],
                role_identity_sha256=duplicate["role_hash"],
                provider_payload=metadata,
                broad_relevance=relevance,
                broad_relevance_reasons=relevance_reasons,
                duplicate_details=duplicate["details"],
                duplicate_of_opportunity=duplicate["duplicate_of_opportunity"],
                duplicate_of_job=duplicate["duplicate_of_job"],
                status=status,
            )
        )
    return opportunities


@transaction.atomic
def run_discovery(
    provider_key: str,
    *,
    trigger: str = DiscoveryRun.Trigger.MANUAL,
    profile: CareerProfile | None = None,
):
    provider = get_discovery_provider(provider_key)
    profile = profile or CareerProfile.get_solo()
    query = build_discovery_query(profile)
    run = DiscoveryRun.objects.create(
        provider_key=provider.key,
        provider_label=provider.label,
        provider_version=provider.version,
        trigger=trigger,
        status=DiscoveryRun.Status.RUNNING,
        query_payload=query.to_dict(),
    )

    try:
        results = tuple(provider.discover(query))
        opportunities = _save_provider_results(
            run=run,
            provider=provider,
            query=query,
            results=results,
        )
    except Exception as exc:
        run.status = DiscoveryRun.Status.FAILED
        run.error_message = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        if isinstance(exc, DiscoveryError):
            raise
        raise DiscoveryProviderError(str(exc)) from exc

    run.status = DiscoveryRun.Status.COMPLETED
    run.result_count = len(opportunities)
    run.new_count = sum(
        item.status == RawJobOpportunity.Status.NEW for item in opportunities
    )
    run.duplicate_count = sum(
        item.status == RawJobOpportunity.Status.DUPLICATE for item in opportunities
    )
    run.outside_preference_count = sum(
        item.broad_relevance == RawJobOpportunity.BroadRelevance.OUTSIDE
        for item in opportunities
    )
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "result_count",
            "new_count",
            "duplicate_count",
            "outside_preference_count",
            "completed_at",
        ]
    )
    return run


@transaction.atomic
def keep_duplicate_for_processing(opportunity: RawJobOpportunity):
    opportunity = RawJobOpportunity.objects.select_for_update().get(pk=opportunity.pk)
    if opportunity.status != RawJobOpportunity.Status.DUPLICATE:
        raise DiscoveryHandoffError("Only duplicate opportunities need an override.")
    opportunity.duplicate_override = True
    opportunity.status = RawJobOpportunity.Status.READY
    opportunity.decision_notes = (
        "User retained this opportunity after reviewing the discovery duplicate warning."
    )
    opportunity.save(
        update_fields=["duplicate_override", "status", "decision_notes", "updated_at"]
    )
    return opportunity


@transaction.atomic
def prepare_opportunity_for_processing(opportunity: RawJobOpportunity):
    opportunity = RawJobOpportunity.objects.select_for_update().get(pk=opportunity.pk)
    if not opportunity.can_send_to_processing:
        raise DiscoveryHandoffError(
            "This opportunity must be new, explicitly retained, or ready for retry before processing."
        )

    try:
        extraction = extract_job_with_fallback(
            opportunity.raw_listing_text,
            source_url=opportunity.source_url,
            source_label=opportunity.provider_label,
        )
    except JobExtractionError as exc:
        opportunity.status = RawJobOpportunity.Status.PROCESSING_FAILED
        opportunity.processing_error = str(exc)
        opportunity.save(update_fields=["status", "processing_error", "updated_at"])
        raise DiscoveryHandoffError(str(exc)) from exc

    duplicate_analysis = analyze_job_duplicates(
        source_url=opportunity.source_url,
        raw_text=opportunity.raw_listing_text,
        extracted_job=extraction.get("job", {}),
    )
    draft = {
        "raw_text": opportunity.raw_listing_text,
        "source_url": opportunity.source_url,
        "source_label": opportunity.provider_label,
        "extraction": extraction,
        "duplicate_analysis": duplicate_analysis,
        "discovery_opportunity_id": opportunity.id,
        "discovery_run_id": opportunity.run_id,
    }

    opportunity.status = RawJobOpportunity.Status.SENT_TO_PROCESSING
    opportunity.processing_error = ""
    opportunity.sent_to_processing_at = timezone.now()
    opportunity.save(
        update_fields=[
            "status",
            "processing_error",
            "sent_to_processing_at",
            "updated_at",
        ]
    )
    return draft


@transaction.atomic
def mark_opportunity_processed(opportunity_id: int, job: JobPosting):
    opportunity = RawJobOpportunity.objects.select_for_update().filter(
        pk=opportunity_id
    ).first()
    if opportunity is None:
        return None
    opportunity.status = RawJobOpportunity.Status.PROCESSED
    opportunity.processed_job = job
    opportunity.processed_at = timezone.now()
    opportunity.processing_error = ""
    opportunity.save(
        update_fields=[
            "status",
            "processed_job",
            "processed_at",
            "processing_error",
            "updated_at",
        ]
    )
    return opportunity


@transaction.atomic
def release_opportunity_handoff(opportunity_id: int):
    opportunity = RawJobOpportunity.objects.select_for_update().filter(
        pk=opportunity_id,
        status=RawJobOpportunity.Status.SENT_TO_PROCESSING,
    ).first()
    if opportunity is None:
        return None
    opportunity.status = (
        RawJobOpportunity.Status.READY
        if opportunity.duplicate_override
        else RawJobOpportunity.Status.NEW
    )
    opportunity.sent_to_processing_at = None
    opportunity.save(
        update_fields=["status", "sent_to_processing_at", "updated_at"]
    )
    return opportunity
