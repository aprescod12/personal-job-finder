from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobPosting, JobRequirement


class JobPostingModelTests(TestCase):
    def test_string_representation(self):
        job = JobPosting(title="Test Engineer", company="Example Medical")
        self.assertEqual(str(job), "Test Engineer at Example Medical")

    def test_default_status_is_discovered(self):
        job = JobPosting.objects.create(title="Engineer", company="Example")
        self.assertEqual(job.status, JobPosting.Status.DISCOVERED)


class JobRequirementModelTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Validation Engineer",
            company="Device Company",
        )

    def test_blank_requirement_has_no_content(self):
        requirements = JobRequirement(job=self.job)

        self.assertFalse(requirements.has_content)
        self.assertEqual(requirements.experience_range, "Not specified")

    def test_experience_range_validation(self):
        requirements = JobRequirement(
            job=self.job,
            minimum_years_experience=3,
            maximum_years_experience=1,
        )

        with self.assertRaises(ValidationError):
            requirements.full_clean()


class CareerProfileModelTests(TestCase):
    def test_get_solo_returns_one_profile(self):
        first_profile = CareerProfile.get_solo()
        second_profile = CareerProfile.get_solo()

        self.assertEqual(first_profile.pk, 1)
        self.assertEqual(first_profile.pk, second_profile.pk)
        self.assertEqual(CareerProfile.objects.count(), 1)

    def test_string_representation(self):
        profile = CareerProfile.get_solo()
        profile.full_name = "Amiri Prescod"
        self.assertEqual(str(profile), "Amiri Prescod's career profile")


class JobPostingViewTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Biomedical Engineer",
            company="Example Medical",
            location="Philadelphia, PA",
            status=JobPosting.Status.SAVED,
        )

    def test_job_list_displays_saved_job(self):
        response = self.client.get(reverse("job_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Biomedical Engineer")
        self.assertContains(response, "Example Medical")

    def test_job_detail_displays_job(self):
        response = self.client.get(reverse("job_detail", args=[self.job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Biomedical Engineer")
        self.assertContains(response, "JOB REQUIREMENTS")

    def test_create_job(self):
        response = self.client.post(
            reverse("job_create"),
            {
                "title": "Systems Engineer",
                "company": "Device Company",
                "status": JobPosting.Status.DISCOVERED,
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            },
        )
        created_job = JobPosting.objects.get(title="Systems Engineer")
        self.assertRedirects(response, reverse("job_detail", args=[created_job.id]))
        self.assertTrue(JobRequirement.objects.filter(job=created_job).exists())

    def test_edit_job(self):
        response = self.client.post(
            reverse("job_edit", args=[self.job.id]),
            {
                "title": self.job.title,
                "company": self.job.company,
                "location": self.job.location,
                "status": JobPosting.Status.APPLIED,
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.ONSITE,
                "next_action": "Follow up with recruiter",
            },
        )
        self.job.refresh_from_db()
        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))
        self.assertEqual(self.job.status, JobPosting.Status.APPLIED)
        self.assertEqual(self.job.next_action, "Follow up with recruiter")

    def test_delete_job(self):
        response = self.client.post(reverse("job_delete", args=[self.job.id]))
        self.assertRedirects(response, reverse("job_list"))
        self.assertFalse(JobPosting.objects.filter(id=self.job.id).exists())

    def test_filter_jobs_by_status(self):
        JobPosting.objects.create(
            title="Other Role",
            company="Other Company",
            status=JobPosting.Status.REJECTED,
        )
        response = self.client.get(
            reverse("job_list"),
            {"status": JobPosting.Status.SAVED},
        )
        self.assertContains(response, "Biomedical Engineer")
        self.assertNotContains(response, "Other Role")

    def test_search_jobs(self):
        response = self.client.get(reverse("job_list"), {"q": "Philadelphia"})
        self.assertContains(response, "Biomedical Engineer")

    def test_requirements_can_be_saved_and_lists_are_normalized(self):
        response = self.client.post(
            reverse("job_requirements", args=[self.job.id]),
            {
                "role_family": "Verification and Validation Engineering",
                "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
                "industry": "Medical devices",
                "required_skills": "MATLAB\nMATLAB\nTest protocols",
                "preferred_skills": "ISO 13485",
                "required_education": "Electrical Engineering",
                "preferred_education": "Biomedical Engineering",
                "minimum_years_experience": "0",
                "maximum_years_experience": "2",
                "responsibilities": "Write protocols\nExecute tests",
                "certifications": "FDA design controls",
                "work_authorization_requirements": "",
                "hard_disqualifiers": "Active clearance required",
                "requirement_notes": "Manual review of posting.",
            },
        )

        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))
        requirements = JobRequirement.objects.get(job=self.job)
        self.assertEqual(requirements.required_skills, "MATLAB\nTest protocols")
        self.assertEqual(requirements.experience_range, "0–2 years")

    def test_invalid_experience_range_is_rejected(self):
        response = self.client.post(
            reverse("job_requirements", args=[self.job.id]),
            {
                "role_family": "Test Engineering",
                "seniority_level": JobRequirement.SeniorityLevel.ENTRY_LEVEL,
                "minimum_years_experience": "4",
                "maximum_years_experience": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Maximum experience cannot be lower than minimum experience",
        )


class CareerProfileViewTests(TestCase):
    def test_profile_page_displays_seeded_background(self):
        response = self.client.get(reverse("career_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CAREER PROFILE")
        self.assertContains(response, "Amiri Prescod")
        self.assertContains(response, "Biomedical Engineer")

    def test_profile_can_be_updated_without_creating_duplicates(self):
        response = self.client.post(
            reverse("career_profile"),
            {
                "full_name": "Amiri Prescod",
                "professional_headline": "Biomedical Engineering Candidate",
                "education_summary": "Electrical Engineering and Biomedical Engineering",
                "target_roles": "Systems Engineer\nSystems Engineer\nTest Engineer",
                "target_industries": "Medical devices",
                "skills": "Python\nDjango",
                "experience_level": CareerProfile.ExperienceLevel.ENTRY_LEVEL,
                "preferred_locations": "Philadelphia, PA",
                "preferred_work_arrangement": (
                    CareerProfile.PreferredWorkArrangement.HYBRID
                ),
                "preferred_employment_type": JobPosting.EmploymentType.FULL_TIME,
                "minimum_salary": "70000",
                "work_authorization": "",
                "priorities": "Hands-on engineering",
                "deal_breakers": "",
                "additional_context": "Interested in medical devices.",
            },
        )

        profile = CareerProfile.get_solo()
        self.assertRedirects(response, reverse("career_profile"))
        self.assertEqual(CareerProfile.objects.count(), 1)
        self.assertEqual(
            profile.professional_headline,
            "Biomedical Engineering Candidate",
        )
        self.assertEqual(profile.target_roles, "Systems Engineer\nTest Engineer")
        self.assertEqual(profile.minimum_salary, 70000)
