from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement


class CalibrationModelTests(TestCase):
    def test_agreement_status_maps_matcher_classification_to_human_judgment(self):
        job = JobPosting.objects.create(
            title="Biomedical Engineer",
            company="Example Medical",
        )
        calibration = JobCalibration(
            job=job,
            human_rating=JobCalibration.HumanRating.STRONG,
            predicted_classification="GOOD MATCH",
        )

        self.assertEqual(calibration.predicted_human_rating, "strong")
        self.assertEqual(calibration.agreement_status, "ALIGNED")
        self.assertIn("agrees", calibration.agreement_label)

    def test_low_confidence_result_is_marked_as_needing_evidence(self):
        job = JobPosting.objects.create(
            title="Engineer",
            company="Example",
        )
        calibration = JobCalibration(
            job=job,
            human_rating=JobCalibration.HumanRating.POSSIBLE,
            predicted_classification="LOW CONFIDENCE",
        )

        self.assertEqual(calibration.agreement_status, "NEEDS EVIDENCE")


class MatchDashboardAndCalibrationTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.preferred_locations = "Philadelphia, PA"
        self.profile.save()

        self.strong_job = JobPosting.objects.create(
            title="Biomedical Engineer",
            company="Alpha Medical",
            location="Philadelphia, PA",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
            status=JobPosting.Status.SAVED,
        )
        JobRequirement.objects.create(
            job=self.strong_job,
            role_family="Biomedical Engineering",
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry="Medical devices",
            required_skills="Python\nDjango\nElectrical engineering",
            preferred_skills="Computer science",
            required_education="Electrical Engineering",
            minimum_years_experience=0,
        )

        self.weak_job = JobPosting.objects.create(
            title="Enterprise Sales Manager",
            company="Zulu Software",
            location="New York, NY",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.ONSITE,
            status=JobPosting.Status.SAVED,
        )
        JobRequirement.objects.create(
            job=self.weak_job,
            role_family="Enterprise Sales Management",
            seniority_level=JobRequirement.SeniorityLevel.SENIOR,
            industry="Enterprise software sales",
            required_skills="Quota management\nEnterprise sales\nCold outreach",
            required_education="Business Administration",
            minimum_years_experience=8,
        )

    def test_dashboard_displays_match_results_for_saved_jobs(self):
        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RANK THE FIT. CALIBRATE THE SEARCH.")
        self.assertContains(response, "Alpha Medical")
        self.assertContains(response, "MATCH ANALYSIS")
        self.assertContains(response, "PRIORITY ROLE")

    def test_strong_fit_filter_excludes_weak_job(self):
        response = self.client.get(reverse("job_list"), {"fit": "strong"})

        self.assertContains(response, "Alpha Medical")
        self.assertNotContains(response, "Zulu Software")

    def test_highest_match_sort_places_strong_job_first(self):
        response = self.client.get(
            reverse("job_list"),
            {"sort": "match_high"},
        )
        content = response.content.decode()

        self.assertLess(content.index("Alpha Medical"), content.index("Zulu Software"))

    def test_requirement_vocabulary_is_searchable_from_dashboard(self):
        response = self.client.get(
            reverse("job_list"),
            {"q": "Quota management"},
        )

        self.assertContains(response, "Zulu Software")
        self.assertNotContains(response, "Alpha Medical")

    def test_match_page_saves_human_calibration_and_score_snapshot(self):
        response = self.client.post(
            reverse("job_match", args=[self.strong_job.id]),
            {
                "human_rating": JobCalibration.HumanRating.STRONG,
                "opportunity_type": JobCalibration.OpportunityType.PRIORITY,
                "notes": "Excellent alignment with my primary medical-device search.",
            },
        )

        self.assertRedirects(
            response,
            reverse("job_match", args=[self.strong_job.id]),
        )
        calibration = JobCalibration.objects.get(job=self.strong_job)
        self.assertIsNotNone(calibration.predicted_score)
        self.assertGreaterEqual(calibration.predicted_score, 80)
        self.assertIn(
            calibration.predicted_classification,
            {"STRONG MATCH", "GOOD MATCH"},
        )
        self.assertEqual(calibration.predicted_track, "PRIORITY ROLE")
        self.assertEqual(calibration.agreement_status, "ALIGNED")

    def test_calibration_post_updates_existing_record(self):
        JobCalibration.objects.create(
            job=self.strong_job,
            human_rating=JobCalibration.HumanRating.POSSIBLE,
        )

        self.client.post(
            reverse("job_match", args=[self.strong_job.id]),
            {
                "human_rating": JobCalibration.HumanRating.STRONG,
                "opportunity_type": JobCalibration.OpportunityType.PRIORITY,
                "notes": "Updated after reviewing the full requirements.",
            },
        )

        self.assertEqual(JobCalibration.objects.filter(job=self.strong_job).count(), 1)
        calibration = JobCalibration.objects.get(job=self.strong_job)
        self.assertEqual(calibration.human_rating, JobCalibration.HumanRating.STRONG)

    def test_unreviewed_filter_hides_calibrated_job(self):
        JobCalibration.objects.create(
            job=self.strong_job,
            human_rating=JobCalibration.HumanRating.STRONG,
            predicted_score=95,
            predicted_classification="STRONG MATCH",
            predicted_track="PRIORITY ROLE",
        )

        response = self.client.get(reverse("job_list"), {"review": "unreviewed"})

        self.assertNotContains(response, "Alpha Medical")
        self.assertContains(response, "Zulu Software")
