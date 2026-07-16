from django.db import migrations, models


def seed_amiri_profile(apps, schema_editor):
    CareerProfile = apps.get_model("tracker", "CareerProfile")
    CareerProfile.objects.update_or_create(
        pk=1,
        defaults={
            "full_name": "Amiri Prescod",
            "professional_headline": (
                "Electrical Engineer | M.S. Biomedical Engineering Candidate | "
                "Computer Science Minor"
            ),
            "education_summary": (
                "B.S. in Electrical Engineering from Villanova University.\n"
                "M.S. in Biomedical Engineering in progress.\n"
                "Minor in Computer Science."
            ),
            "target_roles": (
                "Biomedical Engineer\n"
                "Medical Device Engineer\n"
                "Systems Engineer\n"
                "Test Engineer\n"
                "Quality Engineer\n"
                "Validation Engineer\n"
                "Medical Device Software Engineer"
            ),
            "target_industries": (
                "Medical devices\n"
                "Healthcare technology\n"
                "Biomedical engineering"
            ),
            "skills": (
                "Electrical engineering\n"
                "Biomedical engineering\n"
                "Computer science\n"
                "Python\n"
                "Django\n"
                "Software development\n"
                "Technical testing"
            ),
            "experience_level": "entry_level",
            "preferred_work_arrangement": "flexible",
            "preferred_employment_type": "full_time",
            "priorities": (
                "Entry-level roles with hands-on engineering responsibility\n"
                "Medical-device or healthcare impact\n"
                "Opportunities to learn regulated product development"
            ),
        },
    )


def remove_seeded_profile(apps, schema_editor):
    CareerProfile = apps.get_model("tracker", "CareerProfile")
    CareerProfile.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0002_alter_jobposting_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CareerProfile",
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
                    "full_name",
                    models.CharField(default="Amiri Prescod", max_length=200),
                ),
                (
                    "professional_headline",
                    models.CharField(blank=True, max_length=300),
                ),
                ("education_summary", models.TextField(blank=True)),
                (
                    "target_roles",
                    models.TextField(
                        blank=True,
                        help_text="Enter one target role per line.",
                    ),
                ),
                (
                    "target_industries",
                    models.TextField(
                        blank=True,
                        help_text="Enter one preferred industry per line.",
                    ),
                ),
                (
                    "skills",
                    models.TextField(
                        blank=True,
                        help_text="Enter one skill per line.",
                    ),
                ),
                (
                    "experience_level",
                    models.CharField(
                        choices=[
                            ("entry_level", "Entry level"),
                            ("early_career", "Early career (1–3 years)"),
                            ("mid_level", "Mid level"),
                            ("senior", "Senior"),
                        ],
                        default="entry_level",
                        max_length=20,
                    ),
                ),
                (
                    "preferred_locations",
                    models.TextField(
                        blank=True,
                        help_text="Enter one acceptable location per line.",
                    ),
                ),
                (
                    "preferred_work_arrangement",
                    models.CharField(
                        choices=[
                            ("flexible", "Flexible"),
                            ("onsite", "On-site"),
                            ("hybrid", "Hybrid"),
                            ("remote", "Remote"),
                        ],
                        default="flexible",
                        max_length=20,
                    ),
                ),
                (
                    "preferred_employment_type",
                    models.CharField(
                        choices=[
                            ("full_time", "Full-time"),
                            ("part_time", "Part-time"),
                            ("contract", "Contract"),
                            ("internship", "Internship"),
                            ("temporary", "Temporary"),
                            ("unknown", "Unknown"),
                        ],
                        default="full_time",
                        max_length=20,
                    ),
                ),
                (
                    "minimum_salary",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Optional minimum annual salary in U.S. dollars.",
                        null=True,
                    ),
                ),
                (
                    "work_authorization",
                    models.CharField(blank=True, max_length=300),
                ),
                (
                    "priorities",
                    models.TextField(
                        blank=True,
                        help_text="Enter one priority per line.",
                    ),
                ),
                (
                    "deal_breakers",
                    models.TextField(
                        blank=True,
                        help_text="Enter one non-negotiable or disqualifier per line.",
                    ),
                ),
                ("additional_context", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "career profile",
                "verbose_name_plural": "career profile",
            },
        ),
        migrations.RunPython(seed_amiri_profile, remove_seeded_profile),
    ]
