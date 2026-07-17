"""Controlled semantic layer on top of the calibrated MedTech matcher.

The existing matcher remains authoritative for direct aliases, explicit
relationships, weighting, eligibility, and blockers. This layer only revisits
selected evidence gaps and may convert them into capped semantic matches.
"""

from __future__ import annotations

from .matching import (
    CategoryScore,
    EvidenceMatch,
    split_evidence,
    split_lines,
)
from .semantic_similarity import best_semantic_match
from .software_strategy_matching import (
    analyze_job_match as analyze_software_aware_match,
)


MATCHER_VERSION = "2.3-controlled-semantic"
RELATED_INDUSTRY_THRESHOLD = 0.55
DIRECT_INDUSTRY_THRESHOLD = 0.85


SEMANTIC_ELIGIBLE_KINDS = {
    "role",
    "required_skill",
    "preferred_skill",
    "required_education",
    "preferred_education",
    "industry",
}


def _category_map(result):
    return {category.key: category for category in result.categories}


def _category_fraction(category):
    if not category or not category.available or category.weight <= 0:
        return 0.0
    return max(0.0, min(1.0, category.earned / category.weight))


def _replace_category(category, fraction, explanation):
    return CategoryScore(
        key=category.key,
        label=category.label,
        weight=category.weight,
        earned=category.weight * max(0.0, min(1.0, fraction)),
        available=category.available,
        explanation=explanation,
    )


def _gap_kind(gap, requirements):
    requirement = gap.requirement

    if requirement.startswith("Role:"):
        return "role", requirement.removeprefix("Role:").strip()
    if requirement.startswith("Industry:"):
        return "industry", requirement.removeprefix("Industry:").strip()
    if requirement.startswith("Required education:"):
        return (
            "required_education",
            requirement.removeprefix("Required education:").strip(),
        )
    if requirement.startswith("Preferred education:"):
        return (
            "preferred_education",
            requirement.removeprefix("Preferred education:").strip(),
        )

    # Hard and operational requirements are intentionally excluded.
    excluded_prefixes = (
        "Experience:",
        "Location:",
        "Work arrangement:",
        "Employment type:",
    )
    if requirement.startswith(excluded_prefixes):
        return "excluded", requirement

    required_items = split_lines(requirements.required_skills)
    preferred_items = split_lines(requirements.preferred_skills)
    if requirement in required_items:
        return "required_skill", requirement
    if requirement in preferred_items:
        return "preferred_skill", requirement
    return "excluded", requirement


def _profile_evidence(profile, kind):
    if kind == "role":
        return split_lines(profile.target_roles)
    if kind == "industry":
        return (
            split_lines(profile.target_industries)
            + split_evidence(profile.education_summary)
            + split_evidence(profile.additional_context)
        )
    if kind in {"required_education", "preferred_education"}:
        return (
            split_evidence(profile.education_summary)
            + split_lines(profile.skills)
        )
    return (
        split_lines(profile.skills)
        + split_evidence(profile.education_summary)
        + split_evidence(profile.additional_context)
        + split_lines(profile.priorities)
    )


def _apply_semantic_evidence(result, profile, requirements):
    result.semantic_matches = []
    retained_gaps = []

    for gap in result.gaps:
        kind, comparison_text = _gap_kind(gap, requirements)
        if kind not in SEMANTIC_ELIGIBLE_KINDS:
            retained_gaps.append(gap)
            continue

        evidence = _profile_evidence(profile, kind)
        semantic = best_semantic_match(comparison_text, evidence)
        if not semantic:
            retained_gaps.append(gap)
            continue

        result.semantic_matches.append(
            EvidenceMatch(
                requirement=gap.requirement,
                match_type="semantic",
                evidence=semantic.evidence,
                concept=semantic.explanation,
                strength=semantic.strength,
            )
        )

    result.gaps = retained_gaps


def _match_strengths(result):
    strengths = {}
    collections = (
        result.direct_matches,
        result.related_matches,
        getattr(result, "semantic_matches", []),
    )
    for collection in collections:
        for item in collection:
            strengths[item.requirement] = max(
                strengths.get(item.requirement, 0.0),
                item.strength,
            )
    return strengths


def _match_counts(result, requirement_labels):
    labels = set(requirement_labels)
    direct = sum(item.requirement in labels for item in result.direct_matches)
    related = sum(item.requirement in labels for item in result.related_matches)
    semantic = sum(
        item.requirement in labels
        for item in getattr(result, "semantic_matches", [])
    )
    missing = sum(item.requirement in labels for item in result.gaps)
    return direct, related, semantic, missing


