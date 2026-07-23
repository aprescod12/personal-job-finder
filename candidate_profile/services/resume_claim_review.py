import hashlib
import json
import re
from collections import defaultdict, deque
from copy import deepcopy

from django.db import transaction
from django.utils import timezone

from candidate_profile.models import (
    CandidateProfileClaim,
    ResumeExtractionReview,
    ResumeReviewClaim,
    ResumeSource,
)


ENTRY_SECTIONS = (
    ("education", ResumeReviewClaim.Section.EDUCATION),
    ("experience", ResumeReviewClaim.Section.EXPERIENCE),
    ("projects", ResumeReviewClaim.Section.PROJECTS),
    ("certifications", ResumeReviewClaim.Section.CERTIFICATIONS),
    ("leadership", ResumeReviewClaim.Section.LEADERSHIP),
)


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _claim_is_empty(value):
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not any(not _claim_is_empty(item) for item in value)
    if isinstance(value, dict):
        return not any(not _claim_is_empty(item) for item in value.values())
    return value in {None, ""}


def _evidence_queues(extraction):
    queues = defaultdict(deque)
    for item in extraction.get("evidence", []):
        field = _clean_text(item.get("field"))
        if field:
            queues[field].append(item)
    return queues


def _take_evidence(queues, field, *, fallback_text="", consume=True):
    queue = queues.get(field)
    item = None
    if queue:
        item = queue.popleft() if consume else queue[0]
    return {
        "source_text": _clean_text((item or {}).get("source_text"))
        or _clean_text(fallback_text),
        "evidence_note": _clean_text((item or {}).get("note")),
    }


def _claim_payload(
    *,
    claim_key,
    field_path,
    section,
    claim_type,
    position,
    value,
    evidence,
):
    return ResumeReviewClaim(
        claim_key=claim_key,
        field_path=field_path,
        section=section,
        claim_type=claim_type,
        position=position,
        extracted_value=deepcopy(value),
        reviewed_value=deepcopy(value),
        source_text=evidence["source_text"],
        evidence_note=evidence["evidence_note"],
    )


def build_review_claims(extraction):
    identity = extraction.get("identity", {})
    profile = extraction.get("profile", {})
    evidence = _evidence_queues(extraction)
    claims = []

    for position, field_name in enumerate(("full_name", "email", "phone", "location")):
        value = _clean_text(identity.get(field_name))
        if not value:
            continue
        field_path = f"identity.{field_name}"
        claims.append(
            _claim_payload(
                claim_key=field_path,
                field_path=field_path,
                section=ResumeReviewClaim.Section.IDENTITY,
                claim_type=ResumeReviewClaim.ClaimType.SCALAR,
                position=position,
                value=value,
                evidence=_take_evidence(evidence, field_path, fallback_text=value),
            )
        )

    for index, value in enumerate(identity.get("links", [])):
        value = _clean_text(value)
        if not value:
            continue
        claims.append(
            _claim_payload(
                claim_key=f"identity.links.{index}",
                field_path="identity.links",
                section=ResumeReviewClaim.Section.IDENTITY,
                claim_type=ResumeReviewClaim.ClaimType.LIST_ITEM,
                position=10 + index,
                value=value,
                evidence=_take_evidence(
                    evidence,
                    "identity.links",
                    fallback_text=value,
                    consume=False,
                ),
            )
        )

    summary = _clean_text(profile.get("professional_summary"))
    if summary:
        claims.append(
            _claim_payload(
                claim_key="profile.professional_summary",
                field_path="profile.professional_summary",
                section=ResumeReviewClaim.Section.SUMMARY,
                claim_type=ResumeReviewClaim.ClaimType.SCALAR,
                position=0,
                value=summary,
                evidence=_take_evidence(
                    evidence,
                    "profile.professional_summary",
                    fallback_text=summary,
                ),
            )
        )

    for profile_key, section in ENTRY_SECTIONS:
        field_path = f"profile.{profile_key}"
        for index, raw_entry in enumerate(profile.get(profile_key, [])):
            entry = {
                "heading": _clean_text(raw_entry.get("heading")),
                "subheading": _clean_text(raw_entry.get("subheading")),
                "dates": _clean_text(raw_entry.get("dates")),
                "details": [
                    _clean_text(item)
                    for item in raw_entry.get("details", [])
                    if _clean_text(item)
                ],
            }
            if _claim_is_empty(entry):
                continue
            fallback_text = raw_entry.get("source_text") or "\n".join(
                item
                for item in (
                    entry["heading"],
                    entry["subheading"],
                    entry["dates"],
                    *entry["details"],
                )
                if item
            )
            claims.append(
                _claim_payload(
                    claim_key=f"{field_path}.{index}",
                    field_path=field_path,
                    section=section,
                    claim_type=ResumeReviewClaim.ClaimType.ENTRY,
                    position=index,
                    value=entry,
                    evidence=_take_evidence(
                        evidence,
                        field_path,
                        fallback_text=fallback_text,
                    ),
                )
            )

    for index, value in enumerate(profile.get("skills", [])):
        value = _clean_text(value)
        if not value:
            continue
        claims.append(
            _claim_payload(
                claim_key=f"profile.skills.{index}",
                field_path="profile.skills",
                section=ResumeReviewClaim.Section.SKILLS,
                claim_type=ResumeReviewClaim.ClaimType.LIST_ITEM,
                position=index,
                value=value,
                evidence=_take_evidence(
                    evidence,
                    "profile.skills",
                    fallback_text=value,
                    consume=False,
                ),
            )
        )

    return claims


