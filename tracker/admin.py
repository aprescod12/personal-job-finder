from django.contrib import admin

from .models import CareerProfile, JobPosting


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


@admin.register(CareerProfile)
class CareerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "experience_level",
        "preferred_work_arrangement",
        "preferred_employment_type",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return not CareerProfile.objects.exists()
