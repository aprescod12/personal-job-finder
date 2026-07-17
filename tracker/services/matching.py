from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from .vocabulary import CONCEPTS, RELATED_CONCEPTS, ROLE_RELATIONSHIPS


CATEGORY_WEIGHTS = {
    "role": 20,
    "required_skills": 25,
    "preferred_skills": 10,
    "education": 15,
    "experience": 15,
    "industry": 5,
    "location_arrangement": 5,
    "employment_type": 5,
}

PROFILE_EXPERIENCE_YEARS = {
    "entry_level": 1,
    "early_career": 3,
    "mid_level": 6,
    "senior": 12,
}


@dataclass(frozen=True)
class EvidenceMatch:
    requirement: str
    match_type: str
    evidence: str = ""
    concept: str = ""
    strength: float = 0.0


@dataclass(frozen=True)
class CategoryScore:
    key: str
    label: str
    weight: float
    earned: float
    available: bool
    explanation: str

    @property
    def percent(self):
        if not self.available or self.weight <= 0:
            return 0
        return round(100 * self.earned / self.weight)


@dataclass
class MatchResult:
    score: int
    classification: str
    track: str
    evidence_coverage: int
    categories: list[CategoryScore] = field(default_factory=list)
    direct_matches: list[EvidenceMatch] = field(default_factory=list)
    related_matches: list[EvidenceMatch] = field(default_factory=list)
    gaps: list[EvidenceMatch] = field(default_factory=list)
    confirmed_blockers: list[str] = field(default_factory=list)
    review_blockers: list[str] = field(default_factory=list)
    has_requirements: bool = True

    @property
    def is_disqualified(self):
        return bool(self.confirmed_blockers)


@dataclass(frozen=True)
class ItemMatch:
    match_type: str
    evidence: str
    concept: str
    strength: float


def split_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def split_evidence(value):
    if not value:
        return []
    pieces = re.split(r"[\n.;|]+", value)
    return [piece.strip() for piece in pieces if piece.strip()]


def normalize_text(value):
    value = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode()
    )
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9+#]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _phrase_present(normalized_text, normalized_phrase):
    if not normalized_phrase:
        return False
    if len(normalized_phrase) <= 3:
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
                normalized_text,
            )
        )
    return normalized_phrase in normalized_text


def concepts_in(value, *, role_only=False):
    normalized = normalize_text(value)
    found = set()

    for concept, details in CONCEPTS.items():
        is_role = concept.startswith("role_")
        if role_only != is_role:
            continue

        for alias in details["aliases"]:
            if _phrase_present(normalized, normalize_text(alias)):
                found.add(concept)
                break

    return found


def concept_label(concept):
    return CONCEPTS.get(concept, {}).get(
        "label",
        concept.replace("_", " ").title(),
    )


def related_strength(left, right, relations):
    if left == right:
        return 1.0
    return max(
        relations.get(left, {}).get(right, 0.0),
        relations.get(right, {}).get(left, 0.0),
    )


