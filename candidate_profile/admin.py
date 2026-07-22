from django.contrib import admin

from .models import ResumeSource


@admin.register(ResumeSource)
class ResumeSourceAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
