from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from tracker.models import CareerProfile

from .forms import ResumeSourceUploadForm
from .models import ResumeSource
from .services.resume_documents import ResumeDocumentError, extract_resume_document_text
from .services.resume_extraction import (
    ResumeExtractionError,
    ResumeExtractionRequest,
    extract_resume,
)


RESUME_EXTRACTION_SESSION_KEY = "stage5_resume_extraction_draft"


def resume_source_list(request):
    profile = CareerProfile.get_solo()

    if request.method == "POST":
        form = ResumeSourceUploadForm(
            request.POST,
            request.FILES,
            profile=profile,
        )
        if form.is_valid():
            source = form.save()
            messages.success(
                request,
                (
                    f"Resume source stored: {source.display_label}. "
                    "The career profile was not changed and no extraction was run."
                ),
            )
            return redirect("candidate_profile:resume_source_list")
    else:
        form = ResumeSourceUploadForm(profile=profile)

    sources = profile.resume_sources.all()
    active_source = sources.filter(is_active=True).first()
    return render(
        request,
        "candidate_profile/resume_source_list.html",
        {
            "profile": profile,
            "form": form,
            "sources": sources,
            "active_source": active_source,
            "has_extraction_draft": RESUME_EXTRACTION_SESSION_KEY in request.session,
        },
    )


@require_POST
def activate_resume_source(request, source_id):
    profile = CareerProfile.get_solo()
    source = get_object_or_404(ResumeSource, id=source_id, profile=profile)

    with transaction.atomic():
        ResumeSource.objects.filter(profile=profile, is_active=True).exclude(
            id=source.id
        ).update(is_active=False)
        if not source.is_active:
            source.is_active = True
            source.save(update_fields=["is_active", "updated_at"])

    messages.success(
        request,
        (
            f"Active resume source changed to {source.display_label}. "
            "This still does not update the structured career profile."
        ),
    )
    return redirect("candidate_profile:resume_source_list")


@require_http_methods(["GET", "POST"])
def delete_resume_source(request, source_id):
    profile = CareerProfile.get_solo()
    source = get_object_or_404(ResumeSource, id=source_id, profile=profile)

    if request.method == "GET":
        return render(
            request,
            "candidate_profile/resume_source_confirm_delete.html",
            {
                "profile": profile,
                "source": source,
            },
        )

    display_label = source.display_label
    was_active = source.is_active
    storage = source.document.storage
    stored_name = source.document.name

    draft = request.session.get(RESUME_EXTRACTION_SESSION_KEY, {})
    if draft.get("source", {}).get("id") == source.id:
        request.session.pop(RESUME_EXTRACTION_SESSION_KEY, None)

    with transaction.atomic():
        source.delete()
        if stored_name:
            transaction.on_commit(lambda: storage.delete(stored_name))

    if was_active:
        message = (
            f"Resume source removed: {display_label}. No resume is active now; "
            "choose another stored version explicitly before future extraction."
        )
    else:
        message = f"Resume source removed: {display_label}."

    messages.success(request, message)
    return redirect("candidate_profile:resume_source_list")


@require_POST
def run_resume_extraction(request, source_id):
    profile = CareerProfile.get_solo()
    source = get_object_or_404(ResumeSource, id=source_id, profile=profile)

    try:
        document = extract_resume_document_text(source)
        extraction_request = ResumeExtractionRequest(
            document_text=document.text,
            source_id=source.id,
            source_sha256=source.sha256,
            source_filename=source.original_filename,
            source_label=source.display_label,
            document_parser_key=document.parser_key,
            document_parser_version=document.parser_version,
        )
        extraction = extract_resume(extraction_request)
    except (ResumeDocumentError, ResumeExtractionError) as exc:
        messages.error(request, f"Resume extraction could not start: {exc}")
        return redirect("candidate_profile:resume_source_list")

    request.session[RESUME_EXTRACTION_SESSION_KEY] = {
        "source": {
            "id": source.id,
            "label": source.display_label,
            "filename": source.original_filename,
            "sha256": source.sha256,
            "is_active": source.is_active,
        },
        "document": document.to_dict(),
        "extraction": extraction,
        "created_at": timezone.now().isoformat(),
    }

    messages.success(
        request,
        (
            f"Review draft created from {source.display_label}. "
            "No career-profile fields or match scores were changed."
        ),
    )
    return redirect("candidate_profile:resume_extraction_review")


@require_http_methods(["GET"])
def resume_extraction_review(request):
    draft = request.session.get(RESUME_EXTRACTION_SESSION_KEY)
    if not draft:
        messages.info(request, "No resume extraction draft is waiting for review.")
        return redirect("candidate_profile:resume_source_list")

    source_data = draft.get("source", {})
    source = ResumeSource.objects.filter(id=source_data.get("id")).first()
    if source is None or source.sha256 != source_data.get("sha256"):
        request.session.pop(RESUME_EXTRACTION_SESSION_KEY, None)
        messages.error(
            request,
            "The resume source for this draft no longer exists or no longer matches.",
        )
        return redirect("candidate_profile:resume_source_list")

    return render(
        request,
        "candidate_profile/resume_extraction_review.html",
        {
            "draft": draft,
            "source": source,
            "document": draft.get("document", {}),
            "extraction": draft.get("extraction", {}),
        },
    )


@require_POST
def clear_resume_extraction(request):
    request.session.pop(RESUME_EXTRACTION_SESSION_KEY, None)
    messages.success(
        request,
        "Resume extraction draft discarded. The stored resume source remains available.",
    )
    return redirect("candidate_profile:resume_source_list")