def _token_similarity(left, right):
    left_tokens = {
        token for token in normalize_text(left).split() if len(token) > 2
    }
    right_tokens = {
        token for token in normalize_text(right).split() if len(token) > 2
    }

    if not left_tokens or not right_tokens:
        return 0.0

    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def match_item(requirement, evidence_items: Iterable[str], *, role=False):
    requirement_norm = normalize_text(requirement)
    requirement_concepts = concepts_in(requirement, role_only=role)
    relations = ROLE_RELATIONSHIPS if role else RELATED_CONCEPTS
    best = ItemMatch("missing", "", "", 0.0)

    for evidence in evidence_items:
        evidence_norm = normalize_text(evidence)
        evidence_concepts = concepts_in(evidence, role_only=role)

        if requirement_norm and (
            requirement_norm == evidence_norm
            or (
                len(requirement_norm) >= 5
                and requirement_norm in evidence_norm
            )
            or (
                len(evidence_norm) >= 5
                and evidence_norm in requirement_norm
            )
        ):
            return ItemMatch("direct", evidence, "Exact vocabulary", 1.0)

        shared = requirement_concepts & evidence_concepts
        if shared:
            concept = sorted(shared)[0]
            return ItemMatch(
                "direct",
                evidence,
                concept_label(concept),
                1.0,
            )

        for required_concept in requirement_concepts:
            for evidence_concept in evidence_concepts:
                strength = related_strength(
                    required_concept,
                    evidence_concept,
                    relations,
                )
                if strength > best.strength:
                    best = ItemMatch(
                        "related",
                        evidence,
                        (
                            f"{concept_label(required_concept)} ↔ "
                            f"{concept_label(evidence_concept)}"
                        ),
                        strength,
                    )

        token_similarity = _token_similarity(requirement, evidence)
        if token_similarity >= 0.60 and token_similarity > best.strength:
            best = ItemMatch(
                "related",
                evidence,
                "Shared technical vocabulary",
                min(0.75, token_similarity),
            )

    return best


def _add_match(result, requirement, matched):
    evidence = EvidenceMatch(
        requirement=requirement,
        match_type=matched.match_type,
        evidence=matched.evidence,
        concept=matched.concept,
        strength=matched.strength,
    )

    if matched.match_type == "direct":
        result.direct_matches.append(evidence)
    elif matched.match_type == "related":
        result.related_matches.append(evidence)
    else:
        result.gaps.append(evidence)


def _list_component(requirements, evidence_items, result):
    if not requirements:
        return 0.0, "No requirements entered."

    total = 0.0
    direct = 0
    related = 0
    missing = 0

    for requirement in requirements:
        matched = match_item(requirement, evidence_items)
        _add_match(result, requirement, matched)
        total += matched.strength

        if matched.match_type == "direct":
            direct += 1
        elif matched.match_type == "related":
            related += 1
        else:
            missing += 1

    return (
        total / len(requirements),
        f"{direct} direct, {related} related, {missing} missing.",
    )


def _category(key, fraction, available, explanation):
    weight = CATEGORY_WEIGHTS[key]
    earned = weight * max(0.0, min(1.0, fraction))
    return CategoryScore(
        key=key,
        label=key.replace("_", " ").upper(),
        weight=weight,
        earned=earned,
        available=available,
        explanation=explanation,
    )


def _role_category(profile, job, requirements, result):
    targets = split_lines(profile.target_roles)
    job_roles = [
        value for value in (requirements.role_family, job.title) if value
    ]

    if not targets or not job_roles:
        return (
            _category(
                "role",
                0,
                False,
                "Target roles or job role are missing.",
            ),
            "OUTSIDE PRIORITY",
        )

    best = ItemMatch("missing", "", "", 0.0)
    best_requirement = job_roles[0]

    for job_role in job_roles:
        matched = match_item(job_role, targets, role=True)
        if matched.strength > best.strength:
            best = matched
            best_requirement = job_role

    _add_match(result, f"Role: {best_requirement}", best)

    if best.match_type == "direct":
        track = "PRIORITY ROLE"
    elif best.match_type == "related":
        track = "ADJACENT OPPORTUNITY"
    else:
        track = "OUTSIDE PRIORITY"

    if best.match_type == "missing":
        explanation = "No target-role relationship identified."
    else:
        explanation = f"{best.match_type.title()} role alignment."

    return _category("role", best.strength, True, explanation), track


