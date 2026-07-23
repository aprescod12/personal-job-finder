from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .evaluation_models import JobEvaluationRun
from .models import JobCalibration, JobPosting
from .services.job_evaluations import evaluate_all_jobs, evaluate_job
from .validation_batch import is_blind_validation


@require_POST
def reevaluate_job(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id)
    run = evaluate_job(job, trigger=JobEvaluationRun.Trigger.MANUAL)
    delta = run.score_delta
    if delta is None:
        change = "The first persisted evaluation was created."
    elif delta > 0:
        change = f"The score increased by {delta} point{'s' if delta != 1 else ''}."
    elif delta < 0:
        change = f"The score decreased by {abs(delta)} point{'s' if delta != -1 else ''}."
    else:
        change = "The score did not change."

    messages.success(
        request,
        f"{job.title} was reevaluated with {run.matcher_version}. {change}",
    )
    return redirect("job_match", job_id=job.id)


@require_POST
def reevaluate_all_jobs(request):
    runs = evaluate_all_jobs()
    messages.success(
        request,
        f"Reevaluated {len(runs)} tracked job{'s' if len(runs) != 1 else ''} against the current candidate profile.",
    )
    return redirect("job_list")


def evaluation_history(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id)
    calibration = JobCalibration.objects.filter(job=job).first()
    if is_blind_validation(job, calibration):
        messages.info(
            request,
            "Evaluation history remains hidden until you record the blind holdout judgment.",
        )
        return redirect("job_match", job_id=job.id)

    runs = list(
        JobEvaluationRun.objects.filter(job=job)
        .select_related("candidate_snapshot", "previous_run")
        .order_by("-evaluated_at", "-id")
    )
    return render(
        request,
        "tracker/evaluation_history.html",
        {
            "job": job,
            "runs": runs,
            "current_run": next((run for run in runs if run.is_current), None),
        },
    )
