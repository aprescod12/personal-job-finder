from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tracker", "0004_jobrequirement")]

    operations = [
        migrations.CreateModel(
            name="JobCalibration",
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
                    "human_rating",
                    models.CharField(
                        choices=[
                            ("strong", "Strong match"),
                            ("possible", "Possible match"),
                            ("weak", "Weak match"),
                            ("not_eligible", "Not eligible"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "opportunity_type",
                    models.CharField(
                        choices=[
                            ("priority", "Priority role"),
                            ("adjacent", "Adjacent opportunity"),
                            ("outside", "Outside current priority"),
                            ("unsure", "Unsure"),
                        ],
                        default="unsure",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "predicted_score",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "predicted_classification",
                    models.CharField(blank=True, max_length=40),
                ),
                (
                    "predicted_track",
                    models.CharField(blank=True, max_length=40),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "job",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="calibration",
                        to="tracker.jobposting",
                    ),
                ),
            ],
            options={
                "verbose_name": "job calibration",
                "verbose_name_plural": "job calibrations",
                "ordering": ["-updated_at"],
            },
        )
    ]
