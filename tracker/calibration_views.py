from django.shortcuts import render

from .models import CareerProfile, JobCalibration
from .services.calibration_reporting import build_calibration_report


FILTER_CHOICES = (
    ("", "All reviewed jobs"),
    ("attention", "Needs matcher review"),
    ("aligned", "Current matcher aligned"),
    ("changed", "Strategy changed result"),
    ("improved", "Improved since saved snapshot"),
    ("regressed", "Regressed since saved snapshot"),
)


def calibration_report(request):
    selected_filter = request.GET.get("status", "").strip()
    valid_filters = {value for value, _ in FILTER_CHOICES}
    if selected_filter not in valid_filters:
        selected_filter = ""

    profile = CareerProfile.get_solo()
    calibrations = JobCalibration.objects.select_related("job").all()
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

    return render(
        request,
        "tracker/calibration_report.html",
        {
            "report": report,
            "rows": rows,
            "selected_filter": selected_filter,
            "filter_choices": FILTER_CHOICES,
        },
    )
