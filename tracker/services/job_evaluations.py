from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from django.db import transaction

from candidate_profile.services.candidate_profile_composition import (
    active_candidate_profile_snapshot,
)

from tracker.evaluation_models import JobEvaluationRun
from tracker.models import CareerProfile, JobPosting, JobRequirement
from tracker.services.semantic_strategy_matching import MATCHER_VERSION
from tracker.services.strategy_matching import analyze_job_match


PROFILE_FIELDS = (
    "full_name",
    "professional_headline",
    "education_summary",
    "target_roles",
    "target_industries",
    "skills",
    "experience_level",
    "preferred_locations",
    "preferred_work_arrangement",
    "preferred_employment_type",
    "minimum_salary",
    "work_authorization",
    "priorities",
    "deal_breakers",
    "additional_context",
)

JOB_FIELDS = (
    "title",
    "company",
    "location",
    "description",
    "employment_type",
    "work_arrangement",
    "salary_text",
)

REQUIREMENT_FIELDS = (
    "role_family",
    "seniority_level",
    "industry",
    "required_skills",
    "preferred_skills",
    "required_education",
    "preferred_education",
    "minimum_years_experience",
    "maximum_years_experience",
    "responsibilities",
    "certifications",
    "work_authorization_requirements",
    "hard_disqualifiers",
    "requirement_notes",
)


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value):
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def profile_input(profile):
    snapshot = active_candidate_profile_snapshot(profile)
    return {
        "manual": {field: getattr(profile, field) for field in PROFILE_FIELDS},
        "snapshot": (
            {
                "id": snapshot.id,
                "version": snapshot.version,
                "composition_version": snapshot.composition_version,
                "fingerprint": snapshot.fingerprint,
            }
            if snapshot
            else None
        ),
    }


def job_input(job, requirements):
    return {
        "job": {field: getattr(job, field) for field in JOB_FIELDS},
        "requirements": (
            {field: getattr(requirements, field) for field in REQUIREMENT_FIELDS}
            if requirements
            else None
        ),
    }


def profile_fingerprint(profile):
    return _fingerprint(profile_input(profile))


def job_fingerprint(job, requirements):
    return _fingerprint(job_input(job, requirements))


def _serialize_evidence(item):
    return {
        "requirement": item.requirement,
        "match_type": item.match_type,
        "evidence": item.evidence,
        "concept": item.concept,
        "strength": item.strength,
    }


def serialize_match_result(result):
    return {
        "score": result.score,
        "classification": result.classification,
        "track": result.track,
        "evidence_coverage": result.evidence_coverage,
        "has_requirements": result.has_requirements,
        "categories": [asdict(item) for item in result.categories],
        "direct_matches": [_serialize_evidence(item) for item in result.direct_matches],
        "related_matches": [_serialize_evidence(item) for item in result.related_matches],
        "semantic_matches": [
            _serialize_evidence(item) for item in getattr(result, "semantic_matches", [])
        ],
        "gaps": [_serialize_evidence(item) for item in result.gaps],
        "confirmed_blockers": list(result.confirmed_blockers),
        "review_blockers": list(result.review_blockers),
    }


def _evidence_key(item):
    return (
        str(item.get("requirement", "")).strip().casefold(),
        str(item.get("evidence", "")).strip().casefold(),
    )


def _requirement_key(item):
    return str(item.get("requirement", "")).strip().casefold()


def compare_results(previous, current):
    if not previous:
        return {
            "score_delta": None,
            "classification_changed": False,
            "track_changed": False,
            "added_direct": [],
            "removed_direct": [],
            "added_related": [],
            "removed_related": [],
            "resolved_gaps": [],
            "new_gaps": [],
        }

    previous_direct = {_evidence_key(item): item for item in previous.get("direct_matches", [])}
    current_direct = {_evidence_key(item): item for item in current.get("direct_matches", [])}
    previous_related = {
        _evidence_key(item): item
        for item in previous.get("related_matches", [])
        + previous.get("semantic_matches", [])
    }
    current_related = {
        _evidence_key(item): item
        for item in current.get("related_matches", [])
        + current.get("semantic_matches", [])
    }
    previous_gaps = {
        _requirement_key(item): item for item in previous.get("gaps", [])
    }
    current_gaps = {_requirement_key(item): item for item in current.get("gaps", [])}

    previous_score = previous.get("score")
    current_score = current.get("score")
    score_delta = (
        current_score - previous_score
        if isinstance(previous_score, int) and isinstance(current_score, int)
        else None
    )

    return {
        "score_delta": score_delta,
        "classification_changed": previous.get("classification")
        != current.get("classification"),
        "track_changed": previous.get("track") != current.get("track"),
        "added_direct": [
            current_direct[key] for key in current_direct.keys() - previous_direct.keys()
        ],
        "removed_direct": [
            previous_direct[key] for key in previous_direct.keys() - current_direct.keys()
        ],
        "added_related": [
            current_related[key]
            for key in current_related.keys() - previous_related.keys()
        ],
        "removed_related": [
            previous_related[key]
            for key in previous_related.keys() - current_related.keys()
        ],
        "resolved_gaps": [
            previous_gaps[key] for key in previous_gaps.keys() - current_gaps.keys()
        ],
        "new_gaps": [current_gaps[key] for key in current_gaps.keys() - previous_gaps.keys()],
    }


