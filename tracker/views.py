from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    CareerProfileForm,
    JobCalibrationForm,
    JobListingVerificationForm,
    JobPostingForm,
    JobRequirementForm,
)
from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement
from .services.strategy_matching import analyze_job_match
from .validation_batch import (
    CALIBRATION_SOURCE,
    VALIDATION_SOURCE,
    is_blind_validation,
)


FIT_FILTER_CHOICES = (
    ("", "All fit levels"),
    ("strong", "Strong / good matches"),
    ("possible", "Possible matches"),
    ("weak", "Weak matches"),
    ("disqualified", "Disqualified"),
    ("needs_review", "Needs more evidence"),
)

TRACK_FILTER_CHOICES = (
    ("", "All opportunity lanes"),
    ("priority", "Priority roles"),
    ("adjacent", "Adjacent opportunities"),
    ("outside", "Outside current priority"),
)

REVIEW_FILTER_CHOICES = (
    ("", "All review states"),
    ("reviewed", "Human-reviewed"),
    ("unreviewed", "Not yet reviewed"),
    ("aligned", "Matcher aligned"),
    ("disagree", "Matcher differs"),
)

SOURCE_FILTER_CHOICES = (
    ("", "All job sources"),
    ("validation", "Validation holdout"),
    ("calibration", "Original calibration batch"),
    ("other", "Manual and other jobs"),
)

LISTING_FILTER_CHOICES = (
    ("", "All listing states"),
    ("open", "Verified open"),
    ("needs_verification", "Needs verification"),
    ("deadline_soon", "Deadline within 7 days"),
    ("unavailable", "Closed or expired"),
    ("link_problem", "Broken link or wrong page"),
)

SORT_CHOICES = (
    ("newest", "Newest added"),
    ("match_high", "Highest match score"),
    ("match_low", "Lowest match score"),
    ("deadline", "Nearest deadline"),
    ("company", "Company A–Z"),
)

FIT_CLASSIFICATIONS = {
    "strong": {"STRONG MATCH", "GOOD MATCH"},
    "possible": {"POSSIBLE MATCH"},
    "weak": {"WEAK MATCH"},
    "disqualified": {"DISQUALIFIED"},
    "needs_review": {"LOW CONFIDENCE", "NEEDS REQUIREMENTS"},
}

TRACK_VALUES = {
    "priority": "PRIORITY ROLE",
    "adjacent": "ADJACENT OPPORTUNITY",
    "outside": "OUTSIDE PRIORITY",
}


def _attach_match_data(jobs, profile):
    job_ids = [job.id for job in jobs]
    requirements = {
        item.job_id: item
        for item in JobRequirement.objects.filter(job_id__in=job_ids)
    }
    calibrations = {
        item.job_id: item
        for item in JobCalibration.objects.filter(job_id__in=job_ids)
    }

    for job in jobs:
        requirement = requirements.get(job.id)
        job.match_result = analyze_job_match(profile, job, requirement)
        job.calibration_record = calibrations.get(job.id)
        job.blind_validation = is_blind_validation(
            job,
            job.calibration_record,
        )

    return jobs


def _filter_by_fit(jobs, selected_fit):
    classifications = FIT_CLASSIFICATIONS.get(selected_fit)
    if not classifications:
        return jobs
    return [
        job
        for job in jobs
        if job.blind_validation
        or job.match_result.classification in classifications
    ]


def _filter_by_track(jobs, selected_track):
    track = TRACK_VALUES.get(selected_track)
    if not track:
        return jobs
    return [
        job
        for job in jobs
        if job.blind_validation or job.match_result.track == track
    ]


def _filter_by_review(jobs, selected_review):
    if selected_review == "reviewed":
        return [job for job in jobs if job.calibration_record]
    if selected_review == "unreviewed":
        return [job for job in jobs if not job.calibration_record]
    if selected_review == "aligned":
        return [
            job
            for job in jobs
            if job.calibration_record
            and job.calibration_record.agreement_status == "ALIGNED"
        ]
    if selected_review == "disagree":
        return [
            job
            for job in jobs
            if job.calibration_record
            and job.calibration_record.agreement_status == "REVIEW"
        ]
    return jobs