@transaction.atomic
def create_resume_review(*, profile, source, document, extraction):
    now = timezone.now()
    ResumeExtractionReview.objects.filter(
        profile=profile,
        status__in=(
            ResumeExtractionReview.Status.PENDING,
            ResumeExtractionReview.Status.IN_REVIEW,
        ),
    ).update(
        status=ResumeExtractionReview.Status.STALE,
        completed_at=now,
        updated_at=now,
    )

    provider = extraction.get("provider", {})
    review = ResumeExtractionReview.objects.create(
        profile=profile,
        source=source,
        source_sha256=source.sha256,
        source_label=source.display_label,
        source_filename=source.original_filename,
        provider_key=_clean_text(provider.get("key")) or "unknown",
        provider_label=_clean_text(provider.get("label")) or "Unknown extractor",
        provider_version=_clean_text(provider.get("version")) or "unversioned",
        provider_mode=_clean_text(provider.get("mode")) or "unknown",
        document_parser_key=_clean_text(document.parser_key) or "unknown",
        document_parser_version=_clean_text(document.parser_version) or "unversioned",
        orchestration=deepcopy(extraction.get("orchestration", {})),
        warnings=deepcopy(extraction.get("warnings", [])),
        document_warnings=deepcopy(document.warnings),
    )

    claims = build_review_claims(extraction)
    for claim in claims:
        claim.review = review
    ResumeReviewClaim.objects.bulk_create(claims)
    return review


