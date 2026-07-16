from django.test import TestCase
from django.urls import reverse

from .models import JobPosting


class JobPostingModelTests(TestCase):
    def test_string_representation(self):
        job = JobPosting(title="Test Engineer", company="Example Medical")
        self.assertEqual(str(job), "Test Engineer at Example Medical")

    def test_default_status_is_discovered(self):
        job = JobPosting.objects.create(title="Engineer", company="Example")
        self.assertEqual(job.status, JobPosting.Status.DISCOVERED)


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
