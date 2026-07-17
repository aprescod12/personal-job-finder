from django.contrib import admin

from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement


class JobRequirementInline(admin.StackedInline):
    model = JobRequirement
    extra = 1
    max_num = 1


class JobCalibrationInline(admin.StackedInline):
    model = JobCalibration
    extra = 1
    max_num = 1
    readonly_fields = (
        "predicted_score",
        "predicted_classification",
        "predicted_track",
        "created_at",
        "updated_at",
    )


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
    inlines = (JobRequirementInline, JobCalibrationInline)


@admin.register(JobRequirement)
class JobRequirementAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "role_family",
        "seniority_level",
        "industry",
        "updated_at",
    )
    list_filter = ("seniority_level",)
    search_fields = (
        "job__title",
        "job__company",
        "role_family",
        "industry",
        "required_skills",
        "preferred_skills",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(JobCalibration)
class JobCalibrationAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "human_rating",
        "opportunity_type",
        "predicted_score",
        "predicted_classification",
        "agreement_status",
        "updated_at",
    )
    list_filter = ("human_rating", "opportunity_type", "predicted_classification")
    search_fields = ("job__title", "job__company", "notes")
    readonly_fields = (
        "predicted_score",
        "predicted_classification",
        "predicted_track",
        "created_at",
        "updated_at",
    )


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
