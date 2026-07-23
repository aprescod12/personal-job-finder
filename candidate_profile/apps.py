from django.apps import AppConfig


class CandidateProfileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "candidate_profile"
    verbose_name = "Candidate profile sources"

    def ready(self):
        # Snapshot models live in a dedicated module so the existing résumé-source
        # model file can remain focused. Importing here registers them for every
        # Django command, including migrations and system checks.
        from . import snapshot_models  # noqa: F401
