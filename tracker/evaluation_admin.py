from django.contrib import admin

from .evaluation_models import JobEvaluationRun


@admin.register(JobEvaluationRun)
class JobEvaluationRunAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "score",
        "classification",
        "track",
        "matcher_version",
        "candidate_snapshot_version",
        "is_current",
        "trigger",
        "evaluated_at",
    )
    list_filter = (
        "is_current",
        "trigger",
        "matcher_version",
        "classification",
        "track",
    )
    search_fields = (
        "job__title",
        "job__company",
        "matcher_version",
        "profile_fingerprint",
        "job_fingerprint",
    )
    date_hierarchy = "evaluated_at"
    readonly_fields = tuple(field.name for field in JobEvaluationRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