def stale_reasons(run, *, profile, job, requirements):
    reasons = []
    if run.matcher_version != MATCHER_VERSION:
        reasons.append("Matcher version changed")
    if run.profile_fingerprint != profile_fingerprint(profile):
        reasons.append("Candidate profile or manual preferences changed")
    if run.job_fingerprint != job_fingerprint(job, requirements):
        reasons.append("Job details or structured requirements changed")
    return reasons


@transaction.atomic
def refresh_evaluation_state(job, profile=None, requirements=None):
    profile = profile or CareerProfile.get_solo()
    requirements = requirements or JobRequirement.objects.filter(job=job).first()
    run = (
        JobEvaluationRun.objects.select_for_update()
        .filter(job=job, is_current=True)
        .first()
    )
    if run is None:
        return JobEvaluationRun.objects.filter(job=job).first()

    reasons = stale_reasons(
        run,
        profile=profile,
        job=job,
        requirements=requirements,
    )
    if reasons:
        run.is_current = False
        run.stale_reasons = reasons
        run.save(update_fields=["is_current", "stale_reasons"])
    return run


@transaction.atomic
def mark_evaluations_stale(*, reason, profile=None, job=None):
    queryset = JobEvaluationRun.objects.select_for_update().filter(is_current=True)
    if profile is not None:
        queryset = queryset.filter(profile=profile)
    if job is not None:
        queryset = queryset.filter(job=job)

    count = 0
    for run in queryset:
        reasons = list(run.stale_reasons)
        if reason not in reasons:
            reasons.append(reason)
        run.is_current = False
        run.stale_reasons = reasons
        run.save(update_fields=["is_current", "stale_reasons"])
        count += 1
    return count


@transaction.atomic
def evaluate_job(job, *, trigger=JobEvaluationRun.Trigger.MANUAL):
    profile = CareerProfile.get_solo()
    requirements = JobRequirement.objects.filter(job=job).first()
    job = JobPosting.objects.select_for_update().get(pk=job.pk)
    previous = JobEvaluationRun.objects.filter(job=job).first()

    result = analyze_job_match(profile, job, requirements)
    result_data = serialize_match_result(result)
    comparison = compare_results(previous.result_data if previous else None, result_data)
    snapshot = active_candidate_profile_snapshot(profile)

    JobEvaluationRun.objects.filter(job=job, is_current=True).update(
        is_current=False,
        stale_reasons=["Superseded by a newer evaluation run"],
    )

    return JobEvaluationRun.objects.create(
        job=job,
        profile=profile,
        candidate_snapshot=snapshot,
        previous_run=previous,
        trigger=trigger,
        matcher_version=getattr(result, "matcher_version", MATCHER_VERSION),
        candidate_snapshot_version=(snapshot.version if snapshot else None),
        candidate_snapshot_composition_version=(
            snapshot.composition_version if snapshot else ""
        ),
        profile_fingerprint=profile_fingerprint(profile),
        job_fingerprint=job_fingerprint(job, requirements),
        has_requirements=result.has_requirements,
        score=result.score if result.has_requirements else None,
        classification=result.classification,
        track=result.track,
        evidence_coverage=result.evidence_coverage,
        result_data=result_data,
        comparison_data=comparison,
        is_current=True,
    )


def evaluate_all_jobs():
    runs = []
    for job in JobPosting.objects.order_by("id"):
        runs.append(evaluate_job(job, trigger=JobEvaluationRun.Trigger.BULK))
    return runs


def latest_evaluation(job, *, refresh=True):
    if refresh:
        refresh_evaluation_state(job)
    return JobEvaluationRun.objects.filter(job=job).first()