def _average_strength(strengths, labels):
    if not labels:
        return 0.0
    return sum(strengths.get(label, 0.0) for label in labels) / len(labels)


def _reweight_semantic_categories(result, requirements):
    strengths = _match_strengths(result)
    semantic_requirements = {
        item.requirement for item in getattr(result, "semantic_matches", [])
    }
    revised = []

    required_labels = split_lines(requirements.required_skills)
    preferred_labels = split_lines(requirements.preferred_skills)
    required_education = [
        f"Required education: {item}"
        for item in split_lines(requirements.required_education)
    ]
    preferred_education = [
        f"Preferred education: {item}"
        for item in split_lines(requirements.preferred_education)
    ]

    for category in result.categories:
        if not category.available:
            revised.append(category)
            continue

        if category.key == "required_skills":
            fraction = _average_strength(strengths, required_labels)
            counts = _match_counts(result, required_labels)
            explanation = (
                f"{counts[0]} direct, {counts[1]} related, "
                f"{counts[2]} semantic, {counts[3]} missing."
            )
            revised.append(_replace_category(category, fraction, explanation))
        elif category.key == "preferred_skills":
            fraction = _average_strength(strengths, preferred_labels)
            counts = _match_counts(result, preferred_labels)
            explanation = (
                f"{counts[0]} direct, {counts[1]} related, "
                f"{counts[2]} semantic, {counts[3]} missing."
            )
            revised.append(_replace_category(category, fraction, explanation))
        elif category.key == "role":
            role_labels = [
                item.requirement
                for collection in (
                    result.direct_matches,
                    result.related_matches,
                    getattr(result, "semantic_matches", []),
                    result.gaps,
                )
                for item in collection
                if item.requirement.startswith("Role:")
            ]
            fraction = max(
                (strengths.get(label, 0.0) for label in role_labels),
                default=_category_fraction(category),
            )
            semantic_used = any(
                label in semantic_requirements for label in role_labels
            )
            explanation = (
                "Controlled semantic role evidence found; it is capped as "
                "adjacent rather than direct alignment."
                if semantic_used
                else category.explanation
            )
            revised.append(_replace_category(category, fraction, explanation))
        elif category.key == "industry":
            label = f"Industry: {requirements.industry}"
            fraction = strengths.get(label, _category_fraction(category))
            explanation = (
                "Controlled semantic industry evidence found; direct target-industry "
                "credit still requires explicit or normalized evidence."
                if label in semantic_requirements
                else category.explanation
            )
            revised.append(_replace_category(category, fraction, explanation))
        elif category.key == "education":
            earned = 0.0
            available = 0.0
            if required_education:
                available += 0.8
                earned += 0.8 * max(
                    (strengths.get(label, 0.0) for label in required_education),
                    default=0.0,
                )
            if preferred_education:
                available += 0.2
                earned += 0.2 * max(
                    (strengths.get(label, 0.0) for label in preferred_education),
                    default=0.0,
                )
            fraction = earned / available if available else _category_fraction(category)
            semantic_used = any(
                label in semantic_requirements
                for label in required_education + preferred_education
            )
            explanation = (
                f"{category.explanation} Semantic education evidence is capped "
                "and does not replace an explicitly required degree."
                if semantic_used
                else category.explanation
            )
            revised.append(_replace_category(category, fraction, explanation))
        else:
            revised.append(category)

    result.categories = revised


def _recalculate(result):
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


def _reclassify_track(result):
    categories = _category_map(result)
    industry = categories.get("industry")
    role = categories.get("role")
    if not industry or not industry.available:
        return

    industry_fraction = _category_fraction(industry)
    role_fraction = _category_fraction(role)
    if industry_fraction < RELATED_INDUSTRY_THRESHOLD:
        result.track = "OUTSIDE PRIORITY"
    elif (
        industry_fraction >= DIRECT_INDUSTRY_THRESHOLD
        and role_fraction >= 0.85
    ):
        result.track = "PRIORITY ROLE"
    elif role_fraction > 0:
        result.track = "ADJACENT OPPORTUNITY"
    else:
        result.track = "OUTSIDE PRIORITY"


def analyze_job_match(profile, job, requirements):
    """Return the calibrated matcher result with controlled semantic evidence."""

    result = analyze_software_aware_match(profile, job, requirements)
    result.matcher_version = MATCHER_VERSION
    result.semantic_matches = []
    if not result.has_requirements:
        return result

    _apply_semantic_evidence(result, profile, requirements)
    if result.semantic_matches:
        _reweight_semantic_categories(result, requirements)
        _recalculate(result)
        _reclassify_track(result)
    return result


__all__ = ("MATCHER_VERSION", "analyze_job_match")
