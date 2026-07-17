from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .management.commands.load_stage2_calibration_batch import (
    CALIBRATION_BATCH,
    SOURCE_NAME,
)
from .models import JobCalibration, JobPosting, JobRequirement


class CalibrationBatchCommandTests(TestCase):
    def test_dry_run_does_not_create_records(self):
        output = StringIO()

        call_command(
            "load_stage2_calibration_batch",
            dry_run=True,
            stdout=output,
        )

        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertIn("Dry run complete", output.getvalue())
        self.assertIn("Product Safety Engineer", output.getvalue())

    def test_command_creates_ten_jobs_with_requirements_but_no_judgments(self):
        call_command("load_stage2_calibration_batch", verbosity=0)

        imported_jobs = JobPosting.objects.filter(source=SOURCE_NAME)
        self.assertEqual(imported_jobs.count(), len(CALIBRATION_BATCH))
        self.assertEqual(JobRequirement.objects.count(), len(CALIBRATION_BATCH))
        self.assertEqual(JobCalibration.objects.count(), 0)
        self.assertTrue(
            all(job.requirements.has_content for job in imported_jobs)
        )

    def test_command_is_idempotent(self):
        call_command("load_stage2_calibration_batch", verbosity=0)
        call_command("load_stage2_calibration_batch", verbosity=0)

        self.assertEqual(
            JobPosting.objects.filter(source=SOURCE_NAME).count(),
            len(CALIBRATION_BATCH),
        )
        self.assertEqual(JobRequirement.objects.count(), len(CALIBRATION_BATCH))

    def test_refresh_restores_batch_managed_fields(self):
        call_command("load_stage2_calibration_batch", verbosity=0)
        job = JobPosting.objects.get(
            title="Product Safety Engineer",
            company="Stryker",
        )
        job.company = "Changed Company"
        job.save()

        call_command("load_stage2_calibration_batch", verbosity=0)
        job.refresh_from_db()
        self.assertEqual(job.company, "Changed Company")

        call_command(
            "load_stage2_calibration_batch",
            refresh=True,
            verbosity=0,
        )
        job.refresh_from_db()
        self.assertEqual(job.company, "Stryker")

    def test_refresh_does_not_overwrite_non_batch_record(self):
        first_entry = CALIBRATION_BATCH[0]["job"]
        existing = JobPosting.objects.create(
            title="My manually entered role",
            company="Manual Company",
            job_url=first_entry["job_url"],
            source="Manual entry",
        )

        call_command(
            "load_stage2_calibration_batch",
            refresh=True,
            verbosity=0,
        )

        existing.refresh_from_db()
        self.assertEqual(existing.title, "My manually entered role")
        self.assertEqual(existing.source, "Manual entry")
        self.assertFalse(JobRequirement.objects.filter(job=existing).exists())

    def test_batch_contains_explicit_authorization_and_experience_checks(self):
        call_command("load_stage2_calibration_batch", verbosity=0)

        bd_program = JobPosting.objects.get(
            title="BD Quality Engineering Development Program Associate"
        )
        philips = JobPosting.objects.get(title="Quality Engineer I", company="Philips")
        embedded = JobPosting.objects.get(
            title="Staff Embedded Software & Controls Engineer"
        )

        self.assertIn("cannot sponsor", bd_program.requirements.hard_disqualifiers)
        self.assertIn("visa sponsorship", philips.requirements.hard_disqualifiers)
        self.assertEqual(embedded.requirements.minimum_years_experience, 4)
