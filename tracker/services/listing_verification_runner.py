from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from tracker.models import JobPosting, ListingVerificationRun


class VerificationAlreadyRunning(RuntimeError):
    def __init__(self, run: ListingVerificationRun):
        self.run = run
        super().__init__("A verification run is already active for this job.")


class VerificationInputError(ValueError):
    pass


@dataclass(frozen=True)
class VerificationObservation:
    status: str
    final_url: str = ""
    http_status_code: int | None = None
    detected_job_title: str = ""
    detected_company: str = ""
    detected_listing_status: str = JobPosting.ListingStatus.UNVERIFIED
    detected_deadline_status: str = JobPosting.DeadlineStatus.UNKNOWN
    detected_deadline: date | None = None
    apply_action_found: bool | None = None
    confidence: str = ListingVerificationRun.Confidence.UNKNOWN
    review_status: str = ListingVerificationRun.ReviewStatus.PENDING
    evidence: str = ""
    structured_evidence: dict[str, Any] = field(default_factory=dict)


class ListingVerifier(Protocol):
    version: str

    def verify(self, job: JobPosting) -> VerificationObservation:
        """Inspect one job and return a structured observation."""


class UrlReadinessVerifier:
    """Stage 3 Step 2 preflight.

    This verifier intentionally performs no network request. It confirms that the
    stored URL is structurally usable and records the exact evidence that the next
    verifier will need. Employer-page retrieval and content interpretation belong
    to later Stage 3 steps.
    """

    version = "3.2-url-readiness-v1"

    def verify(self, job: JobPosting) -> VerificationObservation:
        raw_url = (job.job_url or "").strip()
        if not raw_url:
            raise VerificationInputError(
                "Add a direct employer job URL before running verification."
            )

        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise VerificationInputError(
                "The saved job URL must be a complete http or https address."
            )

        return VerificationObservation(
            status=ListingVerificationRun.RunStatus.NEEDS_REVIEW,
            final_url="",
            confidence=ListingVerificationRun.Confidence.LOW,
            review_status=ListingVerificationRun.ReviewStatus.PENDING,
            evidence=(
                "The stored URL is structurally valid. Stage 3 Step 2 did not make "
                "a network request, follow redirects, or inspect the employer page. "
                "The listing still requires page-level verification."
            ),
            structured_evidence={
                "network_request_performed": False,
                "url_scheme": parsed.scheme,
                "url_host": parsed.hostname,
                "expected_job_title": job.title,
                "expected_company": job.company,
                "next_required_capability": "employer_page_retrieval",
            },
        )


def _terminal_statuses() -> set[str]:
    return {
        ListingVerificationRun.RunStatus.COMPLETED,
        ListingVerificationRun.RunStatus.NEEDS_REVIEW,
        ListingVerificationRun.RunStatus.FAILED,
    }


def _start_run(
    job: JobPosting,
    *,
    trigger: str,
    verifier_version: str,
) -> ListingVerificationRun:
    with transaction.atomic():
        locked_job = JobPosting.objects.select_for_update().get(pk=job.pk)
        active_run = locked_job.verification_runs.filter(
            status__in={
                ListingVerificationRun.RunStatus.PENDING,
                ListingVerificationRun.RunStatus.RUNNING,
            }
        ).first()
        if active_run:
            raise VerificationAlreadyRunning(active_run)

        run = ListingVerificationRun.objects.create(
            job=locked_job,
            trigger=trigger,
            status=ListingVerificationRun.RunStatus.PENDING,
            requested_url=locked_job.job_url,
            verifier_version=verifier_version,
        )
        run.status = ListingVerificationRun.RunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])
        return run


def _complete_run(
    run: ListingVerificationRun,
    observation: VerificationObservation,
) -> ListingVerificationRun:
    if observation.status not in _terminal_statuses() - {
        ListingVerificationRun.RunStatus.FAILED
    }:
        raise ValueError("A verifier must return a completed or review result.")

    run.status = observation.status
    run.final_url = observation.final_url
    run.http_status_code = observation.http_status_code
    run.detected_job_title = observation.detected_job_title
    run.detected_company = observation.detected_company
    run.detected_listing_status = observation.detected_listing_status
    run.detected_deadline_status = observation.detected_deadline_status
    run.detected_deadline = observation.detected_deadline
    run.apply_action_found = observation.apply_action_found
    run.confidence = observation.confidence
    run.review_status = observation.review_status
    run.evidence = observation.evidence
    run.structured_evidence = observation.structured_evidence
    run.error_message = ""
    run.completed_at = timezone.now()
    run.full_clean()
    run.save()
    return run


def _fail_run(run: ListingVerificationRun, exc: Exception) -> ListingVerificationRun:
    run.status = ListingVerificationRun.RunStatus.FAILED
    run.confidence = ListingVerificationRun.Confidence.UNKNOWN
    run.review_status = ListingVerificationRun.ReviewStatus.PENDING
    run.error_message = str(exc)[:2000]
    run.evidence = "The verification attempt did not produce a usable result."
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "confidence",
            "review_status",
            "error_message",
            "evidence",
            "completed_at",
        ]
    )
    return run


def run_listing_verification(
    job: JobPosting,
    *,
    verifier: ListingVerifier | None = None,
    trigger: str = ListingVerificationRun.Trigger.MANUAL,
) -> ListingVerificationRun:
    """Create and execute one auditable verification run.

    Results are stored on ``ListingVerificationRun`` only. This function never
    updates the current ``JobPosting`` listing status or deadline.
    """

    selected_verifier = verifier or UrlReadinessVerifier()
    run = _start_run(
        job,
        trigger=trigger,
        verifier_version=selected_verifier.version,
    )

    try:
        observation = selected_verifier.verify(run.job)
        return _complete_run(run, observation)
    except Exception as exc:  # The run must preserve all verifier failures.
        return _fail_run(run, exc)
