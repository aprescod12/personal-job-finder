from django.shortcuts import render

from .models import CareerProfile, JobCalibration
from .services.calibration_reporting import build_calibration_report
from .validation_batch import (
    CALIBRATION_SOURCE,
    VALIDATION_BATCH,
    VALIDATION_SOURCE,
)


FILTER_CHOICES = (
    ("", "All reviewed jobs"),
    ("attention", "Needs matcher review"),
    ("aligned", "Current matcher aligned"),
    ("changed", "Strategy changed result"),
    ("improved", "Improved since saved snapshot"),
    ("regressed", "Regressed since saved snapshot"),
)

SCOPE_CHOICES = (
    ("", "All calibration sources"),
    ("validation", "Unseen validation holdout"),
    ("calibration", "Original calibration batch"),
    ("other", "Manual and other reviews"),
)


def _filter_scope(calibrations, selected_scope):
    if selected_scope == "validation":
        return calibrations.filter(job__source=VALIDATION_SOURCE)
    if selected_scope == "calibration":
        return calibrations.filter(job__source=CALIBRATION_SOURCE)
    if selected_scope == "other":
        return calibrations.exclude(
            job__source__in=(CALIBRATION_SOURCE, VALIDATION_SOURCE)
        )
    return calibrations


def calibration_report(request):
    selected_filter = request.GET.get("status", "").strip()
    selected_scope = request.GET.get("scope", "").strip()
    valid_filters = {value for value, _ in FILTER_CHOICES}
    valid_scopes = {value for value, _ in SCOPE_CHOICES}

    if selected_filter not in valid_filters:
        selected_filter = ""
    if selected_scope not in valid_scopes:
        selected_scope = ""

    profile = CareerProfile.get_solo()
    calibrations = JobCalibration.objects.select_related("job").all()
    calibrations = _filter_scope(calibrations, selected_scope)
    report = build_calibration_report(profile, calibrations)
    rows = report.rows

    if selected_filter == "attention":
        rows = [row for row in rows if row.needs_attention]
    elif selected_filter == "aligned":
        rows = [
            row
            for row in rows
            if row.rating_status == "ALIGNED"
            and row.lane_status in {"ALIGNED", "NOT SCORED"}
        ]
    elif selected_filter == "changed":
        rows = [row for row in rows if row.strategy_changed]
    elif selected_filter == "improved":
        rows = [row for row in rows if row.change_status == "IMPROVED"]
    elif selected_filter == "regressed":
        rows = [row for row in rows if row.change_status == "REGRESSED"]

    validation_reviewed = JobCalibration.objects.filter(
        job__source=VALIDATION_SOURCE
    ).count()

    return render(
        request,
        "tracker/calibration_report.html",
        {
            "report": report,
            "rows": rows,
            "selected_filter": selected_filter,
            "filter_choices": FILTER_CHOICES,
            "selected_scope": selected_scope,
            "scope_choices": SCOPE_CHOICES,
            "validation_reviewed": validation_reviewed,
            "validation_total": len(VALIDATION_BATCH),
            "validation_complete": validation_reviewed >= len(VALIDATION_BATCH),
        },
    )
