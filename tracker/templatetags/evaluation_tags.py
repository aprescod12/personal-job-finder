from django import template

from tracker.evaluation_models import JobEvaluationRun
from tracker.models import JobPosting
from tracker.services.job_evaluations import latest_evaluation


register = template.Library()


@register.simple_tag
def latest_job_evaluation(job):
    return latest_evaluation(job, refresh=True)


@register.simple_tag
def evaluation_dashboard_summary():
    current = 0
    stale = 0
    missing = 0

    for job in JobPosting.objects.order_by("id"):
        run = latest_evaluation(job, refresh=True)
        if run is None:
            missing += 1
        elif run.is_current:
            current += 1
        else:
            stale += 1

    return {
        "current": current,
        "stale": stale,
        "missing": missing,
        "needs_reevaluation": stale + missing,
        "total_runs": JobEvaluationRun.objects.count(),
    }
