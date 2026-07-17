from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement
from .validation_batch import VALIDATION_BATCH, VALIDATION_SOURCE


class ValidationBatchCommandTests(TestCase):
    def test_dry_run_does_not_change_database(self):
        output = StringIO()

        call_command(
            "load_stage2_validation_batch",
            dry_run=True,
            stdout=output,
        )

        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertIn("Dry run complete", output.getvalue())
        self.assertIn("Edison Engineering Development Program", output.getvalue())

    def test_command_creates_ten_jobs_and_no_human_judgments(self):
        call_command("load_stage2_validation_batch", verbosity=0)

        jobs = JobPosting.objects.filter(source=VALIDATION_SOURCE)
        self.assertEqual(jobs.count(), len(VALIDATION_BATCH))
        self.assertEqual(
            JobRequirement.objects.filter(job__source=VALIDATION_SOURCE).count(),
            len(VALIDATION_BATCH),
        )
        self.assertEqual(
            JobCalibration.objects.filter(job__source=VALIDATION_SOURCE).count(),
            0,
        )
        self.assertTrue(all(job.requirements.has_content for job in jobs))

    def test_command_is_idempotent(self):
        call_command("load_stage2_validation_batch", verbosity=0)
        call_command("load_stage2_validation_batch", verbosity=0)

        self.assertEqual(
            JobPosting.objects.filter(source=VALIDATION_SOURCE).count(),
            len(VALIDATION_BATCH),
        )

    def test_refresh_does_not_overwrite_a_non_batch_record(self):
        first = VALIDATION_BATCH[0]["job"]
        manual = JobPosting.objects.create(
            title="Manual opportunity",
            company="Manual Company",
            job_url=first["job_url"],
            source="Manual entry",
        )

        call_command(
            "load_stage2_validation_batch",
            refresh=True,
            verbosity=0,
        )

        manual.refresh_from_db()
        self.assertEqual(manual.title, "Manual opportunity")
        self.assertEqual(manual.source, "Manual entry")
        self.assertFalse(JobRequirement.objects.filter(job=manual).exists())


class BlindValidationInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_stage2_validation_batch", verbosity=0)

    def setUp(self):
        profile = CareerProfile.get_solo()
        profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Medical Device Software Engineer\n"
            "Biomedical Engineer"
        )
        profile.target_industries = "Medical devices\nHealthcare technology"
        profile.skills = (
            "Electrical engineering\nBiomedical engineering\nPython\n"
            "Software development\nTesting and validation\nTechnical documentation"
        )
        profile.education_summary = (
            "B.S. Electrical Engineering. M.S. Biomedical Engineering in progress. "
            "Minor in Computer Science."
        )
        profile.save()
        self.job = JobPosting.objects.filter(source=VALIDATION_SOURCE).first()

    def test_dashboard_filters_to_holdout_and_hides_unreviewed_scores(self):
        response = self.client.get(
            reverse("job_list"),
            {"source": "validation", "review": "unreviewed", "sort": "match_high"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["jobs"]), len(VALIDATION_BATCH))
        self.assertEqual(response.context["selected_sort"], "company")
        self.assertEqual(response.context["blind_jobs"], len(VALIDATION_BATCH))
        self.assertContains(response, "SCORE HIDDEN")
        self.assertContains(response, "BLIND VALIDATION PROTECTED")
        self.assertNotContains(response, "MATCH SCORE")

    def test_job_detail_does_not_reveal_holdout_result(self):
        response = self.client.get(reverse("job_detail", args=[self.job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["blind_validation"])
        self.assertContains(response, "MATCHER RESULT LOCKED")
        self.assertNotContains(response, "VIEW FULL ANALYSIS")

    def test_match_page_hides_result_before_review(self):
        response = self.client.get(reverse("job_match", args=[self.job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["blind_validation"])
        self.assertContains(response, "BLIND FIT REVIEW")
        self.assertContains(response, "RESULT HIDDEN")
        self.assertContains(response, "SAVE AND REVEAL RESULT")
        self.assertNotContains(response, "CATEGORY BREAKDOWN")
        self.assertNotContains(response, "SEMANTIC EVIDENCE")

    def test_saving_judgment_records_snapshot_and_reveals_result(self):
        response = self.client.post(
            reverse("job_match", args=[self.job.id]),
            {
                "human_rating": JobCalibration.HumanRating.POSSIBLE,
                "opportunity_type": JobCalibration.OpportunityType.ADJACENT,
                "notes": "Independent holdout judgment.",
            },
            follow=True,
        )

        calibration = JobCalibration.objects.get(job=self.job)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(calibration.predicted_score)
        self.assertTrue(calibration.predicted_classification)
        self.assertTrue(calibration.predicted_track)
        self.assertFalse(response.context["blind_validation"])
        self.assertContains(response, "Blind validation judgment saved")
        self.assertContains(response, "CATEGORY BREAKDOWN")
        self.assertContains(response, calibration.predicted_classification)

    def test_calibration_report_can_isolate_validation_results(self):
        JobCalibration.objects.create(
            job=self.job,
            human_rating=JobCalibration.HumanRating.POSSIBLE,
            opportunity_type=JobCalibration.OpportunityType.ADJACENT,
            predicted_score=60,
            predicted_classification="POSSIBLE MATCH",
            predicted_track="ADJACENT OPPORTUNITY",
        )
        manual_job = JobPosting.objects.create(
            title="Manual Job",
            company="Manual Company",
            source="Manual entry",
        )
        JobCalibration.objects.create(
            job=manual_job,
            human_rating=JobCalibration.HumanRating.WEAK,
            opportunity_type=JobCalibration.OpportunityType.OUTSIDE,
            predicted_score=30,
            predicted_classification="WEAK MATCH",
            predicted_track="OUTSIDE PRIORITY",
        )

        response = self.client.get(
            reverse("calibration_report"),
            {"scope": "validation"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_scope"], "validation")
        self.assertEqual(response.context["report"].reviewed_count, 1)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0].job, self.job)
        self.assertEqual(response.context["validation_reviewed"], 1)
        self.assertEqual(response.context["validation_total"], len(VALIDATION_BATCH))

    def test_invalid_source_and_scope_filters_fall_back_safely(self):
        dashboard = self.client.get(reverse("job_list"), {"source": "invalid"})
        report = self.client.get(
            reverse("calibration_report"),
            {"scope": "invalid"},
        )

        self.assertEqual(dashboard.context["selected_source"], "")
        self.assertEqual(report.context["selected_scope"], "")
