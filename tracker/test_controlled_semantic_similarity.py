from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobPosting, JobRequirement
from .services.semantic_similarity import (
    SEMANTIC_STRENGTH_CAP,
    best_semantic_match,
)
from .services.semantic_strategy_matching import (
    MATCHER_VERSION,
    analyze_job_match,
)


SEMANTIC_REQUIREMENT = "Patient monitoring data-acquisition architecture"


class ControlledSemanticSimilarityTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = (
            "Medical Device Product Development Engineer\n"
            "Biomedical Engineer\n"
            "Medical Device Software Engineer"
        )
        self.profile.target_industries = (
            "Medical devices\nHealthcare technology"
        )
        self.profile.skills = (
            "Electrical engineering\n"
            "Biomedical engineering\n"
            "Python\n"
            "Software development"
        )
        self.profile.education_summary = (
            "B.S. Electrical Engineering. M.S. Biomedical Engineering in progress."
        )
        self.profile.additional_context = (
            "Developed a physiological sensor-monitoring prototype for "
            "collecting patient signals."
        )
        self.profile.experience_level = CareerProfile.ExperienceLevel.ENTRY_LEVEL
        self.profile.preferred_employment_type = JobPosting.EmploymentType.FULL_TIME
        self.profile.save()

    def make_job(
        self,
        *,
        title="Biomedical Product Engineer",
        required_skills=SEMANTIC_REQUIREMENT,
        minimum_years_experience=0,
        work_authorization_requirements="",
        hard_disqualifiers="",
    ):
        job = JobPosting.objects.create(
            title=title,
            company="Example MedTech",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            work_arrangement=JobPosting.WorkArrangement.HYBRID,
        )
        requirements = JobRequirement.objects.create(
            job=job,
            role_family="Medical Device Product Development Engineering",
            seniority_level=JobRequirement.SeniorityLevel.ENTRY_LEVEL,
            industry="Medical devices",
            required_skills=required_skills,
            required_education="Electrical Engineering\nBiomedical Engineering",
            minimum_years_experience=minimum_years_experience,
            work_authorization_requirements=work_authorization_requirements,
            hard_disqualifiers=hard_disqualifiers,
        )
        return job, requirements

    def test_paraphrased_instrumentation_evidence_receives_semantic_credit(self):
        job, requirements = self.make_job()

        result = analyze_job_match(self.profile, job, requirements)
        semantic = next(
            item
            for item in result.semantic_matches
            if item.requirement == SEMANTIC_REQUIREMENT
        )
        required_category = next(
            category
            for category in result.categories
            if category.key == "required_skills"
        )

        self.assertEqual(result.matcher_version, MATCHER_VERSION)
        self.assertEqual(semantic.match_type, "semantic")
        self.assertIn("physiological sensor", semantic.evidence.casefold())
        self.assertIn("Biosignal and instrumentation", semantic.concept)
        self.assertGreater(semantic.strength, 0)
        self.assertLessEqual(semantic.strength, SEMANTIC_STRENGTH_CAP)
        self.assertGreater(required_category.percent, 0)
        self.assertFalse(
            any(
                gap.requirement == SEMANTIC_REQUIREMENT
                for gap in result.gaps
            )
        )

    def test_semantic_match_is_never_promoted_to_direct_or_rule_related(self):
        job, requirements = self.make_job()

        result = analyze_job_match(self.profile, job, requirements)

        self.assertFalse(
            any(
                item.requirement == SEMANTIC_REQUIREMENT
                for item in result.direct_matches
            )
        )
        self.assertFalse(
            any(
                item.requirement == SEMANTIC_REQUIREMENT
                for item in result.related_matches
            )
        )
        self.assertTrue(
            any(
                item.requirement == SEMANTIC_REQUIREMENT
                for item in result.semantic_matches
            )
        )

    def test_experience_requirement_is_not_semantically_overridden(self):
        job, requirements = self.make_job(minimum_years_experience=5)

        result = analyze_job_match(self.profile, job, requirements)
        experience = next(
            category
            for category in result.categories
            if category.key == "experience"
        )

        self.assertEqual(experience.percent, 0)
        self.assertTrue(
            any(
                gap.requirement.startswith("Experience:")
                for gap in result.gaps
            )
        )
        self.assertFalse(
            any(
                item.requirement.startswith("Experience:")
                for item in result.semantic_matches
            )
        )

    def test_sponsorship_conflict_remains_disqualifying(self):
        self.profile.work_authorization = "Needs sponsorship"
        self.profile.save()
        job, requirements = self.make_job(
            work_authorization_requirements=(
                "Employer cannot sponsor employment visas."
            )
        )

        result = analyze_job_match(self.profile, job, requirements)

        self.assertEqual(result.classification, "DISQUALIFIED")
        self.assertTrue(result.confirmed_blockers)

    def test_unrelated_text_does_not_receive_semantic_credit(self):
        semantic = best_semantic_match(
            "Territory sales and account development",
            [
                "Python",
                "Electrical engineering",
                "Physiological sensor-monitoring prototype",
            ],
        )

        self.assertIsNone(semantic)

    def test_match_page_displays_semantic_evidence_and_safety_note(self):
        job, _ = self.make_job()

        response = self.client.get(reverse("job_match", args=[job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SEMANTIC EVIDENCE")
        self.assertContains(response, "Biosignal and instrumentation")
        self.assertContains(response, "can never satisfy experience")
        self.assertContains(response, MATCHER_VERSION)

    def test_dashboard_uses_controlled_semantic_matcher(self):
        job, _ = self.make_job()

        response = self.client.get(reverse("job_list"))
        rendered_job = next(
            item for item in response.context["jobs"] if item.id == job.id
        )

        self.assertEqual(
            rendered_job.match_result.matcher_version,
            MATCHER_VERSION,
        )
        self.assertTrue(rendered_job.match_result.semantic_matches)
