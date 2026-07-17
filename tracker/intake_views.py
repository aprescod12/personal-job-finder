from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .intake_forms import JobIntakePasteForm, JobIntakeReviewForm
from .services.job_intake import extract_job_intake


INTAKE_SESSION_KEY = "stage4_job_intake_draft"


def job_intake_start(request):
    if request.method == "POST":
        form = JobIntakePasteForm(request.POST)
        if form.is_valid():
            raw_text = form.cleaned_data["raw_text"]
            source_url = form.cleaned_data.get("source_url", "")
            source_label = form.cleaned_data.get("source_label", "")
            extraction = extract_job_intake(
                raw_text,
                source_url=source_url,
                source_label=source_label,
            )
            request.session[INTAKE_SESSION_KEY] = {
                "raw_text": raw_text,
                "source_url": source_url,
                "source_label": source_label,
                "extraction": extraction,
            }
            request.session.modified = True
            messages.info(
                request,
                "Draft extracted. Review every field before creating the tracked job.",
            )
            return redirect("job_intake_review")
    else:
        form = JobIntakePasteForm()

    return render(
        request,
        "tracker/job_intake_start.html",
        {"form": form},
    )


def job_intake_review(request):
    draft = request.session.get(INTAKE_SESSION_KEY)
    if not draft:
        messages.warning(request, "Start by pasting a job listing.")
        return redirect("job_intake_start")

    extraction = draft["extraction"]
    initial = {}
    initial.update(extraction.get("job", {}))
    initial.update(extraction.get("requirements", {}))

    if request.method == "POST":
        form = JobIntakeReviewForm(request.POST)
        if form.is_valid():
            job = form.save()
            request.session.pop(INTAKE_SESSION_KEY, None)
            request.session.modified = True
            messages.success(
                request,
                "Reviewed intake saved. Verify the listing before treating it as an active application target.",
            )
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobIntakeReviewForm(initial=initial)

    return render(
        request,
        "tracker/job_intake_review.html",
        {
            "form": form,
            "draft": draft,
            "extraction": extraction,
        },
    )


@require_POST
def job_intake_clear(request):
    request.session.pop(INTAKE_SESSION_KEY, None)
    request.session.modified = True
    messages.info(request, "Intake draft discarded. No job was created.")
    return redirect("job_intake_start")
