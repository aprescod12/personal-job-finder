from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .evaluation_models import JobEvaluationRun
from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement
from .services.job_evaluations import (
    evaluate_all_jobs,
    evaluate_job,
    latest_evaluation,
)


class JobEvaluationServiceTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = "Software Engineer"
        self.profile.target_industries = "Medical devices"
        self.profile.skills = ""
        self.profile.education_summary = "B.S. Electrical Engineering"
        self.profile.preferred_locations = "Philadelphia, PA"
        self.profile.save()

        self.job = JobPosting.objects.create(
            title="Software Engineer I",
            company="Medical Device Company",
            location="Philadelphia, PA",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
        )
        self.requirements = JobRequirement.objects.create(
            job=self.job,
            role_family="Software Engineer",
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry="Medical devices",
            required_skills="Python",
            required_education="Electrical Engineering",
        )

    def test_first_evaluation_persists_current_audit_run(self):
        run = evaluate_job(self.job)

        self.assertTrue(run.is_current)
        self.assertEqual(run.job, self.job)
        self.assertEqual(run.profile, self.profile)
        self.assertEqual(run.matcher_version, "2.3-controlled-semantic")
        self.assertIsNone(run.previous_run)
        self.assertIsNone(run.score_delta)
        self.assertIn("direct_matches", run.result_data)
        self.assertIn("gaps", run.result_data)
        self.assertTrue(run.profile_fingerprint)
        self.assertTrue(run.job_fingerprint)

    def test_manual_profile_change_marks_current_evaluation_stale(self):
        run = evaluate_job(self.job)

        self.profile.skills = "Python"
        self.profile.save()

        run.refresh_from_db()
        self.assertFalse(run.is_current)
        self.assertIn("Manual career profile changed", run.stale_reasons)

    def test_requirement_change_marks_current_evaluation_stale(self):
        run = evaluate_job(self.job)

        self.requirements.required_skills = "Python\nC++"
        self.requirements.save()

        run.refresh_from_db()
        self.assertFalse(run.is_current)
        self.assertIn("Structured job requirements changed", run.stale_reasons)

    def test_reevaluation_preserves_history_and_explains_resolved_gap(self):
        first = evaluate_job(self.job)
        self.assertTrue(
            any(
                item["requirement"] == "Python"
                for item in first.result_data["gaps"]
            )
        )

        self.profile.skills = "Python"
        self.profile.save()
        second = evaluate_job(self.job)

        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(second.previous_run, first)
        self.assertEqual(JobEvaluationRun.objects.filter(job=self.job).count(), 2)
        self.assertTrue(
            any(
                item["requirement"] == "Python"
                for item in second.comparison_data["resolved_gaps"]
            )
        )
        self.assertTrue(
            any(
                item["requirement"] == "Python"
                for item in second.comparison_data["added_direct"]
            )
        )

    def test_matcher_version_drift_is_detected_without_overwriting_history(self):
        run = evaluate_job(self.job)

        with patch("tracker.services.job_evaluations.MATCHER_VERSION", "future-v9"):
            latest = latest_evaluation(self.job, refresh=True)

        run.refresh_from_db()
        self.assertEqual(latest.id, run.id)
        self.assertFalse(run.is_current)
        self.assertIn("Matcher version changed", run.stale_reasons)

    def test_bulk_evaluation_creates_one_current_run_per_job(self):
        second_job = JobPosting.objects.create(
            title="Test Engineer",
            company="Second Company",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
        )
        JobRequirement.objects.create(
            job=second_job,
            role_family="Test Engineer",
            required_skills="MATLAB",
        )

        runs = evaluate_all_jobs()

        self.assertEqual(len(runs), 2)
        self.assertEqual(JobEvaluationRun.objects.filter(is_current=True).count(), 2)
        self.assertFalse(
            JobEvaluationRun.objects.exclude(
                trigger=JobEvaluationRun.Trigger.BULK
            ).exists()
        )

    def test_reevaluation_does_not_modify_saved_calibration_snapshot(self):
        calibration = JobCalibration.objects.create(
            job=self.job,
            human_rating=JobCalibration.HumanRating.POSSIBLE,
            opportunity_type=JobCalibration.OpportunityType.ADJACENT,
            predicted_score=42,
            predicted_classification="WEAK MATCH",
            predicted_track="OUTSIDE PRIORITY",
        )

        evaluate_job(self.job)
        self.profile.skills = "Python"
        self.profile.save()
        evaluate_job(self.job)

        calibration.refresh_from_db()
        self.assertEqual(calibration.predicted_score, 42)
        self.assertEqual(calibration.predicted_classification, "WEAK MATCH")
        self.assertEqual(calibration.predicted_track, "OUTSIDE PRIORITY")


class JobEvaluationViewTests(JobEvaluationServiceTests):
    def test_reevaluation_endpoints_require_post(self):
        response = self.client.get(reverse("reevaluate_job", args=[self.job.id]))
        self.assertEqual(response.status_code, 405)

        response = self.client.get(reverse("reevaluate_all_jobs"))
        self.assertEqual(response.status_code, 405)

    def test_match_page_exposes_baseline_then_current_status(self):
        response = self.client.get(reverse("job_match", args=[self.job.id]))
        self.assertContains(response, "NO SAVED BASELINE")
        self.assertContains(response, "SAVE BASELINE")

        response = self.client.post(reverse("reevaluate_job", args=[self.job.id]))
        self.assertRedirects(response, reverse("job_match", args=[self.job.id]))

        response = self.client.get(reverse("job_match", args=[self.job.id]))
        self.assertContains(response, "PERSISTED EVALUATION")
        self.assertContains(response, "CURRENT")
        self.assertContains(response, "VIEW HISTORY")

    def test_stale_status_appears_after_profile_change(self):
        evaluate_job(self.job)
        self.profile.skills = "Python"
        self.profile.save()

        response = self.client.get(reverse("job_match", args=[self.job.id]))

        self.assertContains(response, "STALE")
        self.assertContains(response, "Manual career profile changed")
        self.assertContains(response, "REEVALUATE JOB")

    def test_dashboard_bulk_action_and_status_counts(self):
        response = self.client.get(reverse("job_list"))
        self.assertContains(response, "REEVALUATE ALL JOBS")
        self.assertContains(response, "NO SAVED BASELINE")

        response = self.client.post(reverse("reevaluate_all_jobs"))
        self.assertRedirects(response, reverse("job_list"))

        response = self.client.get(reverse("job_list"))
        self.assertContains(response, "CURRENT ·")
        self.assertContains(response, "0 JOBS NEED REEVALUATION")

    def test_history_page_preserves_multiple_runs_and_deltas(self):
        first = evaluate_job(self.job)
        self.profile.skills = "Python"
        self.profile.save()
        second = evaluate_job(self.job)

        response = self.client.get(reverse("evaluation_history", args=[self.job.id]))

        self.assertContains(response, "EVALUATION HISTORY")
        self.assertContains(response, "CURRENT PERSISTED RESULT")
        self.assertContains(response, "RESOLVED GAPS")
        self.assertContains(response, "Python")
        self.assertContains(response, first.matcher_version)
        self.assertContains(response, str(second.score))
