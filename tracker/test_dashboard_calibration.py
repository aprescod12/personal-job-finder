from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobPosting, JobRequirement, MatchCalibration
from .services.matching import analyze_job_match


class DashboardMatchTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.preferred_locations = "Philadelphia, PA"
        self.profile.save()

        self.strong_job = JobPosting.objects.create(
            title="Validation Engineer",
            company="MedTech Strong",
            location="Philadelphia, PA",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
        )
        self.strong_requirements = JobRequirement.objects.create(
            job=self.strong_job,
            role_family="Validation Engineer",
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry="Medical devices",
            required_skills="Python\nTesting and validation",
            required_education="Electrical Engineering",
            minimum_years_experience=0,
        )

        self.weak_job = JobPosting.objects.create(
            title="Regional Sales Manager",
            company="Unrelated Company",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.ONSITE,
        )
        self.weak_requirements = JobRequirement.objects.create(
            job=self.weak_job,
            role_family="Sales Management",
            seniority_level=JobRequirement.SeniorityLevel.SENIOR,
            industry="Retail sales",
            required_skills="Quota management\nSales forecasting",
            required_education="Business Administration",
            minimum_years_experience=5,
        )

    def test_dashboard_displays_live_match_scores(self):
        response = self.client.get(reverse("job_list"))
        strong_result = analyze_job_match(
            self.profile,
            self.strong_job,
            self.strong_requirements,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MATCH QUALITY")
        self.assertContains(response, strong_result.score)
        self.assertContains(response, strong_result.classification)
        self.assertContains(response, "CALIBRATION")

    def test_dashboard_sorts_best_match_first(self):
        response = self.client.get(reverse("job_list"), {"sort": "score_desc"})
        content = response.content.decode()

        self.assertLess(
            content.index("MedTech Strong"),
            content.index("Unrelated Company"),
        )

    def test_dashboard_filters_by_strong_match(self):
        response = self.client.get(reverse("job_list"), {"fit": "strong"})

        self.assertContains(response, "MedTech Strong")
        self.assertNotContains(response, "Unrelated Company")

    def test_dashboard_filters_by_priority_track(self):
        response = self.client.get(reverse("job_list"), {"track": "priority"})

        self.assertContains(response, "MedTech Strong")
        self.assertNotContains(response, "Unrelated Company")


class MatchCalibrationTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Validation Engineer",
            company="Calibration Medical",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
        )
        JobRequirement.objects.create(
            job=self.job,
            role_family="Validation Engineer",
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry="Medical devices",
            required_skills="Python",
            required_education="Electrical Engineering",
            minimum_years_experience=0,
        )

    def test_match_page_saves_human_judgment(self):
        response = self.client.post(
            reverse("job_match", args=[self.job.id]),
            {
                "verdict": MatchCalibration.Verdict.STRONG,
                "notes": "The role closely matches my target and background.",
            },
        )

        self.assertRedirects(response, reverse("job_match", args=[self.job.id]))
        calibration = MatchCalibration.objects.get(job=self.job)
        self.assertEqual(calibration.verdict, MatchCalibration.Verdict.STRONG)
        self.assertIn("closely matches", calibration.notes)

    def test_saving_again_updates_instead_of_duplicating(self):
        MatchCalibration.objects.create(
            job=self.job,
            verdict=MatchCalibration.Verdict.POSSIBLE,
        )

        self.client.post(
            reverse("job_match", args=[self.job.id]),
            {
                "verdict": MatchCalibration.Verdict.WEAK,
                "notes": "After review, the responsibilities are not aligned.",
            },
        )

        self.assertEqual(MatchCalibration.objects.count(), 1)
        calibration = MatchCalibration.objects.get(job=self.job)
        self.assertEqual(calibration.verdict, MatchCalibration.Verdict.WEAK)

    def test_match_page_displays_saved_verdict(self):
        MatchCalibration.objects.create(
            job=self.job,
            verdict=MatchCalibration.Verdict.STRONG,
        )

        response = self.client.get(reverse("job_match", args=[self.job.id]))

        self.assertContains(response, "YOUR CURRENT VERDICT")
        self.assertContains(response, "STRONG MATCH")
        self.assertContains(response, "SAVE MY JUDGMENT")

    def test_dashboard_can_filter_program_disagreements(self):
        MatchCalibration.objects.create(
            job=self.job,
            verdict=MatchCalibration.Verdict.WEAK,
            notes="I consider this a weak fit despite the calculated score.",
        )

        response = self.client.get(reverse("job_list"), {"review": "differs"})

        self.assertContains(response, "Calibration Medical")
        self.assertContains(response, "DIFFERS")

    def test_string_representation(self):
        calibration = MatchCalibration.objects.create(
            job=self.job,
            verdict=MatchCalibration.Verdict.POSSIBLE,
        )

        self.assertIn("Calibration for Validation Engineer", str(calibration))
        self.assertIn("Possible match", str(calibration))