def _education_category(profile, requirements, result):
    required = split_lines(requirements.required_education)
    preferred = split_lines(requirements.preferred_education)

    if not required and not preferred:
        return _category(
            "education",
            0,
            False,
            "No education requirements entered.",
        )

    evidence = split_evidence(profile.education_summary) + split_lines(
        profile.skills
    )
    earned_fraction = 0.0
    available_subweight = 0.0
    explanations = []

    if required:
        available_subweight += 0.8
        matches = [
            (item, match_item(item, evidence)) for item in required
        ]
        best_item, best = max(matches, key=lambda pair: pair[1].strength)
        _add_match(result, f"Required education: {best_item}", best)
        earned_fraction += 0.8 * best.strength
        explanations.append(
            f"Required education: {best.match_type}."
        )

    if preferred:
        available_subweight += 0.2
        matches = [
            (item, match_item(item, evidence)) for item in preferred
        ]
        best_item, best = max(matches, key=lambda pair: pair[1].strength)
        _add_match(result, f"Preferred education: {best_item}", best)
        earned_fraction += 0.2 * best.strength
        explanations.append(
            f"Preferred education: {best.match_type}."
        )

    fraction = (
        earned_fraction / available_subweight
        if available_subweight
        else 0.0
    )
    return _category(
        "education",
        fraction,
        True,
        " ".join(explanations),
    )


def _experience_category(profile, requirements, result):
    minimum = requirements.minimum_years_experience
    seniority = requirements.seniority_level

    if (
        minimum is None
        and seniority == requirements.SeniorityLevel.UNKNOWN
    ):
        return _category(
            "experience",
            0,
            False,
            "No experience requirement entered.",
        )

    profile_years = PROFILE_EXPERIENCE_YEARS.get(
        profile.experience_level,
        1,
    )

    if minimum is not None:
        if minimum <= profile_years:
            fraction = 1.0
            message = (
                f"Profile level supports an estimated {profile_years} years; "
                f"job asks for {minimum}."
            )
            matched = ItemMatch(
                "direct",
                profile.get_experience_level_display(),
                "Experience level",
                1.0,
            )
        elif minimum == profile_years + 1:
            fraction = 0.60
            message = (
                f"Job asks for {minimum} years, slightly above the profile "
                f"estimate of {profile_years}."
            )
            matched = ItemMatch(
                "related",
                profile.get_experience_level_display(),
                "Near experience range",
                0.60,
            )
        else:
            fraction = 0.0
            message = (
                f"Job asks for {minimum} years; profile level is estimated "
                f"at {profile_years}."
            )
            matched = ItemMatch("missing", "", "", 0.0)
    else:
        levels = {
            requirements.SeniorityLevel.INTERNSHIP: {
                "entry_level": 1,
                "early_career": 1,
                "mid_level": 1,
                "senior": 1,
            },
            requirements.SeniorityLevel.ENTRY_LEVEL: {
                "entry_level": 1,
                "early_career": 1,
                "mid_level": 1,
                "senior": 1,
            },
            requirements.SeniorityLevel.EARLY_CAREER: {
                "entry_level": 0.70,
                "early_career": 1,
                "mid_level": 1,
                "senior": 1,
            },
            requirements.SeniorityLevel.MID_LEVEL: {
                "entry_level": 0.20,
                "early_career": 0.50,
                "mid_level": 1,
                "senior": 1,
            },
            requirements.SeniorityLevel.SENIOR: {
                "entry_level": 0,
                "early_career": 0.20,
                "mid_level": 0.60,
                "senior": 1,
            },
            requirements.SeniorityLevel.LEAD_MANAGER: {
                "entry_level": 0,
                "early_career": 0.10,
                "mid_level": 0.50,
                "senior": 0.85,
            },
        }
        fraction = levels.get(seniority, {}).get(
            profile.experience_level,
            0.0,
        )
        message = (
            f"{profile.get_experience_level_display()} profile compared "
            f"with {requirements.get_seniority_level_display()} role."
        )

        if fraction >= 0.85:
            match_type = "direct"
        elif fraction >= 0.45:
            match_type = "related"
        else:
            match_type = "missing"

        matched = ItemMatch(
            match_type,
            profile.get_experience_level_display() if fraction else "",
            "Seniority level",
            fraction,
        )

    _add_match(
        result,
        f"Experience: {requirements.experience_range}",
        matched,
    )
    return _category("experience", fraction, True, message)


