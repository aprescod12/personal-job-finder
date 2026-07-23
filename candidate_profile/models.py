from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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


class ResumeExtractionReview(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending decisions"
        IN_REVIEW = "in_review", "Review in progress"
        COMPLETED = "completed", "Completed"
        DISCARDED = "discarded", "Discarded"
        STALE = "stale", "Superseded by newer extraction"

    profile = models.ForeignKey(
        CareerProfile,
        on_delete=models.CASCADE,
        related_name="resume_extraction_reviews",
    )
    source = models.ForeignKey(
        ResumeSource,
        on_delete=models.CASCADE,
        related_name="extraction_reviews",
    )
    source_sha256 = models.CharField(max_length=64)
    source_label = models.CharField(max_length=120)
    source_filename = models.CharField(max_length=255)

    provider_key = models.CharField(max_length=100)
    provider_label = models.CharField(max_length=160)
    provider_version = models.CharField(max_length=120)
    provider_mode = models.CharField(max_length=40)
    document_parser_key = models.CharField(max_length=100)
    document_parser_version = models.CharField(max_length=120)

    orchestration = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    document_warnings = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["profile", "status", "-created_at"],
                name="resume_review_status_idx",
            ),
            models.Index(
                fields=["source", "-created_at"],
                name="resume_review_source_idx",
            ),
        ]
        verbose_name = "resume extraction review"
        verbose_name_plural = "resume extraction reviews"

    @property
    def is_open(self):
        return self.status in {self.Status.PENDING, self.Status.IN_REVIEW}

    @property
    def pending_count(self):
        return self.claims.filter(decision=ResumeReviewClaim.Decision.PENDING).count()

    @property
    def approved_count(self):
        return self.claims.filter(decision=ResumeReviewClaim.Decision.APPROVED).count()

    @property
    def rejected_count(self):
        return self.claims.filter(decision=ResumeReviewClaim.Decision.REJECTED).count()

    @property
    def applied_count(self):
        return self.claims.filter(applied_at__isnull=False).count()

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def __str__(self):
        return f"Review for {self.source_label} ({self.get_status_display()})"


class ResumeReviewClaim(models.Model):
    class Section(models.TextChoices):
        IDENTITY = "identity", "Identity"
        SUMMARY = "summary", "Professional summary"
        EDUCATION = "education", "Education"
        EXPERIENCE = "experience", "Experience"
        PROJECTS = "projects", "Projects"
        SKILLS = "skills", "Skills"
        CERTIFICATIONS = "certifications", "Certifications"
        LEADERSHIP = "leadership", "Leadership"

    class ClaimType(models.TextChoices):
        SCALAR = "scalar", "Single value"
        LIST_ITEM = "list_item", "List item"
        ENTRY = "entry", "Structured entry"

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approve"
        REJECTED = "rejected", "Reject"

    review = models.ForeignKey(
        ResumeExtractionReview,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    claim_key = models.CharField(max_length=180)
    field_path = models.CharField(max_length=255)
    section = models.CharField(max_length=30, choices=Section.choices)
    claim_type = models.CharField(max_length=20, choices=ClaimType.choices)
    position = models.PositiveIntegerField(default=0)

    extracted_value = models.JSONField()
    reviewed_value = models.JSONField()
    source_text = models.TextField(blank=True)
    evidence_note = models.TextField(blank=True)
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDING,
    )
    applied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["review", "claim_key"],
                name="unique_claim_key_per_review",
            ),
        ]
        indexes = [
            models.Index(
                fields=["review", "section", "position"],
                name="review_claim_section_idx",
            ),
            models.Index(
                fields=["decision", "applied_at"],
                name="review_claim_decision_idx",
            ),
        ]
        verbose_name = "resume review claim"
        verbose_name_plural = "resume review claims"

    @property
    def is_applied(self):
        return self.applied_at is not None

    @property
    def is_editable(self):
        return self.applied_at is None and self.review.is_open

    def __str__(self):
        return f"{self.field_path} — {self.get_decision_display()}"


class CandidateProfileClaim(models.Model):
    profile = models.ForeignKey(
        CareerProfile,
        on_delete=models.CASCADE,
        related_name="approved_resume_claims",
    )
    source = models.ForeignKey(
        ResumeSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_candidate_claims",
    )
    review_claim = models.OneToOneField(
        ResumeReviewClaim,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_profile_claim",
    )

    section = models.CharField(max_length=30, choices=ResumeReviewClaim.Section.choices)
    claim_key = models.CharField(max_length=180)
    field_path = models.CharField(max_length=255)
    semantic_key = models.CharField(max_length=64)
    value = models.JSONField()
    source_text = models.TextField(blank=True)
    evidence_note = models.TextField(blank=True)

    source_sha256 = models.CharField(max_length=64)
    source_label = models.CharField(max_length=120)
    source_filename = models.CharField(max_length=255)
    provider_key = models.CharField(max_length=100)
    provider_version = models.CharField(max_length=120)
    provider_mode = models.CharField(max_length=40)
    document_parser_key = models.CharField(max_length=100)
    document_parser_version = models.CharField(max_length=120)

    is_active = models.BooleanField(default=True)
    approved_at = models.DateTimeField(auto_now_add=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["section", "approved_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "semantic_key"],
                condition=models.Q(is_active=True),
                name="active_candidate_claim_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["profile", "is_active", "section"],
                name="candidate_claim_active_idx",
            ),
            models.Index(
                fields=["source_sha256", "approved_at"],
                name="candidate_claim_source_idx",
            ),
        ]
        verbose_name = "approved candidate profile claim"
        verbose_name_plural = "approved candidate profile claims"

    def __str__(self):
        state = "active" if self.is_active else "superseded"
        return f"{self.field_path} ({state})"
