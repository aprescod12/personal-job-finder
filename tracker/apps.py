from django.apps import AppConfig


class TrackerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tracker"

    def ready(self):
        """Register the current calibrated matcher for application-wide use."""

        from .services import strategy_matching
        from .services.software_strategy_matching import (
            analyze_job_match as analyze_software_aware_match,
        )

        # Views and existing integrations import from strategy_matching. Keeping
        # this stable facade lets the active strategy evolve without duplicating
        # matching calls throughout the application.
        strategy_matching.analyze_job_match = analyze_software_aware_match
