from django.core.management.base import BaseCommand

from tracker.models import JobCalibration, JobPosting, JobRequirement
from tracker.validation_batch import RESEARCHED_ON, VALIDATION_BATCH, VALIDATION_SOURCE


class Command(BaseCommand):
    help = (
        "Load ten unseen Stage 2 validation jobs without creating human judgments. "
        "Scores remain hidden in the interface until each judgment is saved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the holdout jobs without changing the database.",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "Restore curated fields on jobs originally created by this batch. "
                "Records from another source are never overwritten."
            ),
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            self.stdout.write(f"{VALIDATION_SOURCE} ({RESEARCHED_ON})")
            for index, entry in enumerate(VALIDATION_BATCH, start=1):
                job_data = entry["job"]
                self.stdout.write(
                    f"{index:02d}. {job_data['title']} — {job_data['company']}"
                )
            self.stdout.write("Dry run complete. No database records were changed.")
            return

        created_count = 0
        refreshed_count = 0
        unchanged_count = 0
        skipped_count = 0

        for entry in VALIDATION_BATCH:
            job_data = entry["job"].copy()
            requirements_data = entry["requirements"].copy()
            job_url = job_data.pop("job_url")
            job_data.update(
                {
                    "job_url": job_url,
                    "source": VALIDATION_SOURCE,
                    "next_action": "Record a blind fit and opportunity-lane judgment",
                    "notes": (
                        f"Unseen holdout example curated on {RESEARCHED_ON}. "
                        "Confirm the live posting before applying. The calculated result "
                        "stays hidden until an independent judgment is saved."
                    ),
                }
            )

            job, created = JobPosting.objects.get_or_create(
                job_url=job_url,
                defaults=job_data,
            )
            managed_by_batch = created or job.source == VALIDATION_SOURCE

            if created:
                created_count += 1
            elif not managed_by_batch:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped existing non-validation record: {job.title} at {job.company}"
                    )
                )
                continue
            elif options["refresh"]:
                for field_name, value in job_data.items():
                    setattr(job, field_name, value)
                job.save()
                refreshed_count += 1
            else:
                unchanged_count += 1

            requirements, requirements_created = JobRequirement.objects.get_or_create(job=job)
            if created or requirements_created or options["refresh"]:
                for field_name, value in requirements_data.items():
                    setattr(requirements, field_name, value)
                requirements.full_clean()
                requirements.save()

        reviewed_count = JobCalibration.objects.filter(
            job__source=VALIDATION_SOURCE
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                "Validation batch ready: "
                f"{created_count} created, {refreshed_count} refreshed, "
                f"{unchanged_count} unchanged, {skipped_count} skipped."
            )
        )
        self.stdout.write(
            f"Blind validation progress: {reviewed_count}/{len(VALIDATION_BATCH)} reviewed. "
            "Filter the dashboard to VALIDATION HOLDOUT and review each job before "
            "opening its calculated result."
        )
