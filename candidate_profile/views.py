from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tracker.models import CareerProfile

from .forms import ResumeSourceUploadForm
from .models import ResumeSource


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
