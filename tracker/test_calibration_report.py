from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement
from .services import strategy_matching
from .services.calibration_reporting import TRACK_TO_OPPORTUNITY


class CalibrationReportTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Medical Device Software Engineer\n"
            "Biomedical Engineer"
        )
        self.profile.target_industries = (
            "Medical devices\nHealthcare technology"
        )
        self.profile.skills = (
            "Electrical engineering\n"
            "Biomedical engineering\n"
            "Testing and validation\n"
            "Technical documentation\n"
            "Python\nSoftware development"
        )
        self.profile.education_summary = (
            "B.S. Electrical Engineering. M.S. Biomedical Engineering in progress."
        )
        self.profile.preferred_employment_type = (
            JobPosting.EmploymentType.FULL_TIME
        )
        self.profile.save()

    def make_reviewed_job(
        self,
        *,
        title="Product Safety Engineer",
        role_family="Product Safety Engineering",
        industry="Medical devices",
        human_rating=None,
        opportunity_type=None,
        saved_classification=None,
        saved_track=None,
        saved_score=None,
    ):
        job = JobPosting.objects.create(
            title=title,
            company=f"{title} Company",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
        )
        requirements = JobRequirement.objects.create(
            job=job,
            role_family=role_family,
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry=industry,
            required_skills=(
                "Testing and validation\nTechnical documentation\nPython"
            ),
            required_education=(
                "Electrical Engineering\nBiomedical Engineering"
            ),
            minimum_years_experience=0,
            maximum_years_experience=2,
        )
        current = strategy_matching.analyze_job_match(
            self.profile,
            job,
            requirements,
        )
        current_rating = JobCalibration.PREDICTED_RATING_MAP.get(
            current.classification,
            JobCalibration.HumanRating.POSSIBLE,
        )
        current_lane = TRACK_TO_OPPORTUNITY.get(
            current.track,
            JobCalibration.OpportunityType.UNSURE,
        )

        calibration = JobCalibration.objects.create(
            job=job,
            human_rating=human_rating or current_rating,
            opportunity_type=opportunity_type or current_lane,
            notes="Independent human review.",
            predicted_score=(
                current.score if saved_score is None else saved_score
            ),
            predicted_classification=(
                current.classification
                if saved_classification is None
                else saved_classification
            ),
            predicted_track=(
                current.track if saved_track is None else saved_track
            ),
        )
        return job, requirements, calibration, current

    def test_empty_report_explains_how_to_begin(self):
        response = self.client.get(reverse("calibration_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NO CALIBRATIONS YET")
        self.assertEqual(response.context["report"].reviewed_count, 0)

    def test_report_calculates_current_fit_and_lane_agreement(self):
        job, _, _, current = self.make_reviewed_job()

        response = self.client.get(reverse("calibration_report"))
        report = response.context["report"]
        row = response.context["rows"][0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.job, job)
        self.assertEqual(row.rating_status, "ALIGNED")
        self.assertEqual(row.lane_status, "ALIGNED")
        self.assertEqual(report.rating_agreement_percent, 100)
        self.assertEqual(report.lane_agreement_percent, 100)
        self.assertEqual(row.current_result.score, current.score)
        self.assertContains(response, "CURRENT MATCHER")

    def test_report_marks_a_newly_aligned_result_as_improved(self):
        _, _, calibration, current = self.make_reviewed_job()
        current_rating = JobCalibration.PREDICTED_RATING_MAP[current.classification]
        different_saved = (
            "WEAK MATCH"
            if current_rating != JobCalibration.HumanRating.WEAK
            else "POSSIBLE MATCH"
        )
        calibration.predicted_classification = different_saved
        calibration.predicted_score = max(0, current.score - 20)
        calibration.save()

        response = self.client.get(reverse("calibration_report"))
        row = response.context["rows"][0]

        self.assertEqual(row.rating_status, "ALIGNED")
        self.assertEqual(row.change_status, "IMPROVED")
        self.assertTrue(row.strategy_changed)
        self.assertEqual(response.context["report"].improved_count, 1)

    def test_attention_filter_only_shows_current_disagreements(self):
        aligned_job, _, _, _ = self.make_reviewed_job(
            title="Product Safety Engineer",
        )
        review_job, _, calibration, current = self.make_reviewed_job(
            title="Embedded Software Engineer",
            role_family="Embedded Software Engineering",
        )
        current_rating = JobCalibration.PREDICTED_RATING_MAP[current.classification]
        calibration.human_rating = (
            JobCalibration.HumanRating.NOT_ELIGIBLE
            if current_rating != JobCalibration.HumanRating.NOT_ELIGIBLE
            else JobCalibration.HumanRating.STRONG
        )
        calibration.save()

        response = self.client.get(
            reverse("calibration_report"),
            {"status": "attention"},
        )
        jobs = [row.job for row in response.context["rows"]]

        self.assertIn(review_job, jobs)
        self.assertNotIn(aligned_job, jobs)

    def test_report_does_not_replace_saved_matcher_snapshot(self):
        _, _, calibration, _ = self.make_reviewed_job(
            saved_classification="WEAK MATCH",
            saved_track="OUTSIDE PRIORITY",
            saved_score=31,
        )

        self.client.get(reverse("calibration_report"))
        calibration.refresh_from_db()

        self.assertEqual(calibration.predicted_score, 31)
        self.assertEqual(calibration.predicted_classification, "WEAK MATCH")
        self.assertEqual(calibration.predicted_track, "OUTSIDE PRIORITY")

    def test_invalid_filter_falls_back_to_all_rows(self):
        self.make_reviewed_job()

        response = self.client.get(
            reverse("calibration_report"),
            {"status": "unsupported"},
        )

        self.assertEqual(response.context["selected_filter"], "")
        self.assertEqual(len(response.context["rows"]), 1)
