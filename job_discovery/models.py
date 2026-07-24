from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class DiscoveryRun(models.Model):
    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual search"
        SCHEDULED = "scheduled", "Scheduled search"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partially completed"
        FAILED = "failed", "Failed"

    provider_key = models.CharField(max_length=80)
    provider_label = models.CharField(max_length=160)
    provider_version = models.CharField(max_length=100)
    trigger = models.CharField(
        max_length=20,
        choices=Trigger.choices,
        default=Trigger.MANUAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    query_payload = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    outside_preference_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["provider_key", "-created_at"],
                name="disc_run_provider_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="disc_run_status_idx",
            ),
        ]

    @property
    def duration_seconds(self):
        if not self.completed_at:
            return None
        return max(0.0, (self.completed_at - self.started_at).total_seconds())

    def __str__(self):
        return f"{self.provider_label} discovery at {self.created_at:%Y-%m-%d %H:%M}"


class DiscoverySourceAttempt(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    run = models.ForeignKey(
        DiscoveryRun,
        on_delete=models.CASCADE,
        related_name="source_attempts",
    )
    source_key = models.CharField(max_length=100)
    source_label = models.CharField(max_length=200)
    source_identifier = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    result_count = models.PositiveIntegerField(default=0)
    elapsed_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_label", "source_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "source_key"],
                name="disc_source_run_key_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="disc_source_status_idx",
            )
        ]

    def __str__(self):
        return f"{self.source_label}: {self.get_status_display()}"


class RawJobOpportunity(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        DUPLICATE = "duplicate", "Duplicate"
        READY = "ready", "Ready for processing"
        IGNORED = "ignored", "Ignored"
        SENT_TO_PROCESSING = "sent_to_processing", "Sent to processing"
        PROCESSED = "processed", "Processed"
        PROCESSING_FAILED = "processing_failed", "Processing failed"

    class BroadRelevance(models.TextChoices):
        BROAD_MATCH = "broad_match", "Broad preference match"
        UNKNOWN = "unknown", "Not enough information"
        OUTSIDE = "outside", "Outside broad preferences"

    run = models.ForeignKey(
        DiscoveryRun,
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    provider_key = models.CharField(max_length=80)
    provider_label = models.CharField(max_length=160)
    provider_version = models.CharField(max_length=100)
    external_id = models.CharField(max_length=300, blank=True)

    source_url = models.URLField(max_length=1000, blank=True)
    normalized_source_url = models.URLField(max_length=1000, blank=True)
    title_hint = models.CharField(max_length=300, blank=True)
    company_hint = models.CharField(max_length=300, blank=True)
    location_hint = models.CharField(max_length=300, blank=True)
    employment_type_hint = models.CharField(max_length=80, blank=True)
    work_arrangement_hint = models.CharField(max_length=80, blank=True)
    industry_hint = models.CharField(max_length=200, blank=True)
    seniority_hint = models.CharField(max_length=100, blank=True)
    raw_listing_text = models.TextField()
    raw_text_sha256 = models.CharField(max_length=64)
    role_identity_sha256 = models.CharField(max_length=64, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)

    broad_relevance = models.CharField(
        max_length=30,
        choices=BroadRelevance.choices,
        default=BroadRelevance.UNKNOWN,
    )
    broad_relevance_reasons = models.JSONField(default=list, blank=True)
    duplicate_details = models.JSONField(default=list, blank=True)
    duplicate_of_opportunity = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rediscoveries",
    )
    duplicate_of_job = models.ForeignKey(
        "tracker.JobPosting",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_duplicates",
    )
    duplicate_override = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
    )
    decision_notes = models.TextField(blank=True)
    processing_error = models.TextField(blank=True)
    processed_job = models.ForeignKey(
        "tracker.JobPosting",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_sources",
    )

    source_is_active = models.BooleanField(default=True)
    source_last_seen_at = models.DateTimeField(default=timezone.now)
    source_closed_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(default=timezone.now)
    sent_to_processing_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-discovered_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "-discovered_at"],
                name="disc_opp_status_idx",
            ),
            models.Index(
                fields=["provider_key", "external_id"],
                name="disc_opp_provider_idx",
            ),
            models.Index(
                fields=["normalized_source_url"],
                name="disc_opp_url_idx",
            ),
            models.Index(
                fields=["raw_text_sha256"],
                name="disc_opp_text_idx",
            ),
            models.Index(
                fields=["provider_key", "source_is_active"],
                name="disc_opp_active_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.source_url and not self.raw_listing_text.strip():
            raise ValidationError(
                "A discovered opportunity must preserve a source URL or raw listing text."
            )
        if self.status == self.Status.PROCESSED and not self.processed_job_id:
            raise ValidationError(
                {"processed_job": "Processed opportunities must reference the created job."}
            )

    @property
    def has_blocking_duplicate(self):
        return any(bool(item.get("blocking")) for item in self.duplicate_details)

    @property
    def can_send_to_processing(self):
        return (
            self.source_is_active
            and self.source_closed_at is None
            and self.status
            in {
                self.Status.NEW,
                self.Status.READY,
                self.Status.PROCESSING_FAILED,
            }
            and (not self.has_blocking_duplicate or self.duplicate_override)
        )

    def __str__(self):
        title = self.title_hint or "Untitled opportunity"
        company = self.company_hint or self.provider_label
        return f"{title} at {company}"
