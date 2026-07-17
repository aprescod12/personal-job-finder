from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobPosting, JobRequirement
from .services.strategy_matching import CATEGORY_WEIGHTS, analyze_job_match


class IndustryFirstStrategyTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Biomedical Engineer"
        )
        self.profile.target_industries = (
            "Medical devices\n"
            "Healthcare technology"
        )
        self.profile.skills = (
            "Electrical engineering\n"
            "Biomedical engineering\n"
            "Testing and validation\n"
            "Technical documentation\n"
            "Python"
        )
        self.profile.education_summary = (
            "B.S. Electrical Engineering. M.S. Biomedical Engineering in progress."
        )
        self.profile.preferred_employment_type = JobPosting.EmploymentType.FULL_TIME
        self.profile.save()

    def make_job(
        self,
        *,
        title,
        role_family,
        industry,
        required_skills="Technical documentation\nTesting and validation",
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
            required_education="Electrical Engineering\nBiomedical Engineering",
            minimum_years_experience=0,
            maximum_years_experience=2,
        )
        return job, requirements

    def test_industry_is_weighted_above_exact_role(self):
        self.assertEqual(sum(CATEGORY_WEIGHTS.values()), 100)
        self.assertEqual(CATEGORY_WEIGHTS["industry"], 20)
        self.assertEqual(CATEGORY_WEIGHTS["role"], 10)
        self.assertGreater(
            CATEGORY_WEIGHTS["industry"],
            CATEGORY_WEIGHTS["role"],
        )

    def test_product_safety_in_medical_devices_is_adjacent_not_outside(self):
        job, requirements = self.make_job(
            title="Product Safety Engineer",
            role_family="Product Safety Engineering",
            industry="Medical devices",
            required_skills=(
                "Electrical system testing\n"
                "Technical documentation\n"
                "Verification and validation"
            ),
        )

        result = analyze_job_match(self.profile, job, requirements)
        categories = {category.key: category for category in result.categories}

        self.assertEqual(result.track, "ADJACENT OPPORTUNITY")
        self.assertGreaterEqual(categories["role"].percent, 70)
        self.assertEqual(categories["industry"].percent, 100)
        self.assertTrue(
            any(
                item.concept == "Transferable technical MedTech function"
                for item in result.related_matches
            )
        )

    def test_quality_role_in_medical_devices_receives_transferable_credit(self):
        job, requirements = self.make_job(
            title="Quality Engineer I",
            role_family="Quality Engineering",
            industry="Medical devices",
            required_skills=(
                "Corrective and preventive action\n"
                "Technical documentation\n"
                "Testing and validation"
            ),
        )

        result = analyze_job_match(self.profile, job, requirements)
        role_category = next(
            category
            for category in result.categories
            if category.key == "role"
        )

        self.assertEqual(result.track, "ADJACENT OPPORTUNITY")
        self.assertGreaterEqual(role_category.percent, 70)

    def test_exact_function_outside_target_industry_is_not_priority(self):
        job, requirements = self.make_job(
            title="Medical Device Product Development Engineer",
            role_family="Medical Device Product Development Engineering",
            industry="Consumer electronics",
        )

        result = analyze_job_match(self.profile, job, requirements)

        self.assertEqual(result.track, "OUTSIDE PRIORITY")

    def test_medtech_commercial_role_does_not_receive_technical_role_boost(self):
        job, requirements = self.make_job(
            title="Associate Territory Manager",
            role_family="Clinical Sales and Territory Management",
            industry="Medical devices",
            required_skills="Sales\nAccount development\nClinical training",
        )

        result = analyze_job_match(self.profile, job, requirements)
        role_category = next(
            category
            for category in result.categories
            if category.key == "role"
        )

        self.assertEqual(result.track, "OUTSIDE PRIORITY")
        self.assertEqual(role_category.percent, 0)

    def test_dashboard_uses_revised_strategy(self):
        job, _ = self.make_job(
            title="Product Safety Engineer",
            role_family="Product Safety Engineering",
            industry="Medical devices",
        )

        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        rendered_job = next(
            item for item in response.context["jobs"] if item.id == job.id
        )
        self.assertEqual(
            rendered_job.match_result.track,
            "ADJACENT OPPORTUNITY",
        )
