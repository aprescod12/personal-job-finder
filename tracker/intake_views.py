from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from intake_history.services import analyze_job_duplicates

from .intake_forms import JobIntakePasteForm, JobIntakeReviewForm
from .services.job_extraction import JobExtractionError
from .services.job_extraction_coordinator import extract_job_with_fallback


INTAKE_SESSION_KEY = "stage4_job_intake_draft"


def _release_discovery_draft(draft):
    opportunity_id = (draft or {}).get("discovery_opportunity_id")
    if not opportunity_id:
        return None

    from job_discovery.services import release_opportunity_handoff

    return release_opportunity_handoff(opportunity_id)


def job_intake_start(request):
    duplicate_analysis = None

    if request.method == "POST":
        form = JobIntakePasteForm(request.POST)
        if form.is_valid():
            raw_text = form.cleaned_data["raw_text"]
            source_url = form.cleaned_data.get("source_url", "")
            source_label = form.cleaned_data.get("source_label", "")

            duplicate_analysis = analyze_job_duplicates(
                source_url=source_url,
                raw_text=raw_text,
            )
            if (
                duplicate_analysis.get("blocking")
                and not form.cleaned_data.get("continue_duplicate")
            ):
                form.add_error(
                    "continue_duplicate",
                    (
                        "Review the exact match below before spending an extraction "
                        "request or creating another draft."
                    ),
                )
                messages.warning(
                    request,
                    (
                        "A tracked job already matches this URL or pasted listing. "
                        "Extraction was not run."
                    ),
                )
            else:
                try:
                    extraction = extract_job_with_fallback(
                        raw_text,
                        source_url=source_url,
                        source_label=source_label,
                    )
                except JobExtractionError as exc:
                    form.add_error(
                        None,
                        (
                            "The job draft could not be prepared safely. "
                            f"Review the listing and try again. {exc}"
                        ),
                    )
                else:
                    duplicate_analysis = analyze_job_duplicates(
                        source_url=source_url,
                        raw_text=raw_text,
                        extracted_job=extraction.get("job", {}),
                    )
                    _release_discovery_draft(request.session.get(INTAKE_SESSION_KEY))
                    request.session[INTAKE_SESSION_KEY] = {
                        "raw_text": raw_text,
                        "source_url": source_url,
                        "source_label": source_label,
                        "extraction": extraction,
                        "duplicate_analysis": duplicate_analysis,
                    }
                    request.session.modified = True

                    orchestration = extraction.get("orchestration", {})
                    if orchestration.get("manual_review_required"):
                        messages.warning(
                            request,
                            (
                                "No extractor produced a structured draft. The original "
                                "listing was preserved for manual review; nothing was saved."
                            ),
                        )
                    elif orchestration.get("fallback_used"):
                        messages.warning(
                            request,
                            (
                                "The primary extractor was unavailable. A clearly labeled "
                                "deterministic fallback draft is ready for careful review."
                            ),
                        )
                    else:
                        messages.info(
                            request,
                            (
                                "Draft extracted. Review every field before creating "
                                "the tracked job."
                            ),
                        )
                    return redirect("job_intake_review")
    else:
        form = JobIntakePasteForm()

    return render(
        request,
        "tracker/job_intake_start.html",
        {
            "form": form,
            "duplicate_analysis": duplicate_analysis,
        },
    )


def job_intake_review(request):
    draft = request.session.get(INTAKE_SESSION_KEY)
    if not draft:
        messages.warning(request, "Start by pasting a job listing.")
        return redirect("job_intake_start")

    extraction = draft["extraction"]
    duplicate_analysis = draft.get("duplicate_analysis") or analyze_job_duplicates(
        source_url=draft.get("source_url", ""),
        raw_text=draft.get("raw_text", ""),
        extracted_job=extraction.get("job", {}),
    )
    initial = {}
    initial.update(extraction.get("job", {}))
    initial.update(extraction.get("requirements", {}))

    if request.method == "POST":
        form = JobIntakeReviewForm(
            request.POST,
            duplicate_analysis=duplicate_analysis,
        )
        if form.is_valid():
            job = form.save(intake_draft=draft)
            request.session.pop(INTAKE_SESSION_KEY, None)
            request.session.modified = True
            messages.success(
                request,
                (
                    "Reviewed intake saved with source and extraction history. "
                    "Verify the listing before treating it as an active application target."
                ),
            )
            return redirect("job_detail", job_id=job.id)
    else:
        form = JobIntakeReviewForm(
            initial=initial,
            duplicate_analysis=duplicate_analysis,
        )

    return render(
        request,
        "tracker/job_intake_review.html",
        {
            "form": form,
            "draft": draft,
            "extraction": extraction,
            "duplicate_analysis": duplicate_analysis,
        },
    )


@require_POST
def job_intake_clear(request):
    draft = request.session.get(INTAKE_SESSION_KEY)
    released = _release_discovery_draft(draft)
    request.session.pop(INTAKE_SESSION_KEY, None)
    request.session.modified = True
    if released:
        messages.info(
            request,
            "Processing draft discarded. The discovery opportunity returned to the inbox.",
        )
        return redirect("job_discovery:opportunity_detail", opportunity_id=released.id)

    messages.info(request, "Intake draft discarded. No job or history record was created.")
    return redirect("job_intake_start")
