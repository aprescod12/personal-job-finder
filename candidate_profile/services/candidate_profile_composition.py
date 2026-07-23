from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from tracker.models import CareerProfile

from candidate_profile.models import CandidateProfileClaim, ResumeReviewClaim
from candidate_profile.snapshot_models import (
    CandidateProfileSnapshot,
    CandidateProfileSnapshotClaim,
)


COMPOSITION_VERSION = "candidate-profile-composer-v1"
SCALAR_FIELDS = {
    "identity.full_name",
    "identity.email",
    "identity.phone",
    "identity.location",
    "profile.professional_summary",
}
ENTRY_PATHS = {
    "profile.education": "education",
    "profile.experience": "experience",
    "profile.projects": "projects",
    "profile.certifications": "certifications",
    "profile.leadership": "leadership",
}


class CandidateProfileCompositionError(ValueError):
    pass


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_text(value).casefold()
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalized(value[key]) for key in sorted(value)}
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_value(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    return {
        "heading": _clean_text(value.get("heading")),
        "subheading": _clean_text(value.get("subheading")),
        "dates": _clean_text(value.get("dates")),
        "details": [
            _clean_text(item)
            for item in value.get("details", [])
            if _clean_text(item)
        ],
    }


def _claim_identity_key(claim: CandidateProfileClaim) -> tuple[str, str]:
    if claim.field_path in SCALAR_FIELDS:
        return ("scalar", claim.field_path)
    if claim.field_path in ENTRY_PATHS:
        return ("entry-slot", claim.claim_key)
    return ("list", claim.semantic_key)


def _select_claims(claims: list[CandidateProfileClaim]):
    selected: dict[tuple[str, str], CandidateProfileClaim] = {}
    collapsed = []

    for claim in claims:
        key = _claim_identity_key(claim)
        previous = selected.get(key)
        if previous is not None:
            collapsed.append(previous)
        selected[key] = claim

    ordered = sorted(
        selected.values(),
        key=lambda claim: (
            claim.section,
            claim.field_path,
            claim.approved_at,
            claim.id,
        ),
    )
    return ordered, collapsed


def _append_unique(values: list[Any], value: Any, seen: set[str]):
    key = _canonical_json(_normalized(value))
    if key in seen:
        return False
    seen.add(key)
    values.append(value)
    return True


def build_composed_profile(claims: list[CandidateProfileClaim]):
    selected, collapsed = _select_claims(claims)
    data = {
        "identity": {
            "full_name": "",
            "emails": [],
            "phone": "",
            "location": "",
            "links": [],
        },
        "profile": {
            "professional_summary": "",
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "certifications": [],
            "leadership": [],
        },
    }
    warnings = []
    used_claims = []
    seen_by_bucket: dict[str, set[str]] = {
        "emails": set(),
        "links": set(),
        "education": set(),
        "experience": set(),
        "projects": set(),
        "skills": set(),
        "certifications": set(),
        "leadership": set(),
    }

    if collapsed:
        warnings.append(
            f"Collapsed {len(collapsed)} older claim variant"
            f"{'s' if len(collapsed) != 1 else ''} using deterministic source precedence."
        )

    for claim in selected:
        value = claim.value
        included = False

        if claim.field_path == "identity.full_name":
            data["identity"]["full_name"] = _clean_text(value)
            included = bool(data["identity"]["full_name"])
        elif claim.field_path == "identity.email":
            for item in re.split(r"[|\n]+", _clean_text(value)):
                item = _clean_text(item)
                if item:
                    included = _append_unique(
                        data["identity"]["emails"],
                        item,
                        seen_by_bucket["emails"],
                    ) or included
        elif claim.field_path == "identity.phone":
            data["identity"]["phone"] = _clean_text(value)
            included = bool(data["identity"]["phone"])
        elif claim.field_path == "identity.location":
            data["identity"]["location"] = _clean_text(value)
            included = bool(data["identity"]["location"])
        elif claim.field_path == "identity.links":
            included = _append_unique(
                data["identity"]["links"],
                _clean_text(value),
                seen_by_bucket["links"],
            )
        elif claim.field_path == "profile.professional_summary":
            data["profile"]["professional_summary"] = _clean_text(value)
            included = bool(data["profile"]["professional_summary"])
        elif claim.field_path == "profile.skills":
            included = _append_unique(
                data["profile"]["skills"],
                _clean_text(value),
                seen_by_bucket["skills"],
            )
        elif claim.field_path in ENTRY_PATHS:
            bucket = ENTRY_PATHS[claim.field_path]
            included = _append_unique(
                data["profile"][bucket],
                _entry_value(value),
                seen_by_bucket[bucket],
            )

        if included:
            used_claims.append(claim)

    if not data["identity"]["full_name"]:
        warnings.append("No approved full-name claim is present; manual profile identity will remain the fallback.")
    if not data["profile"]["education"]:
        warnings.append("No approved education entries are present.")
    if not data["profile"]["skills"]:
        warnings.append("No approved skill claims are present.")
    if not data["profile"]["experience"]:
        warnings.append("No approved experience entries are present.")

    return data, warnings, used_claims


def _snapshot_fingerprint(data, claims):
    payload = {
        "composition_version": COMPOSITION_VERSION,
        "claim_ids": [claim.id for claim in claims],
        "claim_values": [claim.value for claim in claims],
        "data": data,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@transaction.atomic
def compose_candidate_profile_snapshot(profile: CareerProfile):
    CareerProfile.objects.select_for_update().get(pk=profile.pk)
    claims = list(
        CandidateProfileClaim.objects.filter(profile=profile, is_active=True)
        .select_related("review_claim")
        .order_by("approved_at", "id")
    )
    if not claims:
        raise CandidateProfileCompositionError(
            "Approve and apply at least one résumé claim before composing a candidate profile."
        )

    data, warnings, used_claims = build_composed_profile(claims)
    if not used_claims:
        raise CandidateProfileCompositionError(
            "The active approved claims did not produce any reusable candidate-profile fields."
        )

    fingerprint = _snapshot_fingerprint(data, used_claims)
    existing = CandidateProfileSnapshot.objects.filter(
        profile=profile,
        fingerprint=fingerprint,
    ).first()
    if existing:
        return existing, False

    latest_version = (
        CandidateProfileSnapshot.objects.filter(profile=profile).aggregate(
            value=Max("version")
        )["value"]
        or 0
    )
    snapshot = CandidateProfileSnapshot.objects.create(
        profile=profile,
        version=latest_version + 1,
        composition_version=COMPOSITION_VERSION,
        fingerprint=fingerprint,
        data=data,
        warnings=warnings,
        source_claim_count=len(used_claims),
    )
    CandidateProfileSnapshotClaim.objects.bulk_create(
        [
            CandidateProfileSnapshotClaim(
                snapshot=snapshot,
                candidate_claim=claim,
                position=position,
                section=claim.section,
                field_path=claim.field_path,
                semantic_key=claim.semantic_key,
                value=claim.value,
            )
            for position, claim in enumerate(used_claims)
        ]
    )
    return snapshot, True


@transaction.atomic
def activate_candidate_profile_snapshot(snapshot: CandidateProfileSnapshot):
    CareerProfile.objects.select_for_update().get(pk=snapshot.profile_id)
    snapshot = CandidateProfileSnapshot.objects.select_for_update().get(pk=snapshot.pk)
    if snapshot.status == CandidateProfileSnapshot.Status.ACTIVE:
        return snapshot, False

    now = timezone.now()
    CandidateProfileSnapshot.objects.filter(
        profile_id=snapshot.profile_id,
        status=CandidateProfileSnapshot.Status.ACTIVE,
    ).exclude(pk=snapshot.pk).update(
        status=CandidateProfileSnapshot.Status.ARCHIVED,
        archived_at=now,
    )
    snapshot.status = CandidateProfileSnapshot.Status.ACTIVE
    snapshot.activated_at = now
    snapshot.archived_at = None
    snapshot.save(
        update_fields=["status", "activated_at", "archived_at"]
    )
    return snapshot, True


def active_candidate_profile_snapshot(profile: CareerProfile):
    return CandidateProfileSnapshot.objects.filter(
        profile=profile,
        status=CandidateProfileSnapshot.Status.ACTIVE,
    ).first()


def _render_entry(entry: dict[str, Any]) -> str:
    parts = [
        _clean_text(entry.get("heading")),
        _clean_text(entry.get("subheading")),
        _clean_text(entry.get("dates")),
        *[
            _clean_text(item)
            for item in entry.get("details", [])
            if _clean_text(item)
        ],
    ]
    return "; ".join(part for part in parts if part)


def _merge_lines(*groups):
    merged = []
    seen = set()
    for group in groups:
        if isinstance(group, str):
            items = group.splitlines()
        else:
            items = group or []
        for item in items:
            item = _clean_text(item)
            key = item.casefold()
            if item and key not in seen:
                seen.add(key)
                merged.append(item)
    return "\n".join(merged)


@dataclass(frozen=True)
class ActivatedCandidateProfileAdapter:
    manual_profile: CareerProfile
    snapshot: CandidateProfileSnapshot

    def __getattr__(self, name):
        return getattr(self.manual_profile, name)

    @property
    def full_name(self):
        return self.snapshot.identity.get("full_name") or self.manual_profile.full_name

    @property
    def skills(self):
        return _merge_lines(
            self.snapshot.profile_data.get("skills", []),
            self.manual_profile.skills,
        )

    @property
    def education_summary(self):
        snapshot_lines = [
            _render_entry(entry)
            for entry in self.snapshot.profile_data.get("education", [])
        ]
        return _merge_lines(snapshot_lines, self.manual_profile.education_summary)

    @property
    def additional_context(self):
        evidence_lines = []
        for key in ("experience", "projects", "certifications", "leadership"):
            evidence_lines.extend(
                _render_entry(entry)
                for entry in self.snapshot.profile_data.get(key, [])
            )
        summary = self.snapshot.profile_data.get("professional_summary", "")
        return _merge_lines(summary, evidence_lines, self.manual_profile.additional_context)

    @property
    def candidate_snapshot_id(self):
        return self.snapshot.id

    @property
    def candidate_snapshot_version(self):
        return self.snapshot.version

    @property
    def candidate_snapshot_composition_version(self):
        return self.snapshot.composition_version


def effective_matching_profile(profile: CareerProfile):
    if isinstance(profile, ActivatedCandidateProfileAdapter):
        return profile
    snapshot = active_candidate_profile_snapshot(profile)
    if snapshot is None:
        return profile
    return ActivatedCandidateProfileAdapter(profile, snapshot)
