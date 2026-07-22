from django.urls import path

from .views import activate_resume_source, resume_source_list


app_name = "candidate_profile"

urlpatterns = [
    path("", resume_source_list, name="resume_source_list"),
    path(
        "<int:source_id>/activate/",
        activate_resume_source,
        name="activate_resume_source",
    ),
]
