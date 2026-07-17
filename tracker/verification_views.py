from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import JobPosting, ListingVerificationRun
from .services.listing_verification_runner import (
    VerificationAlreadyRunning,
    run_listing_verification,
)
from .verification_forms import VerificationReviewForm


@require_POST
def run_job_verification(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    try:
        run = run_listing_verification(job)
    except VerificationAlreadyRunning as exc:
        messages.warning(
            request,
            "A verification run is already active for this job.",
        )
        return redirect(
            "verification_run_detail",
            job_id=job.id,
            run_id=exc.run.id,
        )

    if run.status == ListingVerificationRun.RunStatus.FAILED:
        messages.error(
            request,
            "The experimental auto-check failed. You can still review this job manually.",
        )
    elif run.status == ListingVerificationRun.RunStatus.NEEDS_REVIEW:
        messages.warning(
            request,
            (
                "Employer page analyzed. Review the suggested listing status, "
                "deadline, and evidence before changing the job record."
            ),
        )
    else:
        messages.success(request, "Verification completed and the result was saved.")

    return redirect(
        "verification_run_detail",
        job_id=job.id,
        run_id=run.id,
    )


def verification_run_detail(request, job_id, run_id):
    job = get_object_or_404(JobPosting, id=job_id)
    run = get_object_or_404(
        ListingVerificationRun,
        id=run_id,
        job=job,
    )

    return render(
        request,
        "tracker/verification_run_detail.html",
        {
            "job": job,
            "run": run,
        },
    )


def review_verification_run(request, job_id, run_id):
    job = get_object_or_404(JobPosting, id=job_id)
    run = get_object_or_404(
        ListingVerificationRun,
        id=run_id,
        job=job,
    )

    if request.method == "POST" and request.POST.get("decision") == "reject":
        evidence = dict(run.structured_evidence or {})
        evidence["review_decision"] = {
            "decision": "rejected",
            "reviewed_at": timezone.now().isoformat(),
            "job_record_changed": False,
        }
        run.review_status = ListingVerificationRun.ReviewStatus.REJECTED
        run.structured_evidence = evidence
        run.save(update_fields=["review_status", "structured_evidence"])
        messages.info(
            request,
            "The suggested result was rejected. The job record was not changed.",
        )
        return redirect(
            "verification_run_detail",
            job_id=job.id,
            run_id=run.id,
        )

    form = VerificationReviewForm(
        request.POST or None,
        job=job,
        run=run,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.apply_to_job()
            evidence = dict(run.structured_evidence or {})
            evidence["review_decision"] = {
                "decision": "accepted_or_corrected",
                "reviewed_at": timezone.now().isoformat(),
                "job_record_changed": True,
                "applied_listing_status": form.cleaned_data["listing_status"],
                "applied_deadline_status": form.cleaned_data["deadline_status"],
                "applied_deadline": (
                    form.cleaned_data["application_deadline"].isoformat()
                    if form.cleaned_data["application_deadline"]
                    else None
                ),
                "applied_url": form.cleaned_data["job_url"],
            }
            run.review_status = ListingVerificationRun.ReviewStatus.ACCEPTED
            run.structured_evidence = evidence
            run.save(update_fields=["review_status", "structured_evidence"])

        messages.success(
            request,
            "The reviewed listing status and deadline were applied to the job.",
        )
        return redirect("job_detail", job_id=job.id)

    return render(
        request,
        "tracker/verification_run_review.html",
        {
            "job": job,
            "run": run,
            "form": form,
        },
    )
