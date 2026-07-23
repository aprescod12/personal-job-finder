from django.urls import path

from .views import (
    activate_resume_source,
    candidate_claim_list,
    clear_resume_extraction,
    delete_resume_source,
    resume_extraction_review,
    resume_source_list,
    run_resume_extraction,
)


app_name = "candidate_profile"

urlpatterns = [
    path("", resume_source_list, name="resume_source_list"),
    path("claims/", candidate_claim_list, name="candidate_claim_list"),
    path(
        "<int:source_id>/activate/",
        activate_resume_source,
        name="activate_resume_source",
    ),
    path(
        "<int:source_id>/delete/",
        delete_resume_source,
        name="delete_resume_source",
    ),
    path(
        "<int:source_id>/extract/",
        run_resume_extraction,
        name="run_resume_extraction",
    ),
    path(
        "extraction/review/",
        resume_extraction_review,
        name="resume_extraction_review",
    ),
    path(
        "extraction/clear/",
        clear_resume_extraction,
        name="clear_resume_extraction",
    ),
]
