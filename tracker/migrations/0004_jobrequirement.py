from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tracker", "0003_careerprofile")]

    operations = [
        migrations.CreateModel(
            name="JobRequirement",
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
                ("role_family", models.CharField(blank=True, max_length=200)),
                (
                    "seniority_level",
                    models.CharField(
                        choices=[
                            ("unknown", "Not specified"),
                            ("internship", "Internship / student"),
                            ("entry_level", "Entry level"),
                            ("early_career", "Early career"),
                            ("mid_level", "Mid level"),
                            ("senior", "Senior"),
                            ("lead_manager", "Lead / manager"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                ("industry", models.CharField(blank=True, max_length=200)),
                (
                    "required_skills",
                    models.TextField(
                        blank=True,
                        help_text="Enter one required skill per line.",
                    ),
                ),
                (
                    "preferred_skills",
                    models.TextField(
                        blank=True,
                        help_text="Enter one preferred skill per line.",
                    ),
                ),
                (
                    "required_education",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Enter one acceptable required degree or field per line."
                        ),
                    ),
                ),
                (
                    "preferred_education",
                    models.TextField(
                        blank=True,
                        help_text="Enter one preferred degree or field per line.",
                    ),
                ),
                (
                    "minimum_years_experience",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "maximum_years_experience",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "responsibilities",
                    models.TextField(
                        blank=True,
                        help_text="Enter one responsibility per line.",
                    ),
                ),
                (
                    "certifications",
                    models.TextField(
                        blank=True,
                        help_text="Enter one certification or standard per line.",
                    ),
                ),
                (
                    "work_authorization_requirements",
                    models.TextField(blank=True),
                ),
                (
                    "hard_disqualifiers",
                    models.TextField(
                        blank=True,
                        help_text="Enter one explicit blocker per line.",
                    ),
                ),
                ("requirement_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "job",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requirements",
                        to="tracker.jobposting",
                    ),
                ),
            ],
            options={
                "verbose_name": "job requirement set",
                "verbose_name_plural": "job requirement sets",
            },
        )
    ]
