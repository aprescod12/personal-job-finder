import json
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase, override_settings

from tracker.models import JobPosting

from .greenhouse import (
    GreenhouseDiscoveryConfigurationError,
    GreenhouseDiscoveryProvider,
    greenhouse_html_to_text,
)
from .models import DiscoveryRun, DiscoverySourceAttempt, RawJobOpportunity
from .providers import DiscoveryQuery
from .services import run_discovery


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def greenhouse_job(job_id, *, title="Test Engineer", updated_at="2026-07-23T10:00:00Z"):
    return {
        "id": job_id,
        "internal_job_id": job_id + 1000,
        "title": title,
        "updated_at": updated_at,
        "absolute_url": f"https://example.org/careers/{job_id}",
        "location": {"name": "Philadelphia, PA"},
        "language": "en",
        "content": (
            "<h2>Role</h2><p>Execute verification and validation testing for "
            "medical electrical equipment.</p><ul><li>Python</li><li>IEC 60601</li></ul>"
        ),
        "departments": [{"id": 1, "name": "Engineering"}],
        "offices": [{"id": 2, "name": "Philadelphia Lab"}],
        "metadata": [{"name": "Employment Type", "value": "Full-time"}],
    }


GREENHOUSE_BOARDS = [
    {
        "key": "northstar",
        "label": "Northstar Medical",
        "board_token": "northstar-medical",
        "industry_hint": "Medical devices",
        "enabled": True,
    }
]


class GreenhouseProviderTests(TestCase):
    def test_html_normalization_preserves_readable_structure(self):
        text = greenhouse_html_to_text(
            "<h2>Qualifications</h2><p>Electrical engineering &amp; testing.</p>"
            "<ul><li>Python</li><li>MATLAB</li></ul>"
        )

        self.assertIn("Qualifications", text)
        self.assertIn("Electrical engineering & testing.", text)
        self.assertIn("- Python", text)
        self.assertIn("- MATLAB", text)
        self.assertNotIn("<p>", text)

    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=False,
        GREENHOUSE_DISCOVERY_BOARDS=GREENHOUSE_BOARDS,
    )
    def test_live_network_requires_explicit_switch(self):
        provider = GreenhouseDiscoveryProvider()

        with self.assertRaises(GreenhouseDiscoveryConfigurationError):
            tuple(provider.discover(DiscoveryQuery()))

    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=True,
        GREENHOUSE_DISCOVERY_BOARDS=GREENHOUSE_BOARDS,
        GREENHOUSE_DISCOVERY_RETRY_COUNT=0,
        GREENHOUSE_DISCOVERY_MAX_JOBS_PER_BOARD=10,
    )
    @patch("job_discovery.greenhouse.urlopen")
    def test_provider_uses_read_only_content_endpoint_and_preserves_provenance(
        self,
        urlopen_mock,
    ):
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"jobs": [greenhouse_job(101)], "meta": {"total": 1}})

        urlopen_mock.side_effect = open_request
        provider = GreenhouseDiscoveryProvider()
        opportunities = tuple(provider.discover(DiscoveryQuery()))

        self.assertEqual(len(opportunities), 1)
        request = captured["request"]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/boards/northstar-medical/jobs?content=true", request.full_url)
        self.assertNotIn("applications", request.full_url)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.external_id, "northstar:101")
        self.assertEqual(opportunity.company_hint, "Northstar Medical")
        self.assertIn("Execute verification", opportunity.raw_listing_text)
        self.assertEqual(
            opportunity.metadata["raw_content_html"],
            greenhouse_job(101)["content"],
        )
        self.assertEqual(provider.source_reports[0]["status"], "success")
        self.assertEqual(
            provider.source_reports[0]["metadata"]["external_ids"],
            ["northstar:101"],
        )

    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=True,
        GREENHOUSE_DISCOVERY_BOARDS=GREENHOUSE_BOARDS,
        GREENHOUSE_DISCOVERY_RETRY_COUNT=0,
        GREENHOUSE_DISCOVERY_MAX_JOBS_PER_BOARD=1,
    )
    @patch("job_discovery.greenhouse.urlopen")
    def test_per_board_job_limit_prefers_most_recent_updates(self, urlopen_mock):
        urlopen_mock.return_value = FakeResponse(
            {
                "jobs": [
                    greenhouse_job(1, title="Older", updated_at="2026-07-01T10:00:00Z"),
                    greenhouse_job(2, title="Newer", updated_at="2026-07-22T10:00:00Z"),
                ],
                "meta": {"total": 2},
            }
        )

        opportunities = tuple(GreenhouseDiscoveryProvider().discover(DiscoveryQuery()))

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].title_hint, "Newer")


