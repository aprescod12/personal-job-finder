import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tracker", "0007_listingverificationrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobExtractionRun",
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
                ("source_url", models.URLField(blank=True, max_length=1000)),
                (
                    "normalized_source_url",
                    models.CharField(blank=True, max_length=1000),
                ),
                ("source_label", models.CharField(blank=True, max_length=100)),
                ("raw_text", models.TextField()),
                ("raw_text_sha256", models.CharField(max_length=64)),
                ("role_identity_sha256", models.CharField(blank=True, max_length=64)),
                ("provider_key", models.CharField(blank=True, max_length=100)),
                ("provider_label", models.CharField(blank=True, max_length=200)),
                ("provider_version", models.CharField(blank=True, max_length=100)),
                ("extraction_mode", models.CharField(blank=True, max_length=30)),
                ("orchestration_status", models.CharField(blank=True, max_length=50)),
                ("fallback_used", models.BooleanField(default=False)),
                ("manual_review_required", models.BooleanField(default=False)),
                ("total_elapsed_ms", models.PositiveIntegerField(default=0)),
                ("attempts", models.JSONField(blank=True, default=list)),
                ("evidence", models.JSONField(blank=True, default=list)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("extracted_payload", models.JSONField(blank=True, default=dict)),
                ("reviewed_payload", models.JSONField(blank=True, default=dict)),
                ("duplicate_candidates", models.JSONField(blank=True, default=list)),
                ("duplicate_override", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extraction_runs",
                        to="tracker.jobposting",
                    ),
                ),
            ],
            options={
                "verbose_name": "job extraction run",
                "verbose_name_plural": "job extraction runs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="jobextractionrun",
            index=models.Index(
                fields=["job", "-created_at"],
                name="intake_job_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobextractionrun",
            index=models.Index(
                fields=["raw_text_sha256"],
                name="intake_text_hash_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobextractionrun",
            index=models.Index(
                fields=["normalized_source_url"],
                name="intake_url_idx",
            ),
        ),
    ]
