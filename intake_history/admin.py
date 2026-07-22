from django.contrib import admin

from .models import JobExtractionRun


@admin.register(JobExtractionRun)
class JobExtractionRunAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "provider_label",
        "provider_version",
        "extraction_mode",
        "fallback_used",
        "duplicate_override",
        "created_at",
    )
    list_filter = (
        "extraction_mode",
        "fallback_used",
        "manual_review_required",
        "duplicate_override",
        "created_at",
    )
    search_fields = (
        "job__title",
        "job__company",
        "source_url",
        "source_label",
        "provider_key",
        "provider_label",
        "provider_version",
        "raw_text_sha256",
    )
    date_hierarchy = "created_at"
    readonly_fields = (
        "job",
        "source_url",
        "normalized_source_url",
        "source_label",
        "raw_text",
        "raw_text_sha256",
        "role_identity_sha256",
        "provider_key",
        "provider_label",
        "provider_version",
        "extraction_mode",
        "orchestration_status",
        "fallback_used",
        "manual_review_required",
        "total_elapsed_ms",
        "attempts",
        "evidence",
        "warnings",
        "extracted_payload",
        "reviewed_payload",
        "duplicate_candidates",
        "duplicate_override",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