def _normalized_json(value):
    if isinstance(value, str):
        return _clean_text(value).casefold()
    if isinstance(value, list):
        return [_normalized_json(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalized_json(value[key])
            for key in sorted(value)
            if not _claim_is_empty(value[key])
        }
    return value


def semantic_key_for_claim(claim):
    value = claim.reviewed_value
    if claim.claim_type == ResumeReviewClaim.ClaimType.SCALAR:
        identity = f"scalar|{claim.field_path}"
    elif claim.claim_type == ResumeReviewClaim.ClaimType.LIST_ITEM:
        identity = (
            f"list|{claim.field_path}|"
            f"{json.dumps(_normalized_json(value), sort_keys=True)}"
        )
    else:
        value_dict = value if isinstance(value, dict) else {}
        heading = _clean_text(value_dict.get("heading")).casefold()
        subheading = _clean_text(value_dict.get("subheading")).casefold()
        if heading or subheading:
            identity = f"entry|{claim.section}|{heading}|{subheading}"
        else:
            identity = (
                f"entry|{claim.section}|"
                f"{json.dumps(_normalized_json(value), sort_keys=True)}"
            )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@transaction.atomic
def apply_approved_claims(review):
    review = ResumeExtractionReview.objects.select_for_update().get(pk=review.pk)
    if not review.is_open:
        raise ValueError("Only an open resume review can apply approved claims.")
    if review.source.sha256 != review.source_sha256:
        review.status = ResumeExtractionReview.Status.STALE
        review.completed_at = timezone.now()
        review.save(update_fields=["status", "completed_at", "updated_at"])
        raise ValueError("The resume source no longer matches this review.")

    now = timezone.now()
    applied = 0
    claims = list(
        review.claims.select_for_update().filter(
            decision=ResumeReviewClaim.Decision.APPROVED,
            applied_at__isnull=True,
        )
    )
    for claim in claims:
        if _claim_is_empty(claim.reviewed_value):
            raise ValueError(f"Approved claim {claim.field_path} cannot be blank.")

        semantic_key = semantic_key_for_claim(claim)
        CandidateProfileClaim.objects.filter(
            profile=review.profile,
            semantic_key=semantic_key,
            is_active=True,
        ).update(is_active=False, superseded_at=now)

        CandidateProfileClaim.objects.create(
            profile=review.profile,
            source=review.source,
            review_claim=claim,
            section=claim.section,
            claim_key=claim.claim_key,
            field_path=claim.field_path,
            semantic_key=semantic_key,
            value=deepcopy(claim.reviewed_value),
            source_text=claim.source_text,
            evidence_note=claim.evidence_note,
            source_sha256=review.source_sha256,
            source_label=review.source_label,
            source_filename=review.source_filename,
            provider_key=review.provider_key,
            provider_version=review.provider_version,
            provider_mode=review.provider_mode,
            document_parser_key=review.document_parser_key,
            document_parser_version=review.document_parser_version,
        )
        claim.applied_at = now
        claim.save(update_fields=["applied_at", "updated_at"])
        applied += 1

    pending_exists = review.claims.filter(
        decision=ResumeReviewClaim.Decision.PENDING
    ).exists()
    unapplied_approved_exists = review.claims.filter(
        decision=ResumeReviewClaim.Decision.APPROVED,
        applied_at__isnull=True,
    ).exists()
    if not pending_exists and not unapplied_approved_exists:
        review.status = ResumeExtractionReview.Status.COMPLETED
        review.completed_at = now
        review.source.review_status = ResumeSource.ReviewStatus.REVIEWED
        review.source.save(update_fields=["review_status", "updated_at"])
    else:
        review.status = ResumeExtractionReview.Status.IN_REVIEW
    review.save(update_fields=["status", "completed_at", "updated_at"])
    return applied


@transaction.atomic
def close_resume_review(review):
    review = ResumeExtractionReview.objects.select_for_update().get(pk=review.pk)
    if not review.is_open:
        return review

    now = timezone.now()
    review.claims.filter(
        decision=ResumeReviewClaim.Decision.PENDING,
        applied_at__isnull=True,
    ).update(decision=ResumeReviewClaim.Decision.REJECTED, updated_at=now)

    if review.claims.filter(applied_at__isnull=False).exists():
        review.status = ResumeExtractionReview.Status.COMPLETED
        review.source.review_status = ResumeSource.ReviewStatus.REVIEWED
    else:
        review.status = ResumeExtractionReview.Status.DISCARDED
        review.source.review_status = ResumeSource.ReviewStatus.REJECTED
    review.completed_at = now
    review.save(update_fields=["status", "completed_at", "updated_at"])
    review.source.save(update_fields=["review_status", "updated_at"])
    return review
