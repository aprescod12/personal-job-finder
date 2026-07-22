from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models

from tracker.models import CareerProfile


ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}


def resume_upload_path(instance, filename):
    extension = Path(filename).suffix.casefold()
    return f"resumes/profile-{instance.profile_id}/{uuid4().hex}{extension}"


class ResumeSource(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        REVIEWED = "reviewed", "Reviewed"
        REJECTED = "rejected", "Rejected"

    profile = models.ForeignKey(
        CareerProfile,
        on_delete=models.CASCADE,
        related_name="resume_sources",
    )
    document = models.FileField(upload_to=resume_upload_path)
    original_filename = models.CharField(max_length=255)
    label = models.CharField(max_length=120, blank=True)
    content_type = models.CharField(max_length=150, blank=True)
    file_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    is_active = models.BooleanField(default=False)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "sha256"],
                name="unique_resume_content_per_profile",
            ),
            models.UniqueConstraint(
                fields=["profile"],
                condition=models.Q(is_active=True),
                name="one_active_resume_per_profile",
            ),
        ]
        indexes = [
            models.Index(
                fields=["profile", "-created_at"],
                name="resume_profile_created_idx",
            ),
        ]
        verbose_name = "resume source"
        verbose_name_plural = "resume sources"

    def clean(self):
        super().clean()
        extension = Path(self.original_filename or self.document.name).suffix.casefold()
        if extension not in ALLOWED_RESUME_EXTENSIONS:
            raise ValidationError(
                {"document": "Upload a PDF, DOCX, or plain-text resume."}
            )

    @property
    def display_label(self):
        return self.label or self.original_filename

    @property
    def short_fingerprint(self):
        return self.sha256[:12]

    def __str__(self):
        active_label = "active" if self.is_active else "stored"
        return f"{self.display_label} ({active_label})"