def _filter_by_listing(jobs, selected_listing):
    if selected_listing == "open":
        return [
            job
            for job in jobs
            if job.listing_is_available and not job.listing_needs_verification
        ]
    if selected_listing == "needs_verification":
        return [job for job in jobs if job.listing_needs_verification]
    if selected_listing == "deadline_soon":
        return [job for job in jobs if job.deadline_is_due_soon]
    if selected_listing == "unavailable":
        return [
            job
            for job in jobs
            if job.listing_is_unavailable and not job.listing_has_link_problem
        ]
    if selected_listing == "link_problem":
        return [job for job in jobs if job.listing_has_link_problem]
    return jobs


def _sort_jobs(jobs, selected_sort):
    if selected_sort == "match_high":
        return sorted(
            jobs,
            key=lambda job: (
                not job.blind_validation,
                not job.match_result.is_disqualified,
                job.match_result.has_requirements,
                job.match_result.score,
                job.match_result.evidence_coverage,
                job.created_at,
            ),
            reverse=True,
        )
    if selected_sort == "match_low":
        return sorted(
            jobs,
            key=lambda job: (
                job.blind_validation,
                not job.match_result.has_requirements,
                job.match_result.score,
                job.company.casefold(),
            ),
        )
    if selected_sort == "deadline":
        return sorted(
            jobs,
            key=lambda job: (
                job.application_deadline is None,
                job.application_deadline or date.max,
                job.company.casefold(),
            ),
        )
    if selected_sort == "company":
        return sorted(
            jobs,
            key=lambda job: (job.company.casefold(), job.title.casefold()),
        )
    return jobs


def _filter_source(queryset, selected_source):
    if selected_source == "validation":
        return queryset.filter(source=VALIDATION_SOURCE)
    if selected_source == "calibration":
        return queryset.filter(source=CALIBRATION_SOURCE)
    if selected_source == "other":
        return queryset.exclude(
            source__in=(CALIBRATION_SOURCE, VALIDATION_SOURCE)
        )
    return queryset


