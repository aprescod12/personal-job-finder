from django.contrib import admin

from .models import (
    CandidateProfileClaim,
    ResumeExtractionReview,
    ResumeReviewClaim,
    ResumeSource,
)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ResumeSource)
class ResumeSourceAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "display_label",
        "profile",
        "is_active",
        "review_status",
        "original_filename",
        "file_size",
        "created_at",
    )
    list_filter = ("is_active", "review_status", "created_at")
    search_fields = (
        "label",
        "original_filename",
        "sha256",
        "profile__full_name",
        "notes",
    )
    readonly_fields = (
        "profile",
        "document",
        "original_filename",
        "label",
        "content_type",
        "file_size",
        "sha256",
        "is_active",
        "review_status",
        "notes",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"


@admin.register(ResumeExtractionReview)
class ResumeExtractionReviewAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "source_label",
        "profile",
        "status",
        "provider_key",
        "provider_version",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "provider_mode", "provider_key", "created_at")
    search_fields = (
        "source_label",
        "source_filename",
        "source_sha256",
        "provider_key",
        "provider_version",
        "profile__full_name",
    )
    readonly_fields = tuple(
        field.name for field in ResumeExtractionReview._meta.fields
    )
    date_hierarchy = "created_at"


@admin.register(ResumeReviewClaim)
class ResumeReviewClaimAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "field_path",
        "section",
        "decision",
        "review",
        "applied_at",
        "updated_at",
    )
    list_filter = ("section", "decision", "claim_type", "applied_at")
    search_fields = (
        "claim_key",
        "field_path",
        "source_text",
        "review__source_label",
    )
    readonly_fields = tuple(field.name for field in ResumeReviewClaim._meta.fields)


@admin.register(CandidateProfileClaim)
class CandidateProfileClaimAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "field_path",
        "section",
        "profile",
        "source_label",
        "provider_version",
        "is_active",
        "approved_at",
    )
    list_filter = ("section", "is_active", "provider_mode", "approved_at")
    search_fields = (
        "claim_key",
        "field_path",
        "source_label",
        "source_sha256",
        "provider_key",
        "provider_version",
        "profile__full_name",
    )
    readonly_fields = tuple(field.name for field in CandidateProfileClaim._meta.fields)
    date_hierarchy = "approved_at"