class GreenhouseRunTests(TestCase):
    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=True,
        GREENHOUSE_DISCOVERY_BOARDS=[
            *GREENHOUSE_BOARDS,
            {
                "key": "clearpath",
                "label": "ClearPath Diagnostics",
                "board_token": "clearpath-diagnostics",
                "industry_hint": "Medical devices",
                "enabled": True,
            },
        ],
        GREENHOUSE_DISCOVERY_RETRY_COUNT=0,
    )
    @patch("job_discovery.greenhouse.urlopen")
    def test_partial_board_failure_preserves_successes_and_attempts(self, urlopen_mock):
        urlopen_mock.side_effect = [
            FakeResponse({"jobs": [greenhouse_job(10)], "meta": {"total": 1}}),
            URLError("temporary board failure"),
        ]

        run = run_discovery(GreenhouseDiscoveryProvider.key)

        self.assertEqual(run.status, DiscoveryRun.Status.PARTIAL)
        self.assertEqual(run.result_count, 1)
        self.assertEqual(run.opportunities.count(), 1)
        self.assertEqual(run.source_attempts.count(), 2)
        self.assertEqual(
            run.source_attempts.filter(status=DiscoverySourceAttempt.Status.SUCCESS).count(),
            1,
        )
        failed = run.source_attempts.get(status=DiscoverySourceAttempt.Status.FAILED)
        self.assertIn("temporary board failure", failed.error_message)
        self.assertEqual(JobPosting.objects.count(), 0)

    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=True,
        GREENHOUSE_DISCOVERY_BOARDS=GREENHOUSE_BOARDS,
        GREENHOUSE_DISCOVERY_RETRY_COUNT=0,
    )
    @patch("job_discovery.greenhouse.urlopen")
    def test_successful_refresh_marks_disappeared_listing_closed(self, urlopen_mock):
        urlopen_mock.side_effect = [
            FakeResponse(
                {
                    "jobs": [greenhouse_job(1), greenhouse_job(2, title="Quality Engineer")],
                    "meta": {"total": 2},
                }
            ),
            FakeResponse({"jobs": [greenhouse_job(1)], "meta": {"total": 1}}),
        ]

        first_run = run_discovery(GreenhouseDiscoveryProvider.key)
        second_run = run_discovery(GreenhouseDiscoveryProvider.key)

        disappeared = first_run.opportunities.get(external_id="northstar:2")
        disappeared.refresh_from_db()
        self.assertFalse(disappeared.source_is_active)
        self.assertIsNotNone(disappeared.source_closed_at)

        prior_still_open = first_run.opportunities.get(external_id="northstar:1")
        prior_still_open.refresh_from_db()
        self.assertFalse(prior_still_open.source_is_active)
        self.assertIsNone(prior_still_open.source_closed_at)

        latest = second_run.opportunities.get(external_id="northstar:1")
        self.assertTrue(latest.source_is_active)
        self.assertIsNone(latest.source_closed_at)
        self.assertEqual(latest.status, RawJobOpportunity.Status.DUPLICATE)

    @override_settings(
        JOB_DISCOVERY_LIVE_ENABLED=True,
        GREENHOUSE_DISCOVERY_BOARDS=GREENHOUSE_BOARDS,
        GREENHOUSE_DISCOVERY_RETRY_COUNT=0,
    )
    @patch("job_discovery.greenhouse.urlopen")
    def test_failed_refresh_does_not_mark_previous_listing_closed(self, urlopen_mock):
        urlopen_mock.side_effect = [
            FakeResponse({"jobs": [greenhouse_job(1)], "meta": {"total": 1}}),
            URLError("board unavailable"),
        ]

        first_run = run_discovery(GreenhouseDiscoveryProvider.key)
        failed_run = run_discovery(GreenhouseDiscoveryProvider.key)

        self.assertEqual(failed_run.status, DiscoveryRun.Status.FAILED)
        opportunity = first_run.opportunities.get(external_id="northstar:1")
        opportunity.refresh_from_db()
        self.assertTrue(opportunity.source_is_active)
        self.assertIsNone(opportunity.source_closed_at)
        self.assertEqual(failed_run.source_attempts.count(), 1)
        self.assertEqual(
            failed_run.source_attempts.get().status,
            DiscoverySourceAttempt.Status.FAILED,
        )
