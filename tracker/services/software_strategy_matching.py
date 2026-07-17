"""Software-aware extension of the industry-first career strategy.

The industry-first matcher remains the foundation. This layer makes software a
recognized technical path while preserving the user's stated preference for
medical-device industry entry:

- medical-device software can be a priority path;
- embedded, firmware, controls, software V&V, test automation, and software
  quality roles can be credible adjacent entry paths;
- software roles outside the target industry still receive skill credit, but
  do not become strategic priority opportunities solely because of title.
"""

from __future__ import annotations

from .matching import CategoryScore, EvidenceMatch, normalize_text
from .strategy_matching import (
    analyze_job_match as analyze_industry_first_match,
)


MATCHER_VERSION = "2.2-industry-first-software"

SOFTWARE_MEDTECH_ENTRY_TERMS = (
    "software engineer",
    "software engineering",
    "software developer",
    "software development",
    "medical device software",
    "healthcare software",
    "health technology software",
    "digital health software",
    "embedded software",
    "embedded systems",
    "firmware engineer",
    "firmware engineering",
    "firmware developer",
    "controls engineer",
    "controls engineering",
    "control systems engineer",
    "robotics software",
    "systems software",
    "software test engineer",
    "software testing",
    "test automation engineer",
    "test automation",
    "software validation engineer",
    "software verification engineer",
    "software quality engineer",
    "software quality assurance",
    "software design assurance",
    "software reliability engineer",
    "software integration engineer",
    "application software engineer",
    "clinical software engineer",
    "cybersecurity engineer",
    "product security engineer",
)

SOFTWARE_TRANSFERABLE_ROLE_STRENGTH = 0.80
DIRECT_INDUSTRY_THRESHOLD = 0.85
RELATED_INDUSTRY_THRESHOLD = 0.55


def _category_map(result):
    return {category.key: category for category in result.categories}


def _category_fraction(category):
    if not category or not category.available or category.weight <= 0:
        return 0.0
    return max(0.0, min(1.0, category.earned / category.weight))


def _is_software_role(job, requirements):
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
        for term in SOFTWARE_MEDTECH_ENTRY_TERMS
    )


def _role_label(job, requirements):
    return (
        getattr(requirements, "role_family", "") if requirements else ""
    ) or getattr(job, "title", "") or "Software role"


def _replace_role_gap(result, job, requirements):
    result.gaps = [
        item
        for item in result.gaps
        if not item.requirement.startswith("Role:")
    ]

    if not any(
        item.requirement.startswith("Role:")
        and item.concept == "Software pathway into MedTech"
        for item in result.related_matches
    ):
        result.related_matches.append(
            EvidenceMatch(
                requirement=f"Role: {_role_label(job, requirements)}",
                match_type="related",
                evidence="Software is an accepted technical pathway into MedTech",
                concept="Software pathway into MedTech",
                strength=SOFTWARE_TRANSFERABLE_ROLE_STRENGTH,
            )
        )


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


def analyze_job_match(profile, job, requirements):
    """Return an industry-first result with an explicit software pathway."""

    result = analyze_industry_first_match(profile, job, requirements)
    result.matcher_version = MATCHER_VERSION
    if not result.has_requirements:
        return result

    categories = _category_map(result)
    industry = categories.get("industry")
    role = categories.get("role")
    industry_fraction = _category_fraction(industry)
    role_fraction = _category_fraction(role)
    software_role = _is_software_role(job, requirements)

    qualifies_for_software_path = (
        software_role
        and industry_fraction >= RELATED_INDUSTRY_THRESHOLD
    )

    if qualifies_for_software_path and role_fraction < SOFTWARE_TRANSFERABLE_ROLE_STRENGTH:
        revised_categories = []
        for category in result.categories:
            if category.key == "role":
                revised_categories.append(
                    CategoryScore(
                        key=category.key,
                        label=category.label,
                        weight=category.weight,
                        earned=(
                            category.weight
                            * SOFTWARE_TRANSFERABLE_ROLE_STRENGTH
                        ),
                        available=True,
                        explanation=(
                            "Software, embedded, firmware, controls, automation, "
                            "or software-quality work is a recognized technical "
                            "path into the target MedTech ecosystem."
                        ),
                    )
                )
            else:
                revised_categories.append(category)
        result.categories = revised_categories
        role_fraction = SOFTWARE_TRANSFERABLE_ROLE_STRENGTH
        _replace_role_gap(result, job, requirements)
        _recalculate(result)

    if industry and industry.available:
        if industry_fraction < RELATED_INDUSTRY_THRESHOLD:
            result.track = "OUTSIDE PRIORITY"
        elif industry_fraction >= DIRECT_INDUSTRY_THRESHOLD and role_fraction >= 0.85:
            result.track = "PRIORITY ROLE"
        elif qualifies_for_software_path:
            result.track = "ADJACENT OPPORTUNITY"

    return result


__all__ = ("MATCHER_VERSION", "analyze_job_match")
