from django.urls import path

from . import views
from .calibration_views import calibration_report, weight_model_comparison


urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("profile/", views.career_profile, name="career_profile"),
    path("calibration/", calibration_report, name="calibration_report"),
    path(
        "calibration/weights/",
        weight_model_comparison,
        name="weight_model_comparison",
    ),
    path("jobs/add/", views.job_create, name="job_create"),
    path("jobs/<int:job_id>/", views.job_detail, name="job_detail"),
    path(
        "jobs/<int:job_id>/verify/",
        views.job_listing_verify,
        name="job_listing_verify",
    ),
    path("jobs/<int:job_id>/match/", views.job_match, name="job_match"),
    path(
        "jobs/<int:job_id>/requirements/",
        views.job_requirements,
        name="job_requirements",
    ),
    path("jobs/<int:job_id>/edit/", views.job_edit, name="job_edit"),
    path("jobs/<int:job_id>/delete/", views.job_delete, name="job_delete"),
]
