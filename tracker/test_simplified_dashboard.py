from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import JobPosting


class SimplifiedDashboardTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical",
            location="Philadelphia, PA",
            job_url="https://careers.example.com/jobs/123",
            listing_status=JobPosting.ListingStatus.OPEN,
            listing_last_verified=timezone.localdate(),
            deadline_status=JobPosting.DeadlineStatus.NOT_STATED,
            next_action="Tailor resume",
        )

    @patch("tracker.views.analyze_job_match")
    def test_dashboard_keeps_large_match_score_and_compact_priorities(self, analyze):
        analyze.return_value = SimpleNamespace(
            has_requirements=True,
            classification="GOOD MATCH",
            track="PRIORITY ROLE",
            score=87,
            evidence_coverage=82,
            is_disqualified=False,
        )

        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "87")
        self.assertContains(response, "/100")
        self.assertContains(response, "GOOD MATCH")
        self.assertContains(response, "PRIORITY ROLE")
        self.assertContains(response, "No deadline stated")
        self.assertContains(response, "Tailor resume")
        self.assertContains(response, "OPEN POSTING")
        self.assertContains(response, "ADVANCED FILTERS")

    @patch("tracker.views.analyze_job_match")
    def test_dashboard_removes_repeated_admin_panels_from_cards(self, analyze):
        analyze.return_value = SimpleNamespace(
            has_requirements=True,
            classification="STRONG MATCH",
            track="PRIORITY ROLE",
            score=92,
            evidence_coverage=90,
            is_disqualified=False,
        )

        response = self.client.get(reverse("job_list"))

        self.assertNotContains(response, "LISTING RELIABILITY")
        self.assertNotContains(response, "STRONG MATCHES")
        self.assertNotContains(response, "GOOD MATCHES")
        self.assertNotContains(response, "NOT CALIBRATED")
        self.assertNotContains(response, ">EDIT<", html=False)
