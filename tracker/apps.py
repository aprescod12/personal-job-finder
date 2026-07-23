from django.apps import AppConfig


class TrackerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tracker"

    def ready(self):
        """Register runtime models, the active matcher, and input invalidation."""

        from . import evaluation_models  # noqa: F401
        from .services import strategy_matching
        from .services.semantic_strategy_matching import (
            analyze_job_match as analyze_controlled_semantic_match,
        )

        # Views and existing integrations import from strategy_matching. Keeping
        # this stable facade lets the active strategy evolve without duplicating
        # matching calls throughout the application.
        strategy_matching.analyze_job_match = analyze_controlled_semantic_match

        from . import evaluation_admin  # noqa: F401,E402
        from . import evaluation_signals  # noqa: F401,E402
