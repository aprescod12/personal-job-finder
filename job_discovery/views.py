from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tracker.intake_views import INTAKE_SESSION_KEY

from .forms import DiscoveryDecisionForm, DiscoveryRunForm
from .models import DiscoveryRun, RawJobOpportunity
from .services import (
    DiscoveryError,
    DiscoveryHandoffError,
    keep_duplicate_for_processing,
    prepare_opportunity_for_processing,
    run_discovery,
)


STATUS_FILTERS = (
    ("", "All inbox states"),
    *RawJobOpportunity.Status.choices,
)


def discovery_inbox(request):
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _ in STATUS_FILTERS}
    if selected_status not in valid_statuses:
        selected_status = ""

    opportunities = RawJobOpportunity.objects.select_related(
        "run",
        "duplicate_of_opportunity",
        "duplicate_of_job",
        "processed_job",
    )
    if selected_status:
        opportunities = opportunities.filter(status=selected_status)

    counts = {
        item["status"]: item["total"]
        for item in RawJobOpportunity.objects.values("status").annotate(total=Count("id"))
    }
    needs_action = RawJobOpportunity.objects.filter(
        Q(status=RawJobOpportunity.Status.NEW)
        | Q(status=RawJobOpportunity.Status.READY)
        | Q(status=RawJobOpportunity.Status.PROCESSING_FAILED)
    ).count()

    return render(
        request,
        "job_discovery/inbox.html",
        {
            "run_form": DiscoveryRunForm(),
            "opportunities": opportunities[:100],
            "recent_runs": DiscoveryRun.objects.all()[:8],
            "status_filters": STATUS_FILTERS,
            "selected_status": selected_status,
            "counts": counts,
            "total_opportunities": RawJobOpportunity.objects.count(),
            "needs_action": needs_action,
            "duplicate_count": counts.get(RawJobOpportunity.Status.DUPLICATE, 0),
            "processed_count": counts.get(RawJobOpportunity.Status.PROCESSED, 0),
        },
    )


@require_POST
def run_discovery_view(request):
    form = DiscoveryRunForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose an approved discovery provider.")
        return redirect("job_discovery:inbox")

    try:
        run = run_discovery(form.cleaned_data["provider_key"])
    except DiscoveryError as exc:
        messages.error(request, f"Discovery run failed safely: {exc}")
    else:
        messages.success(
            request,
            (
                f"Discovery completed: {run.result_count} result"
                f"{'s' if run.result_count != 1 else ''}, "
                f"{run.new_count} new and {run.duplicate_count} duplicate."
            ),
        )
    return redirect("job_discovery:inbox")


def opportunity_detail(request, opportunity_id):
    opportunity = get_object_or_404(
        RawJobOpportunity.objects.select_related(
            "run",
            "duplicate_of_opportunity",
            "duplicate_of_job",
            "processed_job",
        ),
        pk=opportunity_id,
    )
    active_draft = request.session.get(INTAKE_SESSION_KEY, {})
    return render(
        request,
        "job_discovery/opportunity_detail.html",
        {
            "opportunity": opportunity,
            "decision_form": DiscoveryDecisionForm(
                initial={"notes": opportunity.decision_notes}
            ),
            "processing_draft_active": (
                active_draft.get("discovery_opportunity_id") == opportunity.id
            ),
        },
    )


@require_POST
def ignore_opportunity(request, opportunity_id):
    opportunity = get_object_or_404(RawJobOpportunity, pk=opportunity_id)
    if opportunity.status in {
        RawJobOpportunity.Status.PROCESSED,
        RawJobOpportunity.Status.SENT_TO_PROCESSING,
    }:
        messages.error(request, "A processed or active handoff cannot be ignored.")
        return redirect("job_discovery:opportunity_detail", opportunity_id=opportunity.id)

    form = DiscoveryDecisionForm(request.POST)
    if form.is_valid():
        opportunity.status = RawJobOpportunity.Status.IGNORED
        opportunity.decision_notes = form.cleaned_data["notes"]
        opportunity.save(update_fields=["status", "decision_notes", "updated_at"])
        messages.info(request, "Opportunity moved out of the active discovery inbox.")
    return redirect("job_discovery:opportunity_detail", opportunity_id=opportunity.id)


@require_POST
def restore_opportunity(request, opportunity_id):
    opportunity = get_object_or_404(RawJobOpportunity, pk=opportunity_id)
    if opportunity.status != RawJobOpportunity.Status.IGNORED:
        messages.error(request, "Only ignored opportunities can be restored.")
    else:
        opportunity.status = (
            RawJobOpportunity.Status.DUPLICATE
            if opportunity.has_blocking_duplicate and not opportunity.duplicate_override
            else RawJobOpportunity.Status.READY
        )
        opportunity.save(update_fields=["status", "updated_at"])
        messages.success(request, "Opportunity restored for review.")
    return redirect("job_discovery:opportunity_detail", opportunity_id=opportunity.id)


@require_POST
def retain_duplicate(request, opportunity_id):
    opportunity = get_object_or_404(RawJobOpportunity, pk=opportunity_id)
    try:
        keep_duplicate_for_processing(opportunity)
    except DiscoveryHandoffError as exc:
        messages.error(request, str(exc))
    else:
        messages.warning(
            request,
            "Duplicate warning overridden. The listing still requires normal Job Processing review.",
        )
    return redirect("job_discovery:opportunity_detail", opportunity_id=opportunity.id)


@require_POST
def send_to_processing(request, opportunity_id):
    opportunity = get_object_or_404(RawJobOpportunity, pk=opportunity_id)
    try:
        draft = prepare_opportunity_for_processing(opportunity)
    except DiscoveryHandoffError as exc:
        messages.error(request, f"The processing draft could not be prepared: {exc}")
        return redirect("job_discovery:opportunity_detail", opportunity_id=opportunity.id)

    request.session[INTAKE_SESSION_KEY] = draft
    request.session.modified = True
    messages.info(
        request,
        (
            "Discovery listing sent to Job Processing. Review every extracted field; "
            "no tracked job exists yet."
        ),
    )
    return redirect("job_intake_review")
