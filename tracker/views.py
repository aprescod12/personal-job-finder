from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .calibration_forms import MatchCalibrationForm
from .forms import CareerProfileForm, JobPostingForm, JobRequirementForm
from .models import CareerProfile, JobPosting, JobRequirement, MatchCalibration
from .services.matching import analyze_job_match


FIT_FILTER_CHOICES = (
    ("strong", "Strong match"),
    ("good", "Good match"),
    ("possible", "Possible match"),
    ("weak", "Weak match"),
    ("low_confidence", "Low confidence"),
    ("disqualified", "Disqualified"),
    ("needs_requirements", "Needs requirements"),
)

FIT_FILTER_MAP = {
    "strong": "STRONG MATCH",
    "good": "GOOD MATCH",
    "possible": "POSSIBLE MATCH",
    "weak": "WEAK MATCH",
    "low_confidence": "LOW CONFIDENCE",
    "disqualified": "DISQUALIFIED",
    "needs_requirements": "NEEDS REQUIREMENTS",
}

TRACK_FILTER_CHOICES = (
    ("priority", "Priority roles"),
    ("adjacent", "Adjacent opportunities"),
    ("outside", "Outside priority"),
)

TRACK_FILTER_MAP = {
    "priority": "PRIORITY ROLE",
    "adjacent": "ADJACENT OPPORTUNITY",
    "outside": "OUTSIDE PRIORITY",
}

REVIEW_FILTER_CHOICES = (
    ("reviewed", "Calibrated"),
    ("unreviewed", "Not calibrated"),
    ("agrees", "Program and judgment agree"),
    ("differs", "Program and judgment differ"),
)

SORT_CHOICES = (
    ("score_desc", "Best match first"),
    ("coverage_desc", "Best evidence coverage"),
    ("newest", "Newest added"),
    ("deadline", "Nearest deadline"),
)

VERDICT_CLASSIFICATIONS = {
    MatchCalibration.Verdict.STRONG: {"STRONG MATCH", "GOOD MATCH"},
    MatchCalibration.Verdict.POSSIBLE: {"POSSIBLE MATCH", "LOW CONFIDENCE"},
    MatchCalibration.Verdict.WEAK: {"WEAK MATCH"},
    MatchCalibration.Verdict.NOT_ELIGIBLE: {"DISQUALIFIED"},
}


def _calibration_alignment(calibration, match_result):
    if not calibration or calibration.verdict == MatchCalibration.Verdict.UNSURE:
        return "REVIEW"

    expected = VERDICT_CLASSIFICATIONS.get(calibration.verdict, set())
    return "AGREES" if match_result.classification in expected else "DIFFERS"


def _build_job_card(job, profile):
    requirements = getattr(job, "requirements", None)
    calibration = getattr(job, "calibration", None)
    match_result = analyze_job_match(profile, job, requirements)

    return {
        "job": job,
        "requirements": requirements,
        "match": match_result,
        "calibration": calibration,
        "calibration_alignment": _calibration_alignment(
            calibration,
            match_result,
        ),
    }


def _sort_job_cards(job_cards, selected_sort):
    if selected_sort == "coverage_desc":
        return sorted(
            job_cards,
            key=lambda card: (
                card["match"].evidence_coverage,
                card["match"].score,
                card["job"].created_at,
            ),
            reverse=True,
        )

    if selected_sort == "newest":
        return sorted(
            job_cards,
            key=lambda card: card["job"].created_at,
            reverse=True,
        )

    if selected_sort == "deadline":
        return sorted(
            job_cards,
            key=lambda card: (
                card["job"].application_deadline is None,
                card["job"].application_deadline or date.max,
            ),
        )

    return sorted(
        job_cards,
        key=lambda card: (
            1
            if card["match"].has_requirements
            and not card["match"].is_disqualified
            else 0,
            card["match"].score,
            card["match"].evidence_coverage,
            card["job"].created_at,
        ),
        reverse=True,
    )


