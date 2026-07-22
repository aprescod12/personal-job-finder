import candidate_profile.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tracker", "0007_listingverificationrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResumeSource",
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
                    "document",
                    models.FileField(upload_to=candidate_profile.models.resume_upload_path),
                ),
                ("original_filename", models.CharField(max_length=255)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("content_type", models.CharField(blank=True, max_length=150)),
                ("file_size", models.PositiveIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=False)),
                (
                    "review_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("reviewed", "Reviewed"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resume_sources",
                        to="tracker.careerprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "resume source",
                "verbose_name_plural": "resume sources",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="resumesource",
            constraint=models.UniqueConstraint(
                fields=("profile", "sha256"),
                name="unique_resume_content_per_profile",
            ),
        ),
        migrations.AddConstraint(
            model_name="resumesource",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("profile",),
                name="one_active_resume_per_profile",
            ),
        ),
        migrations.AddIndex(
            model_name="resumesource",
            index=models.Index(
                fields=["profile", "-created_at"],
                name="resume_profile_created_idx",
            ),
        ),
    ]
