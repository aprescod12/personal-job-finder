from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from tracker.intake_views import INTAKE_SESSION_KEY
from tracker.models import CareerProfile, JobPosting

from .models import DiscoveryRun, RawJobOpportunity
from .providers import FixtureDiscoveryProvider
from .services import run_discovery


def fake_extraction(opportunity):
    return {
        "job": {
            "title": opportunity.title_hint,
            "company": opportunity.company_hint,
            "location": opportunity.location_hint,
            "job_url": opportunity.source_url,
            "source": opportunity.provider_label,
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.HYBRID,
            "deadline_status": JobPosting.DeadlineStatus.UNKNOWN,
            "application_deadline": None,
            "next_action": "Verify the employer listing",
            "description": opportunity.raw_listing_text,
        },
        "requirements": {
            "role_family": opportunity.title_hint,
            "seniority_level": "entry_level",
            "industry": opportunity.industry_hint,
            "required_skills": "Python",
            "preferred_skills": "MATLAB",
            "required_education": "Electrical Engineering",
            "preferred_education": "Biomedical Engineering",
            "minimum_years_experience": None,
            "maximum_years_experience": None,
            "responsibilities": "Execute verification testing",
            "certifications": "",
            "work_authorization_requirements": "",
            "hard_disqualifiers": "",
            "requirement_notes": "Fixture extraction for workflow testing.",
        },
        "provider": {
            "key": "fake-processing-extractor",
            "label": "Fake processing extractor",
            "version": "fake-v1",
            "mode": "test",
        },
        "orchestration": {
            "status": "success",
            "fallback_used": False,
            "manual_review_required": False,
            "attempts": [],
            "total_elapsed_ms": 1,
        },
        "warnings": [],
        "evidence": [],
        "parser_version": "fake-v1",
    }


class DiscoveryServiceTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.target_roles = "Test Engineer\nEmbedded Systems Engineer"
        self.profile.target_industries = "Medical devices\nBiomedical instrumentation"
        self.profile.preferred_locations = "Philadelphia, PA\nBoston, MA"
        self.profile.preferred_work_arrangement = "flexible"
        self.profile.preferred_employment_type = JobPosting.EmploymentType.FULL_TIME
        self.profile.save()

    def test_fixture_run_captures_query_and_raw_results_without_creating_jobs(self):
        run = run_discovery(FixtureDiscoveryProvider.key, profile=self.profile)

        self.assertEqual(run.status, DiscoveryRun.Status.COMPLETED)
        self.assertEqual(run.provider_version, "fixture-discovery-v1")
        self.assertEqual(run.result_count, 4)
        self.assertEqual(run.opportunities.count(), 4)
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertIn("Test Engineer", run.query_payload["target_roles"])

        priority = run.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )
        self.assertEqual(
            priority.broad_relevance,
            RawJobOpportunity.BroadRelevance.BROAD_MATCH,
        )
        self.assertTrue(priority.raw_listing_text)
        self.assertTrue(priority.raw_text_sha256)
        self.assertEqual(priority.status, RawJobOpportunity.Status.NEW)

    def test_rediscovered_provider_identifiers_are_blocking_duplicates(self):
        first = run_discovery(FixtureDiscoveryProvider.key, profile=self.profile)
        second = run_discovery(FixtureDiscoveryProvider.key, profile=self.profile)

        self.assertEqual(first.duplicate_count, 0)
        self.assertEqual(second.duplicate_count, 4)
        duplicate = second.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )
        self.assertEqual(duplicate.status, RawJobOpportunity.Status.DUPLICATE)
        self.assertIsNotNone(duplicate.duplicate_of_opportunity)
        self.assertTrue(duplicate.has_blocking_duplicate)

    def test_existing_tracked_url_is_detected_before_processing(self):
        existing = JobPosting.objects.create(
            title="Junior Medical Device Test Engineer",
            company="Northstar Medical Systems",
            location="Philadelphia, PA",
            job_url="https://jobs.example.com/listings/medtech-test-engineer-001",
        )

        run = run_discovery(FixtureDiscoveryProvider.key, profile=self.profile)
        opportunity = run.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )

        self.assertEqual(opportunity.status, RawJobOpportunity.Status.DUPLICATE)
        self.assertEqual(opportunity.duplicate_of_job, existing)
        self.assertTrue(
            any(
                item.get("reason") == "exact_url"
                for item in opportunity.duplicate_details
            )
        )


