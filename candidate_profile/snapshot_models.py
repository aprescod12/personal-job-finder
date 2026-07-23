from django.db import models

from tracker.models import CareerProfile

from .models import CandidateProfileClaim


class CandidateProfileSnapshot(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft preview"
        ACTIVE = "active", "Active for matching"
        ARCHIVED = "archived", "Archived"

    profile = models.ForeignKey(
        CareerProfile,
        on_delete=models.CASCADE,
        related_name="candidate_profile_snapshots",
    )
    version = models.PositiveIntegerField()
    composition_version = models.CharField(max_length=120)
    fingerprint = models.CharField(max_length=64)
    data = models.JSONField(default=dict)
    warnings = models.JSONField(default=list, blank=True)
    source_claim_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "candidate_profile"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "version"],
                name="unique_candidate_snapshot_version",
            ),
            models.UniqueConstraint(
                fields=["profile", "fingerprint"],
                name="unique_candidate_snapshot_fingerprint",
            ),
            models.UniqueConstraint(
                fields=["profile"],
                condition=models.Q(status="active"),
                name="one_active_candidate_snapshot",
            ),
        ]
        indexes = [
            models.Index(
                fields=["profile", "status", "-version"],
                name="candidate_snapshot_status_idx",
            ),
            models.Index(
                fields=["fingerprint"],
                name="candidate_snapshot_fp_idx",
            ),
        ]
        verbose_name = "candidate profile snapshot"
        verbose_name_plural = "candidate profile snapshots"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def identity(self):
        return self.data.get("identity", {})

    @property
    def profile_data(self):
        return self.data.get("profile", {})

    def __str__(self):
        return f"Candidate profile v{self.version} ({self.get_status_display()})"


class CandidateProfileSnapshotClaim(models.Model):
    snapshot = models.ForeignKey(
        CandidateProfileSnapshot,
        on_delete=models.CASCADE,
        related_name="source_claim_links",
    )
    candidate_claim = models.ForeignKey(
        CandidateProfileClaim,
        on_delete=models.PROTECT,
        related_name="snapshot_links",
    )
    position = models.PositiveIntegerField(default=0)
    section = models.CharField(max_length=30)
    field_path = models.CharField(max_length=255)
    semantic_key = models.CharField(max_length=64)
    value = models.JSONField()

    class Meta:
        app_label = "candidate_profile"
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "candidate_claim"],
                name="unique_claim_per_candidate_snapshot",
            ),
        ]
        indexes = [
            models.Index(
                fields=["snapshot", "section", "position"],
                name="snapshot_claim_section_idx",
            ),
            models.Index(
                fields=["candidate_claim"],
                name="snapshot_claim_source_idx",
            ),
        ]
        verbose_name = "candidate profile snapshot claim"
        verbose_name_plural = "candidate profile snapshot claims"

    def __str__(self):
        return f"Snapshot v{self.snapshot.version}: {self.field_path}"
