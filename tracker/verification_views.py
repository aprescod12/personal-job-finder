from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import JobPosting, ListingVerificationRun
from .services.listing_verification_runner import (
    VerificationAlreadyRunning,
    run_listing_verification,
)


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
            "Verification could not start. Review the saved URL and run details.",
        )
    elif run.status == ListingVerificationRun.RunStatus.NEEDS_REVIEW:
        messages.warning(
            request,
            "Verification preflight completed. Employer-page inspection is still required.",
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