def job_list(request):
    all_jobs = JobPosting.objects.select_related(
        "requirements",
        "calibration",
    ).all()
    jobs = all_jobs

    query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_fit = request.GET.get("fit", "").strip()
    selected_track = request.GET.get("track", "").strip()
    selected_review = request.GET.get("review", "").strip()
    selected_sort = request.GET.get("sort", "score_desc").strip()

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
        )

    if selected_status in JobPosting.Status.values:
        jobs = jobs.filter(status=selected_status)

    profile = CareerProfile.get_solo()
    all_cards = [_build_job_card(job, profile) for job in all_jobs]
    job_cards = [_build_job_card(job, profile) for job in jobs]

    fit_classification = FIT_FILTER_MAP.get(selected_fit)
    if fit_classification:
        job_cards = [
            card
            for card in job_cards
            if card["match"].classification == fit_classification
        ]

    track_label = TRACK_FILTER_MAP.get(selected_track)
    if track_label:
        job_cards = [
            card for card in job_cards if card["match"].track == track_label
        ]

    if selected_review == "reviewed":
        job_cards = [card for card in job_cards if card["calibration"]]
    elif selected_review == "unreviewed":
        job_cards = [card for card in job_cards if not card["calibration"]]
    elif selected_review in {"agrees", "differs"}:
        expected = selected_review.upper()
        job_cards = [
            card
            for card in job_cards
            if card["calibration"]
            and card["calibration_alignment"] == expected
        ]

    if selected_sort not in dict(SORT_CHOICES):
        selected_sort = "score_desc"
    job_cards = _sort_job_cards(job_cards, selected_sort)

    context = {
        "job_cards": job_cards,
        "query": query,
        "selected_status": selected_status,
        "selected_fit": selected_fit,
        "selected_track": selected_track,
        "selected_review": selected_review,
        "selected_sort": selected_sort,
        "status_choices": JobPosting.Status.choices,
        "fit_choices": FIT_FILTER_CHOICES,
        "track_choices": TRACK_FILTER_CHOICES,
        "review_choices": REVIEW_FILTER_CHOICES,
        "sort_choices": SORT_CHOICES,
        "total_jobs": len(all_cards),
        "saved_jobs": sum(
            card["job"].status == JobPosting.Status.SAVED for card in all_cards
        ),
        "applied_jobs": sum(
            card["job"].status == JobPosting.Status.APPLIED for card in all_cards
        ),
        "interview_jobs": sum(
            card["job"].status == JobPosting.Status.INTERVIEW
            for card in all_cards
        ),
        "strong_good_jobs": sum(
            card["match"].classification in {"STRONG MATCH", "GOOD MATCH"}
            for card in all_cards
        ),
        "priority_jobs": sum(
            card["match"].track == "PRIORITY ROLE" for card in all_cards
        ),
        "adjacent_jobs": sum(
            card["match"].track == "ADJACENT OPPORTUNITY"
            for card in all_cards
        ),
        "calibrated_jobs": sum(
            bool(card["calibration"]) for card in all_cards
        ),
        "filters_active": any(
            (
                query,
                selected_status,
                selected_fit,
                selected_track,
                selected_review,
                selected_sort != "score_desc",
            )
        ),
    }
    return render(request, "tracker/job_list.html", context)


def career_profile(request):
    profile = CareerProfile.get_solo()

    if request.method == "POST":
        form = CareerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Career profile saved. Job-match analysis will use this information.",
            )
            return redirect("career_profile")
    else:
        form = CareerProfileForm(instance=profile)

    return render(
        request,
        "tracker/career_profile.html",
        {
            "form": form,
            "profile": profile,
        },
    )


def job_detail(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    requirements = JobRequirement.objects.filter(job=job).first()
    profile = CareerProfile.get_solo()
    match_result = analyze_job_match(profile, job, requirements)

    return render(
        request,
        "tracker/job_detail.html",
        {
            "job": job,
            "requirements": requirements,
            "match_result": match_result,
        },
    )


def job_match(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    requirements = JobRequirement.objects.filter(job=job).first()
    profile = CareerProfile.get_solo()
    match_result = analyze_job_match(profile, job, requirements)
    calibration = MatchCalibration.objects.filter(job=job).first()

    if request.method == "POST":
        calibration_form = MatchCalibrationForm(
            request.POST,
            instance=calibration or MatchCalibration(job=job),
        )
        if calibration_form.is_valid():
            calibration = calibration_form.save()
            messages.success(
                request,
                "Your match judgment was saved for Stage 2 calibration.",
            )
            return redirect("job_match", job_id=job.id)
    else:
        calibration_form = MatchCalibrationForm(instance=calibration)

    return render(
        request,
        "tracker/job_match.html",
        {
            "job": job,
            "requirements": requirements,
            "profile": profile,
            "match_result": match_result,
            "calibration": calibration,
            "calibration_form": calibration_form,
            "calibration_alignment": _calibration_alignment(
                calibration,
                match_result,
            ),
        },
    )


def job_requirements(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    requirements, _ = JobRequirement.objects.get_or_create(job=job)

    if request.method == "POST":
        form = JobRequirementForm(request.POST, instance=requirements)
        if form.is_valid():
            form.save()
            messages.success(request, "Structured job requirements saved.")
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobRequirementForm(instance=requirements)

    return render(
        request,
        "tracker/job_requirements.html",
        {
            "job": job,
            "requirements": requirements,
            "form": form,
        },
    )


def job_create(request):
    if request.method == "POST":
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save()
            JobRequirement.objects.get_or_create(job=job)
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobPostingForm()

    return render(
        request,
        "tracker/job_form.html",
        {
            "form": form,
            "page_title": "Add a Job",
            "submit_label": "Save Job",
        },
    )


def job_edit(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    if request.method == "POST":
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobPostingForm(instance=job)

    return render(
        request,
        "tracker/job_form.html",
        {
            "form": form,
            "job": job,
            "page_title": "Edit Job",
            "submit_label": "Save Changes",
        },
    )


def job_delete(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    if request.method == "POST":
        job.delete()
        return redirect("job_list")

    return render(request, "tracker/job_confirm_delete.html", {"job": job})
