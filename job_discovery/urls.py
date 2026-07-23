from django.urls import path

from . import views


app_name = "job_discovery"

urlpatterns = [
    path("", views.discovery_inbox, name="inbox"),
    path("run/", views.run_discovery_view, name="run"),
    path(
        "opportunities/<int:opportunity_id>/",
        views.opportunity_detail,
        name="opportunity_detail",
    ),
    path(
        "opportunities/<int:opportunity_id>/ignore/",
        views.ignore_opportunity,
        name="ignore_opportunity",
    ),
    path(
        "opportunities/<int:opportunity_id>/restore/",
        views.restore_opportunity,
        name="restore_opportunity",
    ),
    path(
        "opportunities/<int:opportunity_id>/retain-duplicate/",
        views.retain_duplicate,
        name="retain_duplicate",
    ),
    path(
        "opportunities/<int:opportunity_id>/send-to-processing/",
        views.send_to_processing,
        name="send_to_processing",
    ),
]
