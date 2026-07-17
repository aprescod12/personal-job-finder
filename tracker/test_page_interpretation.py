from datetime import date

from django.test import TestCase

from .models import JobPosting, ListingVerificationRun
from .services.page_interpretation import EmployerPageInterpreter
from .services.page_retrieval import RetrievedPage


def page(
    body: str,
    *,
    url: str = "https://careers.example.com/jobs/embedded-software-engineer",
    status: int = 200,
    content_type: str = "text/html",
) -> RetrievedPage:
    return RetrievedPage(
        requested_url=url,
        final_url=url,
        status_code=status,
        content_type=content_type,
        charset="utf-8",
        bytes_read=len(body.encode()),
        body_sha256="b" * 64,
        body_text=body,
        body_stored=True,
        response_headers={"content_type": content_type},
    )


class EmployerPageInterpreterTests(TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Embedded Software Engineer",
            company="Example Medical",
            job_url="https://careers.example.com/jobs/embedded-software-engineer",
        )
        self.interpreter = EmployerPageInterpreter()
        self.today = date(2026, 7, 17)

    def test_matching_structured_job_and_apply_action_is_open(self):
        html = """
            <html>
              <head>
                <title>Embedded Software Engineer | Example Medical Careers</title>
                <meta property="og:site_name" content="Example Medical">
                <script type="application/ld+json">
                  {
                    "@context": "https://schema.org",
                    "@type": "JobPosting",
                    "title": "Embedded Software Engineer",
                    "hiringOrganization": {"@type": "Organization", "name": "Example Medical"},
                    "validThrough": "2026-08-31",
                    "directApply": true,
                    "url": "https://careers.example.com/jobs/embedded-software-engineer"
                  }
                </script>
              </head>
              <body>
                <h1>Embedded Software Engineer</h1>
                <p>Join Example Medical and build connected medical devices.</p>
                <a href="/jobs/embedded-software-engineer/apply">Apply now</a>
              </body>
            </html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(result.detected_listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(result.detected_job_title, self.job.title)
        self.assertEqual(result.detected_company, self.job.company)
        self.assertTrue(result.apply_action_found)
        self.assertEqual(
            result.detected_deadline_status,
            JobPosting.DeadlineStatus.CONFIRMED,
        )
        self.assertEqual(result.detected_deadline, date(2026, 8, 31))
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.HIGH)
        self.assertTrue(result.structured_evidence["json_ld_role_match"])
        self.assertTrue(result.structured_evidence["json_ld_company_match"])

    def test_explicit_closed_message_marks_matching_role_closed(self):
        html = """
            <html><head><title>Embedded Software Engineer | Example Medical</title></head>
            <body>
              <h1>Embedded Software Engineer</h1>
              <p>Example Medical</p>
              <p>This job is no longer available and we are no longer accepting applications.</p>
            </body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(result.detected_listing_status, JobPosting.ListingStatus.CLOSED)
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.HIGH)
        self.assertIn(
            "this job is no longer available",
            result.structured_evidence["closed_signals"],
        )

    def test_passed_structured_deadline_marks_role_expired(self):
        html = """
            <html><head><title>Embedded Software Engineer</title>
            <meta property="og:site_name" content="Example Medical">
            <script type="application/ld+json">
              {
                "@type": "JobPosting",
                "title": "Embedded Software Engineer",
                "hiringOrganization": {"name": "Example Medical"},
                "validThrough": "2026-07-01"
              }
            </script></head>
            <body><h1>Embedded Software Engineer</h1><p>Example Medical</p></body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(result.detected_listing_status, JobPosting.ListingStatus.EXPIRED)
        self.assertEqual(result.detected_deadline, date(2026, 7, 1))
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.HIGH)

    def test_http_404_without_closure_evidence_is_broken_link(self):
        html = "<html><title>Page not found</title><body>We could not find that page.</body></html>"

        result = self.interpreter.interpret(
            self.job,
            page(html, status=404),
            today=self.today,
        )

        self.assertEqual(
            result.detected_listing_status,
            JobPosting.ListingStatus.LINK_BROKEN,
        )
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.HIGH)

    def test_generic_careers_redirect_without_role_match_is_wrong_page(self):
        html = """
            <html><head><title>Careers at Example Medical</title></head>
            <body>
              <h1>Career opportunities</h1>
              <p>Example Medical</p>
              <a href="/jobs">Search all jobs</a>
              <a href="/talent">Join our talent community</a>
            </body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html, url="https://careers.example.com/careers"),
            today=self.today,
        )

        self.assertEqual(
            result.detected_listing_status,
            JobPosting.ListingStatus.WRONG_PAGE,
        )
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.MEDIUM)
        self.assertTrue(result.structured_evidence["wrong_page_signals"])

    def test_generic_apply_link_does_not_make_unrelated_page_open(self):
        html = """
            <html><head><title>Senior Finance Manager | Example Medical</title></head>
            <body>
              <h1>Senior Finance Manager</h1>
              <p>Example Medical</p>
              <a href="/jobs/finance-manager/apply">Apply now</a>
            </body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html, url="https://careers.example.com/jobs/finance-manager"),
            today=self.today,
        )

        self.assertNotEqual(result.detected_listing_status, JobPosting.ListingStatus.OPEN)
        self.assertEqual(
            result.detected_listing_status,
            JobPosting.ListingStatus.WRONG_PAGE,
        )
        self.assertTrue(result.apply_action_found)

    def test_matching_page_without_application_evidence_remains_unverified(self):
        html = """
            <html><head><title>Embedded Software Engineer | Example Medical</title></head>
            <body><h1>Embedded Software Engineer</h1><p>Example Medical</p></body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(
            result.detected_listing_status,
            JobPosting.ListingStatus.UNVERIFIED,
        )
        self.assertEqual(result.confidence, ListingVerificationRun.Confidence.LOW)
        self.assertFalse(result.apply_action_found)

    def test_text_deadline_is_extracted(self):
        html = """
            <html><head><title>Embedded Software Engineer | Example Medical</title></head>
            <body>
              <h1>Embedded Software Engineer</h1><p>Example Medical</p>
              <p>Application deadline: August 15, 2026.</p>
              <a href="/apply">Apply now</a>
            </body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(
            result.detected_deadline_status,
            JobPosting.DeadlineStatus.CONFIRMED,
        )
        self.assertEqual(result.detected_deadline, date(2026, 8, 15))
        self.assertTrue(result.structured_evidence["deadline_evidence"])

    def test_rolling_deadline_phrase_is_preserved(self):
        html = """
            <html><head><title>Embedded Software Engineer | Example Medical</title></head>
            <body>
              <h1>Embedded Software Engineer</h1><p>Example Medical</p>
              <p>This position is open until filled.</p>
              <a href="/apply">Apply now</a>
            </body></html>
        """

        result = self.interpreter.interpret(
            self.job,
            page(html),
            today=self.today,
        )

        self.assertEqual(
            result.detected_deadline_status,
            JobPosting.DeadlineStatus.ROLLING,
        )
        self.assertIsNone(result.detected_deadline)

    def test_plain_text_page_can_be_interpreted(self):
        text = (
            "Embedded Software Engineer at Example Medical. "
            "This job is no longer available."
        )

        result = self.interpreter.interpret(
            self.job,
            page(text, content_type="text/plain"),
            today=self.today,
        )

        self.assertEqual(result.detected_listing_status, JobPosting.ListingStatus.CLOSED)