def job_list(request):
    all_jobs = JobPosting.objects.all()
    all_jobs_list = list(all_jobs)
    filtered_jobs = all_jobs

    query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_fit = request.GET.get("fit", "").strip()
    selected_track = request.GET.get("track", "").strip()
    selected_review = request.GET.get("review", "").strip()
    selected_source = request.GET.get("source", "").strip()
    selected_listing = request.GET.get("listing", "").strip()
    selected_sort = request.GET.get("sort", "newest").strip()

    if query:
        filtered_jobs = filtered_jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
            | Q(source__icontains=query)
            | Q(listing_verification_notes__icontains=query)
            | Q(requirements__role_family__icontains=query)
            | Q(requirements__industry__icontains=query)
            | Q(requirements__required_skills__icontains=query)
            | Q(requirements__preferred_skills__icontains=query)
        ).distinct()

    if selected_status in JobPosting.Status.values:
        filtered_jobs = filtered_jobs.filter(status=selected_status)
    else:
        selected_status = ""

    valid_fit_values = {value for value, _ in FIT_FILTER_CHOICES}
    valid_track_values = {value for value, _ in TRACK_FILTER_CHOICES}
    valid_review_values = {value for value, _ in REVIEW_FILTER_CHOICES}
    valid_source_values = {value for value, _ in SOURCE_FILTER_CHOICES}
    valid_listing_values = {value for value, _ in LISTING_FILTER_CHOICES}
    valid_sort_values = {value for value, _ in SORT_CHOICES}

    if selected_fit not in valid_fit_values:
        selected_fit = ""
    if selected_track not in valid_track_values:
        selected_track = ""
    if selected_review not in valid_review_values:
        selected_review = ""
    if selected_source not in valid_source_values:
        selected_source = ""
    if selected_listing not in valid_listing_values:
        selected_listing = ""
    if selected_sort not in valid_sort_values:
        selected_sort = "newest"

    filtered_jobs = _filter_source(filtered_jobs, selected_source)

    profile = CareerProfile.get_solo()
    jobs = _attach_match_data(list(filtered_jobs), profile)
    jobs = _filter_by_listing(jobs, selected_listing)
    jobs = _filter_by_fit(jobs, selected_fit)
    jobs = _filter_by_track(jobs, selected_track)
    jobs = _filter_by_review(jobs, selected_review)

    blind_sort_reset = False
    if any(job.blind_validation for job in jobs) and selected_sort in {
        "match_high",
        "match_low",
    }:
        selected_sort = "company"
        blind_sort_reset = True

    jobs = _sort_jobs(jobs, selected_sort)

    visible_jobs = [job for job in jobs if not job.blind_validation]
    analyzed_count = sum(
        job.match_result.has_requirements for job in visible_jobs
    )
    strong_count = sum(
        job.match_result.classification == "STRONG MATCH"
        for job in visible_jobs
    )
    good_count = sum(
        job.match_result.classification == "GOOD MATCH"
        for job in visible_jobs
    )
    reviewed_count = sum(bool(job.calibration_record) for job in jobs)
    blind_count = sum(job.blind_validation for job in jobs)

    context = {
        "jobs": jobs,
        "query": query,
        "selected_status": selected_status,
        "selected_fit": selected_fit,
        "selected_track": selected_track,
        "selected_review": selected_review,
        "selected_source": selected_source,
        "selected_listing": selected_listing,
        "selected_sort": selected_sort,
        "status_choices": JobPosting.Status.choices,
        "fit_filter_choices": FIT_FILTER_CHOICES,
        "track_filter_choices": TRACK_FILTER_CHOICES,
        "review_filter_choices": REVIEW_FILTER_CHOICES,
        "source_filter_choices": SOURCE_FILTER_CHOICES,
        "listing_filter_choices": LISTING_FILTER_CHOICES,
        "sort_choices": SORT_CHOICES,
        "total_jobs": len(all_jobs_list),
        "analyzed_jobs": analyzed_count,
        "strong_jobs": strong_count,
        "good_jobs": good_count,
        "reviewed_jobs": reviewed_count,
        "blind_jobs": blind_count,
        "verified_open_jobs": sum(
            job.listing_is_available and not job.listing_needs_verification
            for job in all_jobs_list
        ),
        "verification_needed_jobs": sum(
            job.listing_needs_verification for job in all_jobs_list
        ),
        "deadline_soon_jobs": sum(
            job.deadline_is_due_soon for job in all_jobs_list
        ),
        "blind_sort_reset": blind_sort_reset,
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
    calibration = JobCalibration.objects.filter(job=job).first()
    blind_validation = is_blind_validation(job, calibration)

    return render(
        request,
        "tracker/job_detail.html",
        {
            "job": job,
            "requirements": requirements,
            "match_result": match_result,
            "calibration": calibration,
            "blind_validation": blind_validation,
        },
    )


def job_listing_verify(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    if request.method == "POST":
        form = JobListingVerificationForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save()
            messages.success(
                request,
                (
                    f"Listing verification saved as {job.effective_listing_status_label}. "
                    f"Last checked {job.listing_last_verified:%b %d, %Y}."
                ),
            )
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobListingVerificationForm(instance=job)

    return render(
        request,
        "tracker/job_listing_verify.html",
        {
            "job": job,
            "form": form,
        },
    )


def job_match(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    requirements = JobRequirement.objects.filter(job=job).first()
    profile = CareerProfile.get_solo()
    match_result = analyze_job_match(profile, job, requirements)
    calibration = JobCalibration.objects.filter(job=job).first()
    blind_validation = is_blind_validation(job, calibration)

    if request.method == "POST":
        calibration_form = JobCalibrationForm(
            request.POST,
            instance=calibration,
        )
        if calibration_form.is_valid():
            calibration = calibration_form.save(commit=False)
            calibration.job = job
            calibration.predicted_score = (
                match_result.score if match_result.has_requirements else None
            )
            calibration.predicted_classification = match_result.classification
            calibration.predicted_track = match_result.track
            calibration.save()
            messages.success(
                request,
                (
                    "Blind validation judgment saved. The matcher result is now revealed."
                    if blind_validation
                    else "Your calibration judgment was saved with the current matcher result."
                ),
            )
            return redirect("job_match", job_id=job.id)
    else:
        calibration_form = JobCalibrationForm(instance=calibration)

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
            "blind_validation": blind_validation,
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
