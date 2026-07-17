from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import JobCalibrationForm, JobListingVerificationForm, JobPostingForm
from .models import JobCalibration, JobPosting
from .services.weight_model_comparison import (
    LIVE_MODEL_KEY,
    MODEL_A_KEY,
    MODEL_A_WEIGHTS,
    MODEL_B_WEIGHTS,
)


class ListingReliabilityModelTests(TestCase):
    def test_confirmed_past_deadline_makes_open_listing_effectively_expired(self):
        job = JobPosting(
            title="Expired role",
            company="Example Medical",
            listing_status=JobPosting.ListingStatus.OPEN,
            deadline_status=JobPosting.DeadlineStatus.CONFIRMED,
            application_deadline=timezone.localdate() - timedelta(days=1),
        )

        self.assertEqual(
            job.effective_listing_status,
            JobPosting.ListingStatus.EXPIRED,
        )
        self.assertTrue(job.listing_is_unavailable)
        self.assertTrue(job.deadline_is_overdue)

    def test_open_listing_becomes_stale_after_seven_days(self):
        job = JobPosting(
            title="Stale role",
            company="Example Medical",
            listing_status=JobPosting.ListingStatus.OPEN,
            deadline_status=JobPosting.DeadlineStatus.NOT_STATED,
            listing_last_verified=timezone.localdate() - timedelta(days=8),
        )

        self.assertTrue(job.listing_needs_verification)

    def test_recent_open_listing_with_known_deadline_state_is_actionable(self):
        job = JobPosting(
            title="Current role",
            company="Example Medical",
            listing_status=JobPosting.ListingStatus.OPEN,
            deadline_status=JobPosting.DeadlineStatus.ROLLING,
            listing_last_verified=timezone.localdate(),
        )

        self.assertTrue(job.listing_is_available)
        self.assertFalse(job.listing_needs_verification)
        self.assertEqual(job.deadline_label, "Rolling / open until filled")


class ListingReliabilityFormTests(TestCase):
    def test_deadline_date_automatically_marks_deadline_confirmed(self):
        future = timezone.localdate() + timedelta(days=14)
        form = JobPostingForm(
            data={
                "title": "Verification Engineer",
                "company": "Example Medical",
                "job_url": "https://example.com/jobs/verification-engineer",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.HYBRID,
                "deadline_status": JobPosting.DeadlineStatus.UNKNOWN,
                "application_deadline": future.isoformat(),
                "status": JobPosting.Status.SAVED,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["deadline_status"],
            JobPosting.DeadlineStatus.CONFIRMED,
        )

    def test_open_listing_requires_direct_url(self):
        form = JobListingVerificationForm(
            data={
                "job_url": "",
                "listing_status": JobPosting.ListingStatus.OPEN,
                "deadline_status": JobPosting.DeadlineStatus.NOT_STATED,
                "listing_verification_notes": "Checked employer website.",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("job_url", form.errors)


class ListingReliabilityViewTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Product Safety Engineer",
            company="Example Medical",
            job_url="https://example.com/careers",
            status=JobPosting.Status.SAVED,
        )

    def test_verification_page_records_status_date_deadline_and_note(self):
        deadline = timezone.localdate() + timedelta(days=6)
        response = self.client.post(
            reverse("job_listing_verify", args=[self.job.id]),
            {
                "job_url": "https://example.com/jobs/product-safety-engineer",
                "listing_status": JobPosting.ListingStatus.OPEN,
                "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
                "application_deadline": deadline.isoformat(),
                "listing_verification_notes": "Exact employer role page is open.",
            },
        )

        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(self.job.listing_last_verified, timezone.localdate())
        self.assertEqual(self.job.application_deadline, deadline)
        self.assertIn("Exact employer role page", self.job.listing_verification_notes)

    def test_dashboard_emphasizes_unverified_listing_and_deadline_filter(self):
        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VERIFY THE LISTING")
        self.assertContains(response, "VERIFICATION REQUIRED")
        self.assertContains(response, "Never checked on employer site")

        filtered = self.client.get(
            reverse("job_list"),
            {"listing": "needs_verification"},
        )
        self.assertContains(filtered, self.job.title)

    def test_wrong_page_is_visible_as_link_problem(self):
        self.job.listing_status = JobPosting.ListingStatus.WRONG_PAGE
        self.job.listing_last_verified = timezone.localdate()
        self.job.listing_verification_notes = "URL redirects to general careers page."
        self.job.save()

        response = self.client.get(reverse("job_detail", args=[self.job.id]))

        self.assertContains(response, "WRONG COMPANY PAGE")
        self.assertContains(response, "not a reliable direct application page")
        self.assertContains(response, "CHECK RECORDED LINK")


class GoodMatchRatingTests(TestCase):
    def test_good_match_is_a_separate_human_rating(self):
        choices = dict(JobCalibration.HumanRating.choices)

        self.assertEqual(choices[JobCalibration.HumanRating.STRONG], "Strong match")
        self.assertEqual(choices[JobCalibration.HumanRating.GOOD], "Good match")
        self.assertEqual(
            JobCalibration.PREDICTED_RATING_MAP["GOOD MATCH"],
            JobCalibration.HumanRating.GOOD,
        )

    def test_calibration_form_includes_good_match(self):
        form = JobCalibrationForm()
        values = [value for value, _ in form.fields["human_rating"].choices]

        self.assertIn(JobCalibration.HumanRating.GOOD, values)
        self.assertIn("Good = qualified and worth applying", form.fields["human_rating"].help_text)

    def test_model_a_remains_live_and_model_b_is_retained(self):
        self.assertEqual(LIVE_MODEL_KEY, MODEL_A_KEY)
        self.assertEqual(MODEL_A_WEIGHTS["required_skills"], 20)
        self.assertEqual(MODEL_A_WEIGHTS["industry"], 20)
        self.assertEqual(MODEL_B_WEIGHTS["required_skills"], 25)
        self.assertEqual(MODEL_B_WEIGHTS["industry"], 15)