def _industry_category(profile, requirements, result):
    if not requirements.industry:
        return _category(
            "industry",
            0,
            False,
            "No industry entered.",
        )

    targets = split_lines(profile.target_industries)
    if not targets:
        return _category(
            "industry",
            0,
            False,
            "No target industries entered in the profile.",
        )

    matched = match_item(requirements.industry, targets)
    _add_match(result, f"Industry: {requirements.industry}", matched)
    return _category(
        "industry",
        matched.strength,
        True,
        f"{matched.match_type.title()} industry alignment.",
    )


def _location_arrangement_category(profile, job, result):
    earned = 0.0
    available = 0.0
    messages = []
    preferred_locations = split_lines(profile.preferred_locations)

    if job.location and preferred_locations:
        available += 0.4
        location_match = match_item(job.location, preferred_locations)

        if (
            location_match.match_type == "missing"
            and "remote" in normalize_text(job.location)
        ):
            remote_evidence = next(
                (
                    item
                    for item in preferred_locations
                    if "remote" in normalize_text(item)
                ),
                "",
            )
            if remote_evidence:
                location_match = ItemMatch(
                    "direct",
                    remote_evidence,
                    "Remote location",
                    1.0,
                )

        earned += 0.4 * location_match.strength
        _add_match(result, f"Location: {job.location}", location_match)
        messages.append(
            f"Location: {location_match.match_type}."
        )

    if job.work_arrangement != job.WorkArrangement.UNKNOWN:
        available += 0.6
        preferred = profile.preferred_work_arrangement

        if (
            preferred == profile.PreferredWorkArrangement.FLEXIBLE
            or preferred == job.work_arrangement
        ):
            arrangement = ItemMatch(
                "direct",
                profile.get_preferred_work_arrangement_display(),
                "Work arrangement",
                1.0,
            )
        elif {
            preferred,
            job.work_arrangement,
        } == {
            profile.PreferredWorkArrangement.HYBRID,
            job.WorkArrangement.ONSITE,
        }:
            arrangement = ItemMatch(
                "related",
                profile.get_preferred_work_arrangement_display(),
                "Partly on-site",
                0.60,
            )
        else:
            arrangement = ItemMatch("missing", "", "", 0.0)

        earned += 0.6 * arrangement.strength
        _add_match(
            result,
            f"Work arrangement: {job.get_work_arrangement_display()}",
            arrangement,
        )
        messages.append(
            f"Arrangement: {arrangement.match_type}."
        )

    if not available:
        return _category(
            "location_arrangement",
            0,
            False,
            (
                "Location and work arrangement are not sufficiently "
                "specified."
            ),
        )

    return _category(
        "location_arrangement",
        earned / available,
        True,
        " ".join(messages),
    )


def _employment_category(profile, job, result):
    if job.employment_type == job.EmploymentType.UNKNOWN:
        return _category(
            "employment_type",
            0,
            False,
            "Employment type is not specified.",
        )

    if profile.preferred_employment_type == job.employment_type:
        matched = ItemMatch(
            "direct",
            profile.get_preferred_employment_type_display(),
            "Employment type",
            1.0,
        )
    else:
        matched = ItemMatch("missing", "", "", 0.0)

    _add_match(
        result,
        f"Employment type: {job.get_employment_type_display()}",
        matched,
    )
    return _category(
        "employment_type",
        matched.strength,
        True,
        f"{matched.match_type.title()} employment preference.",
    )


