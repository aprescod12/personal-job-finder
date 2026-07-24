from django.contrib import admin

from .models import DiscoveryRun, DiscoverySourceAttempt, RawJobOpportunity


class RawJobOpportunityInline(admin.TabularInline):
    model = RawJobOpportunity
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "title_hint",
        "company_hint",
        "status",
        "broad_relevance",
        "source_is_active",
        "external_id",
        "discovered_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class DiscoverySourceAttemptInline(admin.TabularInline):
    model = DiscoverySourceAttempt
    extra = 0
    can_delete = False
    fields = (
        "source_label",
        "status",
        "result_count",
        "elapsed_ms",
        "error_message",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DiscoveryRun)
class DiscoveryRunAdmin(admin.ModelAdmin):
    list_display = (
        "provider_label",
        "status",
        "trigger",
        "result_count",
        "new_count",
        "duplicate_count",
        "created_at",
    )
    list_filter = ("status", "trigger", "provider_key")
    search_fields = ("provider_key", "provider_label", "error_message")
    readonly_fields = tuple(field.name for field in DiscoveryRun._meta.fields)
    inlines = (DiscoverySourceAttemptInline, RawJobOpportunityInline)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DiscoverySourceAttempt)
class DiscoverySourceAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "source_label",
        "status",
        "result_count",
        "elapsed_ms",
        "run",
        "created_at",
    )
    list_filter = ("status", "run__provider_key")
    search_fields = (
        "source_key",
        "source_label",
        "source_identifier",
        "error_message",
    )
    readonly_fields = tuple(field.name for field in DiscoverySourceAttempt._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RawJobOpportunity)
class RawJobOpportunityAdmin(admin.ModelAdmin):
    list_display = (
        "title_hint",
        "company_hint",
        "provider_label",
        "status",
        "source_is_active",
        "broad_relevance",
        "discovered_at",
    )
    list_filter = ("status", "source_is_active", "broad_relevance", "provider_key")
    search_fields = (
        "title_hint",
        "company_hint",
        "location_hint",
        "external_id",
        "source_url",
        "raw_listing_text",
    )
    readonly_fields = tuple(field.name for field in RawJobOpportunity._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
