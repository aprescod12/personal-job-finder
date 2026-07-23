from unittest.mock import patch

from django.test import TestCase

from tracker.models import CareerProfile
from tracker.services.job_extraction import JobExtractionError

from .models import DiscoveryRun, RawJobOpportunity
from .providers import DiscoveryQuery, DiscoveredOpportunity, FixtureDiscoveryProvider
from .services import (
    APPROVED_DISCOVERY_PROVIDERS,
    DiscoveryHandoffError,
    DiscoveryProviderError,
    prepare_opportunity_for_processing,
    run_discovery,
)


class InvalidFixtureProvider:
    key = "invalid-fixture"
    label = "Invalid fixture provider"
    version = "invalid-v1"

    def discover(self, query: DiscoveryQuery):
        del query
        return (
            DiscoveredOpportunity(
                external_id="invalid-1",
                source_url="https://jobs.example.com/invalid-1",
                title_hint="Invalid result",
                company_hint="Fixture",
                location_hint="",
                raw_listing_text="too short",
            ),
        )


class DiscoveryFailurePersistenceTests(TestCase):
    def test_provider_contract_failure_preserves_failed_run_without_partial_results(self):
        profile = CareerProfile.get_solo()

        with patch.dict(
            APPROVED_DISCOVERY_PROVIDERS,
            {InvalidFixtureProvider.key: InvalidFixtureProvider},
        ):
            with self.assertRaises(DiscoveryProviderError):
                run_discovery(InvalidFixtureProvider.key, profile=profile)

        run = DiscoveryRun.objects.get(provider_key=InvalidFixtureProvider.key)
        self.assertEqual(run.status, DiscoveryRun.Status.FAILED)
        self.assertIn("enough raw listing text", run.error_message)
        self.assertIsNotNone(run.completed_at)
        self.assertEqual(run.opportunities.count(), 0)

    def test_extraction_failure_persists_retryable_opportunity_state(self):
        run = run_discovery(FixtureDiscoveryProvider.key)
        opportunity = run.opportunities.get(
            external_id="fixture-medtech-test-engineer-001"
        )

        with patch(
            "job_discovery.services.extract_job_with_fallback",
            side_effect=JobExtractionError("controlled extraction failure"),
        ):
            with self.assertRaises(DiscoveryHandoffError):
                prepare_opportunity_for_processing(opportunity)

        opportunity.refresh_from_db()
        self.assertEqual(
            opportunity.status,
            RawJobOpportunity.Status.PROCESSING_FAILED,
        )
        self.assertEqual(opportunity.processing_error, "controlled extraction failure")
        self.assertTrue(opportunity.can_send_to_processing)
