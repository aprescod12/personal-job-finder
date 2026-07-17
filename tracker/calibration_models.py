from django.db import models

from .models_base import JobPosting


class MatchCalibration(models.Model):
    class Verdict(models.TextChoices):
        STRONG = "strong", "Strong match"
        POSSIBLE = "possible", "Possible match"
        WEAK = "weak", "Weak match"
        NOT_ELIGIBLE = "not_eligible", "Not eligible"
        UNSURE = "unsure", "Unsure / needs more review"

    job = models.OneToOneField(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="calibration",
    )
    verdict = models.CharField(max_length=20, choices=Verdict.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reviewed_at"]
        verbose_name = "match calibration"
        verbose_name_plural = "match calibrations"

    def __str__(self):
        return f"Calibration for {self.job}: {self.get_verdict_display()}"
