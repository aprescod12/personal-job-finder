from django.db import models

from candidate_profile.snapshot_models import CandidateProfileSnapshot

from .models import CareerProfile, JobPosting


class JobEvaluationRun(models.Model):
    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual job reevaluation"
        BULK = "bulk", "Bulk job reevaluation"

    job = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="evaluation_runs",
    )
    profile = models.ForeignKey(
        CareerProfile,
        on_delete=models.PROTECT,
        related_name="job_evaluation_runs",
    )
    candidate_snapshot = models.ForeignKey(
        CandidateProfileSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_evaluation_runs",
    )
    previous_run = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_runs",
    )

    trigger = models.CharField(
        max_length=20,
        choices=Trigger.choices,
        default=Trigger.MANUAL,
    )
    matcher_version = models.CharField(max_length=120)
    candidate_snapshot_version = models.PositiveIntegerField(null=True, blank=True)
    candidate_snapshot_composition_version = models.CharField(max_length=120, blank=True)
    profile_fingerprint = models.CharField(max_length=64)
    job_fingerprint = models.CharField(max_length=64)

    has_requirements = models.BooleanField(default=False)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    classification = models.CharField(max_length=40, blank=True)
    track = models.CharField(max_length=40, blank=True)
    evidence_coverage = models.PositiveSmallIntegerField(default=0)
    result_data = models.JSONField(default=dict)
    comparison_data = models.JSONField(default=dict, blank=True)

    is_current = models.BooleanField(default=True)
    stale_reasons = models.JSONField(default=list, blank=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tracker"
        ordering = ["-evaluated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["job"],
                condition=models.Q(is_current=True),
                name="one_current_job_evaluation",
            ),
        ]
        indexes = [
            models.Index(
                fields=["job", "-evaluated_at"],
                name="job_eval_history_idx",
            ),
            models.Index(
                fields=["is_current", "-evaluated_at"],
                name="job_eval_current_idx",
            ),
            models.Index(
                fields=["candidate_snapshot", "-evaluated_at"],
                name="job_eval_snapshot_idx",
            ),
        ]
        verbose_name = "job evaluation run"
        verbose_name_plural = "job evaluation runs"

    @property
    def is_stale(self):
        return not self.is_current

    @property
    def score_delta(self):
        value = self.comparison_data.get("score_delta")
        return value if isinstance(value, int) else None

    def __str__(self):
        state = "current" if self.is_current else "stale"
        return f"Evaluation for {self.job} ({state})"
