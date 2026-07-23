from collections import OrderedDict

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tracker.models import CareerProfile

from .models import CandidateProfileClaim, ResumeReviewClaim
from .services.candidate_profile_composition import (
    CandidateProfileCompositionError,
    activate_candidate_profile_snapshot,
    compose_candidate_profile_snapshot,
)
from .snapshot_models import CandidateProfileSnapshot


SNAPSHOT_SECTION_ORDER = (
    ("education", "Education"),
    ("experience", "Experience"),
    ("projects", "Projects"),
    ("skills", "Skills"),
    ("certifications", "Certifications"),
    ("leadership", "Leadership"),
)


def candidate_snapshot_list(request):
    profile = CareerProfile.get_solo()
    snapshots = list(
        CandidateProfileSnapshot.objects.filter(profile=profile).order_by("-version")
    )
    active_snapshot = next((item for item in snapshots if item.is_active), None)
    return render(
        request,
        "candidate_profile/candidate_snapshot_list.html",
        {
            "profile": profile,
            "snapshots": snapshots,
            "active_snapshot": active_snapshot,
            "active_claim_count": CandidateProfileClaim.objects.filter(
                profile=profile,
                is_active=True,
            ).count(),
        },
    )


@require_POST
def compose_candidate_snapshot(request):
    profile = CareerProfile.get_solo()
    try:
        snapshot, created = compose_candidate_profile_snapshot(profile)
    except CandidateProfileCompositionError as exc:
        messages.error(request, str(exc))
        return redirect("candidate_profile:candidate_snapshot_list")

    if created:
        messages.success(
            request,
            (
                f"Candidate profile v{snapshot.version} composed for preview. "
                "It will not affect matching until you activate it."
            ),
        )
    else:
        messages.info(
            request,
            (
                f"The approved evidence is unchanged, so candidate profile "
                f"v{snapshot.version} was reused."
            ),
        )
    return redirect("candidate_profile:candidate_snapshot_detail", snapshot.id)


def candidate_snapshot_detail(request, snapshot_id):
    profile = CareerProfile.get_solo()
    snapshot = get_object_or_404(
        CandidateProfileSnapshot,
        pk=snapshot_id,
        profile=profile,
    )
    links = list(
        snapshot.source_claim_links.select_related("candidate_claim").order_by(
            "position",
            "id",
        )
    )
    provenance_groups = OrderedDict(
        (
            section,
            {
                "key": section,
                "label": label,
                "links": [],
            },
        )
        for section, label in ResumeReviewClaim.Section.choices
    )
    for link in links:
        if link.section in provenance_groups:
            provenance_groups[link.section]["links"].append(link)

    return render(
        request,
        "candidate_profile/candidate_snapshot_detail.html",
        {
            "profile": profile,
            "snapshot": snapshot,
            "identity": snapshot.identity,
            "profile_data": snapshot.profile_data,
            "section_order": SNAPSHOT_SECTION_ORDER,
            "provenance_groups": [
                group for group in provenance_groups.values() if group["links"]
            ],
        },
    )


@require_POST
def activate_candidate_snapshot(request, snapshot_id):
    profile = CareerProfile.get_solo()
    snapshot = get_object_or_404(
        CandidateProfileSnapshot,
        pk=snapshot_id,
        profile=profile,
    )
    snapshot, changed = activate_candidate_profile_snapshot(snapshot)
    if changed:
        messages.success(
            request,
            (
                f"Candidate profile v{snapshot.version} is now active. "
                "Job matching will combine this evidence with your manual preferences."
            ),
        )
    else:
        messages.info(
            request,
            f"Candidate profile v{snapshot.version} was already active.",
        )
    return redirect("candidate_profile:candidate_snapshot_detail", snapshot.id)
