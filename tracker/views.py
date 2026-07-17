from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CareerProfileForm, JobPostingForm, JobRequirementForm
from .models import CareerProfile, JobPosting, JobRequirement
from .services.matching import analyze_job_match


def job_list(request):
    all_jobs = JobPosting.objects.all()
    jobs = all_jobs

    query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
        )

    if selected_status in JobPosting.Status.values:
        jobs = jobs.filter(status=selected_status)

    context = {
        "jobs": jobs,
        "query": query,
        "selected_status": selected_status,
        "status_choices": JobPosting.Status.choices,
        "total_jobs": all_jobs.count(),
        "saved_jobs": all_jobs.filter(status=JobPosting.Status.SAVED).count(),
        "applied_jobs": all_jobs.filter(status=JobPosting.Status.APPLIED).count(),
        "interview_jobs": all_jobs.filter(
            status=JobPosting.Status.INTERVIEW
        ).count(),
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

    return render(
        request,
        "tracker/job_match.html",
        {
            "job": job,
            "requirements": requirements,
            "profile": profile,
            "match_result": match_result,
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