class DiscoveryViewTests(TestCase):
    def setUp(self):
        profile = CareerProfile.get_solo()
        profile.target_roles = "Test Engineer\nEmbedded Systems Engineer"
        profile.target_industries = "Medical devices\nBiomedical instrumentation"
        profile.preferred_locations = "Philadelphia, PA\nBoston, MA"
        profile.save()
        self.run = run_discovery(FixtureDiscoveryProvider.key, profile=profile)
        self.opportunity = self.run.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )

    def test_inbox_discloses_untrusted_boundary_and_runs_provider_via_post(self):
        response = self.client.get(reverse("job_discovery:inbox"))
        self.assertContains(response, "DISCOVERY RESULTS ARE NOT VERIFIED JOBS")
        self.assertContains(response, "Local fixture provider")
        self.assertContains(response, "Junior Medical Device Test Engineer")

        response = self.client.get(reverse("job_discovery:run"))
        self.assertEqual(response.status_code, 405)

        response = self.client.post(
            reverse("job_discovery:run"),
            {"provider_key": FixtureDiscoveryProvider.key},
        )
        self.assertRedirects(response, reverse("job_discovery:inbox"))
        self.assertEqual(DiscoveryRun.objects.count(), 2)

    @patch("job_discovery.services.extract_job_with_fallback")
    def test_send_to_processing_creates_session_draft_not_job(self, extractor):
        extractor.return_value = fake_extraction(self.opportunity)

        response = self.client.post(
            reverse(
                "job_discovery:send_to_processing",
                args=[self.opportunity.id],
            )
        )

        self.assertRedirects(response, reverse("job_intake_review"))
        self.assertEqual(JobPosting.objects.count(), 0)
        self.opportunity.refresh_from_db()
        self.assertEqual(
            self.opportunity.status,
            RawJobOpportunity.Status.SENT_TO_PROCESSING,
        )
        draft = self.client.session[INTAKE_SESSION_KEY]
        self.assertEqual(draft["discovery_opportunity_id"], self.opportunity.id)
        self.assertEqual(draft["raw_text"], self.opportunity.raw_listing_text)

    @patch("job_discovery.services.extract_job_with_fallback")
    def test_reviewed_processing_creates_job_and_links_discovery(self, extractor):
        extractor.return_value = fake_extraction(self.opportunity)
        self.client.post(
            reverse(
                "job_discovery:send_to_processing",
                args=[self.opportunity.id],
            )
        )

        response = self.client.post(
            reverse("job_intake_review"),
            {
                "title": self.opportunity.title_hint,
                "company": self.opportunity.company_hint,
                "location": self.opportunity.location_hint,
                "job_url": self.opportunity.source_url,
                "source": self.opportunity.provider_label,
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "work_arrangement": JobPosting.WorkArrangement.HYBRID,
                "deadline_status": JobPosting.DeadlineStatus.UNKNOWN,
                "application_deadline": "",
                "next_action": "Verify the employer listing",
                "description": self.opportunity.raw_listing_text,
                "role_family": "Test Engineer",
                "seniority_level": "entry_level",
                "industry": "Medical devices",
                "required_skills": "Python",
                "preferred_skills": "MATLAB",
                "required_education": "Electrical Engineering",
                "preferred_education": "Biomedical Engineering",
                "minimum_years_experience": "",
                "maximum_years_experience": "",
                "responsibilities": "Execute verification testing",
                "certifications": "",
                "work_authorization_requirements": "",
                "hard_disqualifiers": "",
                "requirement_notes": "Reviewed discovery fixture.",
            },
        )

        job = JobPosting.objects.get()
        self.assertRedirects(response, reverse("job_detail", args=[job.id]))
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, RawJobOpportunity.Status.PROCESSED)
        self.assertEqual(self.opportunity.processed_job, job)
        self.assertNotIn(INTAKE_SESSION_KEY, self.client.session)

    @patch("job_discovery.services.extract_job_with_fallback")
    def test_discarding_processing_draft_returns_opportunity_to_inbox(self, extractor):
        extractor.return_value = fake_extraction(self.opportunity)
        self.client.post(
            reverse(
                "job_discovery:send_to_processing",
                args=[self.opportunity.id],
            )
        )

        response = self.client.post(reverse("job_intake_clear"))

        self.assertRedirects(
            response,
            reverse(
                "job_discovery:opportunity_detail",
                args=[self.opportunity.id],
            ),
        )
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, RawJobOpportunity.Status.NEW)
        self.assertIsNone(self.opportunity.sent_to_processing_at)

    def test_duplicate_requires_explicit_override_before_processing(self):
        second_run = run_discovery(FixtureDiscoveryProvider.key)
        duplicate = second_run.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )

        response = self.client.post(
            reverse("job_discovery:send_to_processing", args=[duplicate.id])
        )
        self.assertRedirects(
            response,
            reverse("job_discovery:opportunity_detail", args=[duplicate.id]),
        )
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, RawJobOpportunity.Status.DUPLICATE)

        response = self.client.post(
            reverse("job_discovery:retain_duplicate", args=[duplicate.id])
        )
        self.assertRedirects(
            response,
            reverse("job_discovery:opportunity_detail", args=[duplicate.id]),
        )
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, RawJobOpportunity.Status.READY)
        self.assertTrue(duplicate.duplicate_override)

    def test_ignore_and_restore_are_explicit_post_actions(self):
        response = self.client.get(
            reverse("job_discovery:ignore_opportunity", args=[self.opportunity.id])
        )
        self.assertEqual(response.status_code, 405)

        self.client.post(
            reverse("job_discovery:ignore_opportunity", args=[self.opportunity.id]),
            {"notes": "Outside this search round."},
        )
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, RawJobOpportunity.Status.IGNORED)
        self.assertEqual(self.opportunity.decision_notes, "Outside this search round.")

        self.client.post(
            reverse("job_discovery:restore_opportunity", args=[self.opportunity.id])
        )
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, RawJobOpportunity.Status.READY)
