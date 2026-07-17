from django import forms
from django.utils import timezone

from .forms import DeadlineValidationMixin
from .models import JobPosting, ListingVerificationRun


class VerificationReviewForm(DeadlineValidationMixin, forms.Form):
    job_url = forms.URLField(
        required=False,
        max_length=1000,
        label="Direct company job URL",
        help_text="Use the exact employer role page when one is available.",
    )
    listing_status = forms.ChoiceField(
        choices=JobPosting.ListingStatus.choices,
        label="Reviewed listing status",
    )
    deadline_status = forms.ChoiceField(
        choices=JobPosting.DeadlineStatus.choices,
        label="Reviewed deadline status",
    )
    application_deadline = forms.DateField(
        required=False,
        label="Confirmed application deadline",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    listing_verification_notes = forms.CharField(
        required=False,
        label="Review evidence and notes",
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": (
                    "Example: Opened the employer page manually. The exact role is still "
                    "available and applications are accepted on a rolling basis."
                ),
            }
        ),
    )

    def __init__(self, *args, job: JobPosting, run: ListingVerificationRun, **kwargs):
        self.job = job
        self.run = run
        kwargs.setdefault("initial", self._initial_values(job, run))
        super().__init__(*args, **kwargs)

    @staticmethod
    def _initial_values(job: JobPosting, run: ListingVerificationRun) -> dict:
        use_detected_result = (
            run.status != ListingVerificationRun.RunStatus.FAILED
            and run.review_status == ListingVerificationRun.ReviewStatus.PENDING
            and run.detected_listing_status != JobPosting.ListingStatus.UNVERIFIED
        )

        if use_detected_result:
            listing_status = run.detected_listing_status
            deadline_status = run.detected_deadline_status
            deadline = run.detected_deadline
            notes = run.evidence
        else:
            listing_status = job.listing_status
            deadline_status = job.deadline_status
            deadline = job.application_deadline
            notes = job.listing_verification_notes

        return {
            "job_url": run.final_url or job.job_url,
            "listing_status": listing_status,
            "deadline_status": deadline_status,
            "application_deadline": deadline,
            "listing_verification_notes": notes,
        }

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("listing_status") == JobPosting.ListingStatus.OPEN
            and not cleaned_data.get("job_url")
        ):
            self.add_error(
                "job_url",
                "An open listing needs a direct employer job URL.",
            )
        return cleaned_data

    def apply_to_job(self) -> JobPosting:
        if not self.is_valid():
            raise ValueError("Cannot apply an invalid verification review.")

        self.job.job_url = self.cleaned_data["job_url"]
        self.job.listing_status = self.cleaned_data["listing_status"]
        self.job.deadline_status = self.cleaned_data["deadline_status"]
        self.job.application_deadline = self.cleaned_data["application_deadline"]
        self.job.listing_verification_notes = self.cleaned_data[
            "listing_verification_notes"
        ]
        self.job.listing_last_verified = timezone.localdate()
        self.job.save(
            update_fields=[
                "job_url",
                "listing_status",
                "deadline_status",
                "application_deadline",
                "listing_verification_notes",
                "listing_last_verified",
                "updated_at",
            ]
        )
        return self.job
