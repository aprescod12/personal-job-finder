import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0006_listing_reliability_and_good_match"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingVerificationRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "trigger",
                    models.CharField(
                        choices=[
                            ("manual", "Manual request"),
                            ("agent", "Verification agent"),
                            ("scheduled", "Scheduled check"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("needs_review", "Needs manual review"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "requested_url",
                    models.URLField(blank=True, max_length=1000),
                ),
                (
                    "final_url",
                    models.URLField(blank=True, max_length=1000),
                ),
                (
                    "http_status_code",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "detected_job_title",
                    models.CharField(blank=True, max_length=300),
                ),
                (
                    "detected_company",
                    models.CharField(blank=True, max_length=300),
                ),
                (
                    "detected_listing_status",
                    models.CharField(
                        choices=[
                            ("unverified", "Unverified"),
                            ("open", "Open"),
                            ("closed", "Closed by employer"),
                            ("expired", "Expired"),
                            ("link_broken", "Broken link"),
                            ("wrong_page", "Wrong company page"),
                        ],
                        default="unverified",
                        max_length=20,
                    ),
                ),
                (
                    "detected_deadline_status",
                    models.CharField(
                        choices=[
                            ("unknown", "Unknown"),
                            ("confirmed", "Confirmed date"),
                            ("rolling", "Rolling / open until filled"),
                            ("not_stated", "No deadline stated"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                (
                    "detected_deadline",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "apply_action_found",
                    models.BooleanField(blank=True, null=True),
                ),
                (
                    "confidence",
                    models.CharField(
                        choices=[
                            ("unknown", "Not assessed"),
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                (
                    "review_status",
                    models.CharField(
                        choices=[
                            ("not_required", "Not required"),
                            ("pending", "Pending review"),
                            ("accepted", "Accepted"),
                            ("rejected", "Rejected"),
                        ],
                        default="not_required",
                        max_length=20,
                    ),
                ),
                ("evidence", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                (
                    "structured_evidence",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "verifier_version",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "started_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification_runs",
                        to="tracker.jobposting",
                    ),
                ),
            ],
            options={
                "verbose_name": "listing verification run",
                "verbose_name_plural": "listing verification runs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["job", "-created_at"],
                        name="verify_job_created_idx",
                    ),
                    models.Index(
                        fields=["status", "-created_at"],
                        name="verify_status_created_idx",
                    ),
                ],
            },
        ),
    ]
