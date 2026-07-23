import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("candidate_profile", "0003_candidate_profile_snapshots"),
        ("tracker", "0007_listingverificationrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobEvaluationRun",
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
                            ("manual", "Manual job reevaluation"),
                            ("bulk", "Bulk job reevaluation"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("matcher_version", models.CharField(max_length=120)),
                ("candidate_snapshot_version", models.PositiveIntegerField(blank=True, null=True)),
                ("candidate_snapshot_composition_version", models.CharField(blank=True, max_length=120)),
                ("profile_fingerprint", models.CharField(max_length=64)),
                ("job_fingerprint", models.CharField(max_length=64)),
                ("has_requirements", models.BooleanField(default=False)),
                ("score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("classification", models.CharField(blank=True, max_length=40)),
                ("track", models.CharField(blank=True, max_length=40)),
                ("evidence_coverage", models.PositiveSmallIntegerField(default=0)),
                ("result_data", models.JSONField(default=dict)),
                ("comparison_data", models.JSONField(blank=True, default=dict)),
                ("is_current", models.BooleanField(default=True)),
                ("stale_reasons", models.JSONField(blank=True, default=list)),
                ("evaluated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "candidate_snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="job_evaluation_runs",
                        to="candidate_profile.candidateprofilesnapshot",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluation_runs",
                        to="tracker.jobposting",
                    ),
                ),
                (
                    "previous_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="next_runs",
                        to="tracker.jobevaluationrun",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="job_evaluation_runs",
                        to="tracker.careerprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "job evaluation run",
                "verbose_name_plural": "job evaluation runs",
                "ordering": ["-evaluated_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="jobevaluationrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_current", True)),
                fields=("job",),
                name="one_current_job_evaluation",
            ),
        ),
        migrations.AddIndex(
            model_name="jobevaluationrun",
            index=models.Index(
                fields=["job", "-evaluated_at"],
                name="job_eval_history_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobevaluationrun",
            index=models.Index(
                fields=["is_current", "-evaluated_at"],
                name="job_eval_current_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobevaluationrun",
            index=models.Index(
                fields=["candidate_snapshot", "-evaluated_at"],
                name="job_eval_snapshot_idx",
            ),
        ),
    ]
