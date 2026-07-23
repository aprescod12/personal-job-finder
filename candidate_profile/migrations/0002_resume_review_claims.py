import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("candidate_profile", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResumeExtractionReview",
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
                ("source_sha256", models.CharField(max_length=64)),
                ("source_label", models.CharField(max_length=120)),
                ("source_filename", models.CharField(max_length=255)),
                ("provider_key", models.CharField(max_length=100)),
                ("provider_label", models.CharField(max_length=160)),
                ("provider_version", models.CharField(max_length=120)),
                ("provider_mode", models.CharField(max_length=40)),
                ("document_parser_key", models.CharField(max_length=100)),
                ("document_parser_version", models.CharField(max_length=120)),
                ("orchestration", models.JSONField(blank=True, default=dict)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("document_warnings", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending decisions"),
                            ("in_review", "Review in progress"),
                            ("completed", "Completed"),
                            ("discarded", "Discarded"),
                            ("stale", "Superseded by newer extraction"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resume_extraction_reviews",
                        to="tracker.careerprofile",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extraction_reviews",
                        to="candidate_profile.resumesource",
                    ),
                ),
            ],
            options={
                "verbose_name": "resume extraction review",
                "verbose_name_plural": "resume extraction reviews",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ResumeReviewClaim",
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
                ("claim_key", models.CharField(max_length=180)),
                ("field_path", models.CharField(max_length=255)),
                (
                    "section",
                    models.CharField(
                        choices=[
                            ("identity", "Identity"),
                            ("summary", "Professional summary"),
                            ("education", "Education"),
                            ("experience", "Experience"),
                            ("projects", "Projects"),
                            ("skills", "Skills"),
                            ("certifications", "Certifications"),
                            ("leadership", "Leadership"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "claim_type",
                    models.CharField(
                        choices=[
                            ("scalar", "Single value"),
                            ("list_item", "List item"),
                            ("entry", "Structured entry"),
                        ],
                        max_length=20,
                    ),
                ),
                ("position", models.PositiveIntegerField(default=0)),
                ("extracted_value", models.JSONField()),
                ("reviewed_value", models.JSONField()),
                ("source_text", models.TextField(blank=True)),
                ("evidence_note", models.TextField(blank=True)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approve"),
                            ("rejected", "Reject"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="claims",
                        to="candidate_profile.resumeextractionreview",
                    ),
                ),
            ],
            options={
                "verbose_name": "resume review claim",
                "verbose_name_plural": "resume review claims",
                "ordering": ["section", "position", "id"],
            },
        ),
        migrations.CreateModel(
            name="CandidateProfileClaim",
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
                    "section",
                    models.CharField(
                        choices=[
                            ("identity", "Identity"),
                            ("summary", "Professional summary"),
                            ("education", "Education"),
                            ("experience", "Experience"),
                            ("projects", "Projects"),
                            ("skills", "Skills"),
                            ("certifications", "Certifications"),
                            ("leadership", "Leadership"),
                        ],
                        max_length=30,
                    ),
                ),
                ("claim_key", models.CharField(max_length=180)),
                ("field_path", models.CharField(max_length=255)),
                ("semantic_key", models.CharField(max_length=64)),
                ("value", models.JSONField()),
                ("source_text", models.TextField(blank=True)),
                ("evidence_note", models.TextField(blank=True)),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_label", models.CharField(max_length=120)),
                ("source_filename", models.CharField(max_length=255)),
                ("provider_key", models.CharField(max_length=100)),
                ("provider_version", models.CharField(max_length=120)),
                ("provider_mode", models.CharField(max_length=40)),
                ("document_parser_key", models.CharField(max_length=100)),
                ("document_parser_version", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("approved_at", models.DateTimeField(auto_now_add=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approved_resume_claims",
                        to="tracker.careerprofile",
                    ),
                ),
                (
                    "review_claim",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="candidate_profile_claim",
                        to="candidate_profile.resumereviewclaim",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_candidate_claims",
                        to="candidate_profile.resumesource",
                    ),
                ),
            ],
            options={
                "verbose_name": "approved candidate profile claim",
                "verbose_name_plural": "approved candidate profile claims",
                "ordering": ["section", "approved_at", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="resumereviewclaim",
            constraint=models.UniqueConstraint(
                fields=("review", "claim_key"),
                name="unique_claim_key_per_review",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateprofileclaim",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("profile", "semantic_key"),
                name="active_candidate_claim_key",
            ),
        ),
        migrations.AddIndex(
            model_name="resumeextractionreview",
            index=models.Index(
                fields=["profile", "status", "-created_at"],
                name="resume_review_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resumeextractionreview",
            index=models.Index(
                fields=["source", "-created_at"],
                name="resume_review_source_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resumereviewclaim",
            index=models.Index(
                fields=["review", "section", "position"],
                name="review_claim_section_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resumereviewclaim",
            index=models.Index(
                fields=["decision", "applied_at"],
                name="review_claim_decision_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofileclaim",
            index=models.Index(
                fields=["profile", "is_active", "section"],
                name="candidate_claim_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofileclaim",
            index=models.Index(
                fields=["source_sha256", "approved_at"],
                name="candidate_claim_source_idx",
            ),
        ),
    ]
