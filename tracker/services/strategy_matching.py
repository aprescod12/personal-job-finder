"""Career-strategy layer applied on top of the transparent base matcher.

The base matcher remains responsible for evidence extraction and category-level
comparison. This module applies Amiri's calibrated search strategy:

- entering the medical-device industry is more important than an exact title;
- medical-device product development remains the preferred function;
- technical functions surrounding development receive transferable credit;
- unrelated commercial functions do not receive technical credit solely because
  they are inside a target industry.
"""

from __future__ import annotations

from dataclasses import replace

from .matching import (
    CategoryScore,
    EvidenceMatch,
    analyze_job_match as analyze_base_job_match,
    concepts_in,
    match_item,
    normalize_text,
    split_lines,
)


MATCHER_VERSION = "2.1-industry-first"

CATEGORY_WEIGHTS = {
    "role": 10,
    "required_skills": 20,
    "preferred_skills": 10,
    "education": 15,
    "experience": 15,
    "industry": 20,
    "location_arrangement": 5,
    "employment_type": 5,
}

# These functions can provide a credible first step into medical-device product
# development. They receive related-role credit only when the job is also inside
# a target or closely related industry.
TECHNICAL_MEDTECH_ENTRY_TERMS = (
    "product safety",
    "electrical safety",
    "quality engineer",
    "quality engineering",
    "design assurance",
    "validation engineer",
    "validation engineering",
    "verification engineer",
    "verification engineering",
    "v&v",
    "v and v",
    "test engineer",
    "test engineering",
    "systems engineer",
    "systems engineering",
    "manufacturing engineer",
    "manufacturing engineering",
    "process engineer",
    "process engineering",
    "new product introduction",
    "npi engineer",
    "reliability engineer",
    "reliability engineering",
    "regulatory engineer",
    "regulatory engineering",
    "compliance engineer",
    "compliance engineering",
    "product engineer",
    "product engineering",
    "product development",
    "research and development",
    "r&d engineer",
    "engineering technician",
    "clinical engineer",
    "clinical engineering",
    "applications engineer",
    "application engineer",
    "field service engineer",
)

TRANSFERABLE_ROLE_STRENGTH = 0.70
DIRECT_INDUSTRY_THRESHOLD = 0.85
RELATED_INDUSTRY_THRESHOLD = 0.55


def _category_fraction(category):
    if not category or not category.available or category.weight <= 0:
        return 0.0
    return max(0.0, min(1.0, category.earned / category.weight))


def _category_map(result):
    return {category.key: category for category in result.categories}


def _technical_medtech_entry_role(job, requirements):
    role_text = "\n".join(
        value
        for value in (
            getattr(requirements, "role_family", "") if requirements else "",
            getattr(job, "title", ""),
        )
        if value
    )
    normalized_role = normalize_text(role_text)
    return any(
        normalize_text(term) in normalized_role
        for term in TECHNICAL_MEDTECH_ENTRY_TERMS
    )


def _replace_role_gap_with_transferable_evidence(result, job, requirements):
    role_values = [
        value
        for value in (
            getattr(requirements, "role_family", "") if requirements else "",
            getattr(job, "title", ""),
        )
        if value
    ]
    role_label = role_values[0] if role_values else "Technical MedTech role"

    result.gaps = [
        item
        for item in result.gaps
        if not item.requirement.startswith("Role:")
    ]

    if not any(
        item.requirement.startswith("Role:")
        for item in result.related_matches
    ):
        result.related_matches.append(
            EvidenceMatch(
                requirement=f"Role: {role_label}",
                match_type="related",
                evidence="Medical-device industry entry strategy",
                concept="Transferable technical MedTech function",
                strength=TRANSFERABLE_ROLE_STRENGTH,
            )
        )


def _reweight_categories(result, job, requirements):
    original = _category_map(result)
    industry_fraction = _category_fraction(original.get("industry"))
    role_fraction = _category_fraction(original.get("role"))

    transferable_role = (
        industry_fraction >= RELATED_INDUSTRY_THRESHOLD
        and _technical_medtech_entry_role(job, requirements)
        and role_fraction < TRANSFERABLE_ROLE_STRENGTH
    )
    if transferable_role:
        role_fraction = TRANSFERABLE_ROLE_STRENGTH
        _replace_role_gap_with_transferable_evidence(result, job, requirements)

    revised_categories = []
    for category in result.categories:
        weight = CATEGORY_WEIGHTS[category.key]
        fraction = _category_fraction(category)
        explanation = category.explanation

        if category.key == "role" and transferable_role:
            fraction = role_fraction
            explanation = (
                "Transferable technical function inside the target medical-device "
                "ecosystem. Exact title alignment is not required for entry."
            )
        elif category.key == "industry" and category.available:
            explanation = (
                f"{category.explanation} Industry entry is weighted above exact "
                "function because the career strategy allows later internal pivots."
            )

        revised_categories.append(
            CategoryScore(
                key=category.key,
                label=category.label,
                weight=weight,
                earned=weight * fraction,
                available=category.available,
                explanation=explanation,
            )
        )

    result.categories = revised_categories
    return role_fraction, industry_fraction, transferable_role


def _recalculate_score(result):
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


def _reclassify_track(
    result,
    *,
    role_fraction,
    industry_fraction,
    industry_available,
    transferable_role,
):
    if not industry_available:
        # Missing industry evidence should not erase a clear role relationship,
        # but it should remain a prompt to complete the requirements record.
        return

    if industry_fraction < RELATED_INDUSTRY_THRESHOLD:
        result.track = "OUTSIDE PRIORITY"
        return

    if (
        industry_fraction >= DIRECT_INDUSTRY_THRESHOLD
        and role_fraction >= 0.85
    ):
        result.track = "PRIORITY ROLE"
        return

    if (
        industry_fraction >= RELATED_INDUSTRY_THRESHOLD
        and (role_fraction > 0 or transferable_role)
    ):
        result.track = "ADJACENT OPPORTUNITY"
        return

    result.track = "OUTSIDE PRIORITY"


def analyze_job_match(profile, job, requirements):
    """Return a transparent match result calibrated to industry-first entry."""

    result = analyze_base_job_match(profile, job, requirements)
    if not result.has_requirements:
        return result

    role_fraction, industry_fraction, transferable_role = _reweight_categories(
        result,
        job,
        requirements,
    )
    _recalculate_score(result)

    industry_category = _category_map(result).get("industry")
    _reclassify_track(
        result,
        role_fraction=role_fraction,
        industry_fraction=industry_fraction,
        industry_available=bool(industry_category and industry_category.available),
        transferable_role=transferable_role,
    )

    return result


__all__ = (
    "CATEGORY_WEIGHTS",
    "MATCHER_VERSION",
    "analyze_job_match",
    "concepts_in",
    "match_item",
    "normalize_text",
    "split_lines",
)
