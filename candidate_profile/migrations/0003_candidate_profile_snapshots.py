import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("candidate_profile", "0002_resume_review_claims"),
    ]

    operations = [
        migrations.CreateModel(
            name="CandidateProfileSnapshot",
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
                ("version", models.PositiveIntegerField()),
                ("composition_version", models.CharField(max_length=120)),
                ("fingerprint", models.CharField(max_length=64)),
                ("data", models.JSONField(default=dict)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("source_claim_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft preview"),
                            ("active", "Active for matching"),
                            ("archived", "Archived"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="candidate_profile_snapshots",
                        to="tracker.careerprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "candidate profile snapshot",
                "verbose_name_plural": "candidate profile snapshots",
                "ordering": ["-version"],
            },
        ),
        migrations.CreateModel(
            name="CandidateProfileSnapshotClaim",
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
                ("position", models.PositiveIntegerField(default=0)),
                ("section", models.CharField(max_length=30)),
                ("field_path", models.CharField(max_length=255)),
                ("semantic_key", models.CharField(max_length=64)),
                ("value", models.JSONField()),
                (
                    "candidate_claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="snapshot_links",
                        to="candidate_profile.candidateprofileclaim",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_claim_links",
                        to="candidate_profile.candidateprofilesnapshot",
                    ),
                ),
            ],
            options={
                "verbose_name": "candidate profile snapshot claim",
                "verbose_name_plural": "candidate profile snapshot claims",
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="candidateprofilesnapshot",
            constraint=models.UniqueConstraint(
                fields=("profile", "version"),
                name="unique_candidate_snapshot_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateprofilesnapshot",
            constraint=models.UniqueConstraint(
                fields=("profile", "fingerprint"),
                name="unique_candidate_snapshot_fingerprint",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateprofilesnapshot",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "active")),
                fields=("profile",),
                name="one_active_candidate_snapshot",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofilesnapshot",
            index=models.Index(
                fields=["profile", "status", "-version"],
                name="candidate_snapshot_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofilesnapshot",
            index=models.Index(
                fields=["fingerprint"],
                name="candidate_snapshot_fingerprint_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateprofilesnapshotclaim",
            constraint=models.UniqueConstraint(
                fields=("snapshot", "candidate_claim"),
                name="unique_claim_per_candidate_snapshot",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofilesnapshotclaim",
            index=models.Index(
                fields=["snapshot", "section", "position"],
                name="snapshot_claim_section_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="candidateprofilesnapshotclaim",
            index=models.Index(
                fields=["candidate_claim"],
                name="snapshot_claim_source_idx",
            ),
        ),
    ]
