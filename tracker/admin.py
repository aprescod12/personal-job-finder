from django.contrib import admin

from .models import JobPosting


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "status",
        "location",
        "employment_type",
        "work_arrangement",
        "application_deadline",
        "updated_at",
    )
    list_filter = ("status", "employment_type", "work_arrangement")
    search_fields = ("title", "company", "location", "description", "notes")
    date_hierarchy = "created_at"