def _detect_blockers(profile, job, requirements, result):
    for blocker in split_lines(requirements.hard_disqualifiers):
        result.review_blockers.append(
            f"Posting blocker to verify: {blocker}"
        )

    authorization = normalize_text(profile.work_authorization)
    job_authorization = normalize_text(
        requirements.work_authorization_requirements
    )
    needs_sponsorship = any(
        phrase in authorization
        for phrase in (
            "need sponsorship",
            "needs sponsorship",
            "require sponsorship",
            "requires sponsorship",
        )
    )
    no_sponsorship = any(
        phrase in job_authorization
        for phrase in (
            "no sponsorship",
            "cannot sponsor",
            "unable to sponsor",
            "sponsorship not available",
        )
    )

    if needs_sponsorship and no_sponsorship:
        result.confirmed_blockers.append(
            "The profile indicates sponsorship is required, but the "
            "posting states sponsorship is unavailable."
        )
    elif job_authorization:
        result.review_blockers.append(
            "Work authorization requirement to verify: "
            f"{requirements.work_authorization_requirements.strip()}"
        )

    searchable_job = "\n".join(
        value
        for value in (
            job.title,
            job.description,
            requirements.role_family,
            requirements.industry,
            requirements.required_skills,
            requirements.preferred_skills,
            requirements.hard_disqualifiers,
            requirements.work_authorization_requirements,
        )
        if value
    )
    normalized_job = normalize_text(searchable_job)

    for deal_breaker in split_lines(profile.deal_breakers):
        normalized_breaker = normalize_text(deal_breaker)
        if normalized_breaker and normalized_breaker in normalized_job:
            result.confirmed_blockers.append(
                f"Profile deal-breaker found in posting: {deal_breaker}"
            )


def analyze_job_match(profile, job, requirements):
    has_requirements = bool(requirements and requirements.has_content)
    result = MatchResult(
        score=0,
        classification="NEEDS REQUIREMENTS",
        track="OUTSIDE PRIORITY",
        evidence_coverage=0,
        has_requirements=has_requirements,
    )

    if not has_requirements:
        return result

    role_category, track = _role_category(
        profile,
        job,
        requirements,
        result,
    )
    result.track = track
    result.categories.append(role_category)

    profile_skill_evidence = (
        split_lines(profile.skills)
        + split_evidence(profile.education_summary)
        + split_evidence(profile.additional_context)
        + split_lines(profile.priorities)
    )

    required_items = split_lines(requirements.required_skills)
    required_fraction, required_explanation = _list_component(
        required_items,
        profile_skill_evidence,
        result,
    )
    result.categories.append(
        _category(
            "required_skills",
            required_fraction,
            bool(required_items),
            required_explanation,
        )
    )

    preferred_items = split_lines(requirements.preferred_skills)
    preferred_fraction, preferred_explanation = _list_component(
        preferred_items,
        profile_skill_evidence,
        result,
    )
    result.categories.append(
        _category(
            "preferred_skills",
            preferred_fraction,
            bool(preferred_items),
            preferred_explanation,
        )
    )

    result.categories.append(
        _education_category(profile, requirements, result)
    )
    result.categories.append(
        _experience_category(profile, requirements, result)
    )
    result.categories.append(
        _industry_category(profile, requirements, result)
    )
    result.categories.append(
        _location_arrangement_category(profile, job, result)
    )
    result.categories.append(
        _employment_category(profile, job, result)
    )

    _detect_blockers(profile, job, requirements, result)

    available_weight = sum(
        category.weight
        for category in result.categories
        if category.available
    )
    earned = sum(
        category.earned
        for category in result.categories
        if category.available
    )
    result.evidence_coverage = round(available_weight)
    result.score = (
        round(100 * earned / available_weight)
        if available_weight
        else 0
    )

    if result.confirmed_blockers:
        result.classification = "DISQUALIFIED"
    elif result.evidence_coverage < 35:
        result.classification = "LOW CONFIDENCE"
    elif result.score >= 80:
        result.classification = "STRONG MATCH"
    elif result.score >= 65:
        result.classification = "GOOD MATCH"
    elif result.score >= 50:
        result.classification = "POSSIBLE MATCH"
    else:
        result.classification = "WEAK MATCH"

    if result.track == "OUTSIDE PRIORITY" and result.score >= 65:
        result.track = "ADJACENT OPPORTUNITY"

    return result
