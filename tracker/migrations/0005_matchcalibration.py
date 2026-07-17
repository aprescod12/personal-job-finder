from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tracker", "0004_jobrequirement")]

    operations = [
        migrations.CreateModel(
            name="MatchCalibration",
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
                    "verdict",
                    models.CharField(
                        choices=[
                            ("strong", "Strong match"),
                            ("possible", "Possible match"),
                            ("weak", "Weak match"),
                            ("not_eligible", "Not eligible"),
                            ("unsure", "Unsure / needs more review"),
                        ],
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(auto_now=True)),
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
                "verbose_name": "match calibration",
                "verbose_name_plural": "match calibrations",
                "ordering": ["-reviewed_at"],
            },
        )
    ]
