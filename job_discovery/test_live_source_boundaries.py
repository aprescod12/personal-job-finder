from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import DiscoveryRun, RawJobOpportunity
from .services import DiscoveryHandoffError, prepare_opportunity_for_processing


class LiveSourceBoundaryTests(TestCase):
    def test_closed_source_record_cannot_enter_job_processing(self):
        run = DiscoveryRun.objects.create(
            provider_key="greenhouse",
            provider_label="Greenhouse approved employer boards",
            provider_version="greenhouse-job-board-v1",
            status=DiscoveryRun.Status.COMPLETED,
        )
        opportunity = RawJobOpportunity.objects.create(
            run=run,
            provider_key="greenhouse",
            provider_label="Greenhouse approved employer boards",
            provider_version="greenhouse-job-board-v1",
            external_id="northstar:101",
            source_url="https://example.org/careers/101",
            normalized_source_url="https://example.org/careers/101",
            title_hint="Test Engineer",
            company_hint="Northstar Medical",
            raw_listing_text=(
                "Test Engineer\nNorthstar Medical\nExecute verification and validation "
                "testing for regulated medical electrical equipment."
            ),
            raw_text_sha256="a" * 64,
            source_is_active=False,
            source_closed_at=timezone.now(),
        )

        self.assertFalse(opportunity.can_send_to_processing)
        with patch("job_discovery.services.extract_job_with_fallback") as extractor:
            with self.assertRaises(DiscoveryHandoffError):
                prepare_opportunity_for_processing(opportunity)

        extractor.assert_not_called()
        self.assertEqual(opportunity.processed_job_id, None)
