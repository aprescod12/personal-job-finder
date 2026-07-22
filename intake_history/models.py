from django.db import models


class JobExtractionRun(models.Model):
    """Read-only provenance captured when a reviewed intake draft is approved."""

    job = models.ForeignKey(
        "tracker.JobPosting",
        on_delete=models.CASCADE,
        related_name="extraction_runs",
    )

    source_url = models.URLField(max_length=1000, blank=True)
    normalized_source_url = models.CharField(max_length=1000, blank=True)
    source_label = models.CharField(max_length=100, blank=True)
    raw_text = models.TextField()
    raw_text_sha256 = models.CharField(max_length=64)
    role_identity_sha256 = models.CharField(max_length=64, blank=True)

    provider_key = models.CharField(max_length=100, blank=True)
    provider_label = models.CharField(max_length=200, blank=True)
    provider_version = models.CharField(max_length=100, blank=True)
    extraction_mode = models.CharField(max_length=30, blank=True)

    orchestration_status = models.CharField(max_length=50, blank=True)
    fallback_used = models.BooleanField(default=False)
    manual_review_required = models.BooleanField(default=False)
    total_elapsed_ms = models.PositiveIntegerField(default=0)
    attempts = models.JSONField(default=list, blank=True)

    evidence = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    extracted_payload = models.JSONField(default=dict, blank=True)
    reviewed_payload = models.JSONField(default=dict, blank=True)

    duplicate_candidates = models.JSONField(default=list, blank=True)
    duplicate_override = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["job", "-created_at"],
                name="intake_job_created_idx",
            ),
            models.Index(
                fields=["raw_text_sha256"],
                name="intake_text_hash_idx",
            ),
            models.Index(
                fields=["normalized_source_url"],
                name="intake_url_idx",
            ),
        ]
        verbose_name = "job extraction run"
        verbose_name_plural = "job extraction runs"

    @property
    def fingerprint_short(self):
        return self.raw_text_sha256[:12]

    def __str__(self):
        return f"Extraction for {self.job} at {self.created_at:%Y-%m-%d %H:%M}"
