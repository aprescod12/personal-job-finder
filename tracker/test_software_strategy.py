from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobPosting, JobRequirement
from .services.software_strategy_matching import (
    MATCHER_VERSION,
    analyze_job_match,
)


class SoftwareStrategyTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Medical Device Software Engineer\n"
            "Biomedical Engineer"
        )
        self.profile.target_industries = (
            "Medical devices\n"
            "Healthcare technology"
        )
        self.profile.skills = (
            "Electrical engineering\n"
            "Biomedical engineering\n"
            "Python\n"
            "Software development\n"
            "Testing and validation\n"
            "Technical documentation"
        )
        self.profile.education_summary = (
            "B.S. Electrical Engineering. M.S. Biomedical Engineering in progress. "
            "Minor in Computer Science."
        )
        self.profile.preferred_employment_type = JobPosting.EmploymentType.FULL_TIME
        self.profile.save()

    def make_job(
        self,
        *,
        title,
        role_family,
        industry,
        required_skills="Python\nSoftware development\nTesting and validation",
    ):
        job = JobPosting.objects.create(
            title=title,
            company="Example Company",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
        )
        requirements = JobRequirement.objects.create(
            job=job,
            role_family=role_family,
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry=industry,
            required_skills=required_skills,
            required_education=(
                "Electrical Engineering\n"
                "Biomedical Engineering\n"
                "Computer Science"
            ),
            minimum_years_experience=0,
            maximum_years_experience=2,
        )
        return job, requirements

    def test_medical_device_software_is_a_priority_path(self):
        job, requirements = self.make_job(
            title="Medical Device Software Engineer",
            role_family="Medical Device Software Engineering",
            industry="Medical devices",
        )

        result = analyze_job_match(self.profile, job, requirements)

        self.assertEqual(result.track, "PRIORITY ROLE")
        self.assertEqual(result.matcher_version, MATCHER_VERSION)

    def test_embedded_medtech_role_receives_software_path_credit(self):
        self.profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Biomedical Engineer"
        )
        self.profile.save()
        job, requirements = self.make_job(
            title="Embedded Software Engineer",
            role_family="Embedded Software and Firmware Engineering",
            industry="Medical devices",
            required_skills="Embedded software\nC++\nTesting and validation",
        )

        result = analyze_job_match(self.profile, job, requirements)
        role_category = next(
            category
            for category in result.categories
            if category.key == "role"
        )

        self.assertEqual(result.track, "ADJACENT OPPORTUNITY")
        self.assertGreaterEqual(role_category.percent, 80)
        self.assertTrue(
            any(
                item.concept == "Software pathway into MedTech"
                for item in result.related_matches
            )
        )

    def test_software_test_automation_in_healthtech_is_adjacent(self):
        job, requirements = self.make_job(
            title="Software Test Automation Engineer",
            role_family="Software Test Automation Engineering",
            industry="Healthcare technology",
            required_skills="Python\nTest automation\nSoftware testing",
        )

        result = analyze_job_match(self.profile, job, requirements)

        self.assertEqual(result.track, "ADJACENT OPPORTUNITY")

    def test_general_software_outside_target_industry_is_not_priority(self):
        job, requirements = self.make_job(
            title="Software Engineer",
            role_family="Software Engineering",
            industry="Online advertising",
        )

        result = analyze_job_match(self.profile, job, requirements)

        self.assertEqual(result.track, "OUTSIDE PRIORITY")

    def test_dashboard_uses_software_aware_strategy(self):
        job, _ = self.make_job(
            title="Firmware Engineer",
            role_family="Firmware Engineering",
            industry="Medical devices",
            required_skills="Firmware\nC programming\nTechnical documentation",
        )

        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        rendered_job = next(
            item for item in response.context["jobs"] if item.id == job.id
        )
        self.assertEqual(
            rendered_job.match_result.matcher_version,
            MATCHER_VERSION,
        )
        self.assertEqual(
            rendered_job.match_result.track,
            "ADJACENT OPPORTUNITY",
        )
