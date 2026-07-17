from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class JobPosting(models.Model):
    VERIFICATION_MAX_AGE_DAYS = 7

    class Status(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        SAVED = "saved", "Saved"
        PREPARING = "preparing", "Preparing application"
        APPLIED = "applied", "Applied"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CLOSED = "closed", "Closed"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"
        TEMPORARY = "temporary", "Temporary"
        UNKNOWN = "unknown", "Unknown"

    class WorkArrangement(models.TextChoices):
        ONSITE = "onsite", "On-site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"
        UNKNOWN = "unknown", "Unknown"

    class ListingStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed by employer"
        EXPIRED = "expired", "Expired"
        LINK_BROKEN = "link_broken", "Broken link"
        WRONG_PAGE = "wrong_page", "Wrong company page"

    class DeadlineStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        CONFIRMED = "confirmed", "Confirmed date"
        ROLLING = "rolling", "Rolling / open until filled"
        NOT_STATED = "not_stated", "No deadline stated"

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    job_url = models.URLField(max_length=1000, blank=True)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DISCOVERED,
    )
    source = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.UNKNOWN,
    )
    work_arrangement = models.CharField(
        max_length=20,
        choices=WorkArrangement.choices,
        default=WorkArrangement.UNKNOWN,
    )
    salary_text = models.CharField(max_length=200, blank=True)
    date_posted = models.DateField(null=True, blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    deadline_status = models.CharField(
        max_length=20,
        choices=DeadlineStatus.choices,
        default=DeadlineStatus.UNKNOWN,
    )
    listing_status = models.CharField(
        max_length=20,
        choices=ListingStatus.choices,
        default=ListingStatus.UNVERIFIED,
    )
    listing_last_verified = models.DateField(null=True, blank=True)
    listing_verification_notes = models.TextField(blank=True)
    next_action = models.CharField(max_length=300, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if (
            self.deadline_status == self.DeadlineStatus.CONFIRMED
            and not self.application_deadline
        ):
            raise ValidationError(
                {
                    "application_deadline": (
                        "Enter the confirmed application deadline."
                    )
                }
            )
        if (
            self.date_posted
            and self.application_deadline
            and self.application_deadline < self.date_posted
        ):
            raise ValidationError(
                {
                    "application_deadline": (
                        "Application deadline cannot be earlier than the posting date."
                    )
                }
            )

    @property
    def deadline_days_remaining(self):
        if (
            self.deadline_status != self.DeadlineStatus.CONFIRMED
            or not self.application_deadline
        ):
            return None
        return (self.application_deadline - timezone.localdate()).days

    @property
    def deadline_is_overdue(self):
        days = self.deadline_days_remaining
        return days is not None and days < 0

    @property
    def deadline_is_due_soon(self):
        days = self.deadline_days_remaining
        return days is not None and 0 <= days <= 7

    @property
    def deadline_label(self):
        if (
            self.deadline_status == self.DeadlineStatus.CONFIRMED
            and self.application_deadline
        ):
            days = self.deadline_days_remaining
            if days is not None and days < 0:
                return f"Expired {abs(days)} day{'s' if abs(days) != 1 else ''} ago"
            if days == 0:
                return "Deadline today"
            if days == 1:
                return "Deadline tomorrow"
            return f"Deadline in {days} days"
        return self.get_deadline_status_display()

    @property
    def effective_listing_status(self):
        if (
            self.deadline_is_overdue
            and self.listing_status
            in {self.ListingStatus.OPEN, self.ListingStatus.UNVERIFIED}
        ):
            return self.ListingStatus.EXPIRED
        return self.listing_status

    @property
    def effective_listing_status_label(self):
        return dict(self.ListingStatus.choices).get(
            self.effective_listing_status,
            "Unverified",
        )

    @property
    def listing_is_available(self):
        return self.effective_listing_status == self.ListingStatus.OPEN

    @property
    def listing_has_link_problem(self):
        return self.effective_listing_status in {
            self.ListingStatus.LINK_BROKEN,
            self.ListingStatus.WRONG_PAGE,
        }

    @property
    def listing_is_unavailable(self):
        return self.effective_listing_status in {
            self.ListingStatus.CLOSED,
            self.ListingStatus.EXPIRED,
            self.ListingStatus.LINK_BROKEN,
            self.ListingStatus.WRONG_PAGE,
        }

    @property
    def listing_needs_verification(self):
        status = self.effective_listing_status
        if status == self.ListingStatus.UNVERIFIED:
            return True
        if status != self.ListingStatus.OPEN:
            return False
        if self.deadline_status == self.DeadlineStatus.UNKNOWN:
            return True
        if not self.listing_last_verified:
            return True
        oldest_acceptable = timezone.localdate() - timedelta(
            days=self.VERIFICATION_MAX_AGE_DAYS
        )
        return self.listing_last_verified < oldest_acceptable

    def __str__(self):
        return f"{self.title} at {self.company}"


class JobRequirement(models.Model):
    class SeniorityLevel(models.TextChoices):
        UNKNOWN = "unknown", "Not specified"
        INTERNSHIP = "internship", "Internship / student"
        ENTRY_LEVEL = "entry_level", "Entry level"
        EARLY_CAREER = "early_career", "Early career"
        MID_LEVEL = "mid_level", "Mid level"
        SENIOR = "senior", "Senior"
        LEAD_MANAGER = "lead_manager", "Lead / manager"

    job = models.OneToOneField(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    role_family = models.CharField(max_length=200, blank=True)
    seniority_level = models.CharField(
        max_length=20,
        choices=SeniorityLevel.choices,
        default=SeniorityLevel.UNKNOWN,
    )
    industry = models.CharField(max_length=200, blank=True)

    required_skills = models.TextField(
        blank=True,
        help_text="Enter one required skill per line.",
    )
    preferred_skills = models.TextField(
        blank=True,
        help_text="Enter one preferred skill per line.",
    )
    required_education = models.TextField(
        blank=True,
        help_text="Enter one acceptable required degree or field per line.",
    )
    preferred_education = models.TextField(
        blank=True,
        help_text="Enter one preferred degree or field per line.",
    )
    minimum_years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    maximum_years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    responsibilities = models.TextField(
        blank=True,
        help_text="Enter one responsibility per line.",
    )
    certifications = models.TextField(
        blank=True,
        help_text="Enter one certification or standard per line.",
    )
    work_authorization_requirements = models.TextField(blank=True)
    hard_disqualifiers = models.TextField(
        blank=True,
        help_text="Enter one explicit blocker per line.",
    )
    requirement_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "job requirement set"
        verbose_name_plural = "job requirement sets"

    def clean(self):
        super().clean()
        if (
            self.minimum_years_experience is not None
            and self.maximum_years_experience is not None
            and self.maximum_years_experience < self.minimum_years_experience
        ):
            raise ValidationError(
                {
                    "maximum_years_experience": (
                        "Maximum experience cannot be lower than minimum experience."
                    )
                }
            )

    @property
    def has_content(self):
        text_fields = (
            self.role_family,
            self.industry,
            self.required_skills,
            self.preferred_skills,
            self.required_education,
            self.preferred_education,
            self.responsibilities,
            self.certifications,
            self.work_authorization_requirements,
            self.hard_disqualifiers,
            self.requirement_notes,
        )
        return bool(
            any(value.strip() for value in text_fields)
            or self.seniority_level != self.SeniorityLevel.UNKNOWN
            or self.minimum_years_experience is not None
            or self.maximum_years_experience is not None
        )

    @property
    def experience_range(self):
        minimum = self.minimum_years_experience
        maximum = self.maximum_years_experience

        if minimum is not None and maximum is not None:
            return f"{minimum}–{maximum} years"
        if minimum is not None:
            return f"{minimum}+ years"
        if maximum is not None:
            return f"Up to {maximum} years"
        return "Not specified"

    def __str__(self):
        return f"Requirements for {self.job}"


class JobCalibration(models.Model):
    class HumanRating(models.TextChoices):
        STRONG = "strong", "Strong match"
        GOOD = "good", "Good match"
        POSSIBLE = "possible", "Possible match"
        WEAK = "weak", "Weak match"
        NOT_ELIGIBLE = "not_eligible", "Not eligible"

    class OpportunityType(models.TextChoices):
        PRIORITY = "priority", "Priority role"
        ADJACENT = "adjacent", "Adjacent opportunity"
        OUTSIDE = "outside", "Outside current priority"
        UNSURE = "unsure", "Unsure"

    PREDICTED_RATING_MAP = {
        "STRONG MATCH": HumanRating.STRONG,
        "GOOD MATCH": HumanRating.GOOD,
        "POSSIBLE MATCH": HumanRating.POSSIBLE,
        "WEAK MATCH": HumanRating.WEAK,
        "DISQUALIFIED": HumanRating.NOT_ELIGIBLE,
    }

    job = models.OneToOneField(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="calibration",
    )
    human_rating = models.CharField(
        max_length=20,
        choices=HumanRating.choices,
    )
    opportunity_type = models.CharField(
        max_length=20,
        choices=OpportunityType.choices,
        default=OpportunityType.UNSURE,
    )
    notes = models.TextField(blank=True)

    predicted_score = models.PositiveSmallIntegerField(null=True, blank=True)
    predicted_classification = models.CharField(max_length=40, blank=True)
    predicted_track = models.CharField(max_length=40, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "job calibration"
        verbose_name_plural = "job calibrations"

    @property
    def predicted_human_rating(self):
        return self.PREDICTED_RATING_MAP.get(self.predicted_classification, "")

    @property
    def agreement_status(self):
        predicted = self.predicted_human_rating
        if not predicted:
            return "NEEDS EVIDENCE"
        if predicted == self.human_rating:
            return "ALIGNED"
        return "REVIEW"

    @property
    def agreement_label(self):
        labels = {
            "ALIGNED": "Matcher agrees with your judgment",
            "REVIEW": "Matcher and your judgment differ",
            "NEEDS EVIDENCE": "Matcher needs more evidence",
        }
        return labels[self.agreement_status]

    def __str__(self):
        return f"Calibration for {self.job}"


class CareerProfile(models.Model):
    class ExperienceLevel(models.TextChoices):
        ENTRY_LEVEL = "entry_level", "Entry level"
        EARLY_CAREER = "early_career", "Early career (1–3 years)"
        MID_LEVEL = "mid_level", "Mid level"
        SENIOR = "senior", "Senior"

    class PreferredWorkArrangement(models.TextChoices):
        FLEXIBLE = "flexible", "Flexible"
        ONSITE = "onsite", "On-site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    full_name = models.CharField(max_length=200, default="Amiri Prescod")
    professional_headline = models.CharField(max_length=300, blank=True)
    education_summary = models.TextField(blank=True)

    target_roles = models.TextField(
        blank=True,
        help_text="Enter one target role per line.",
    )
    target_industries = models.TextField(
        blank=True,
        help_text="Enter one preferred industry per line.",
    )
    skills = models.TextField(
        blank=True,
        help_text="Enter one skill per line.",
    )

    experience_level = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.ENTRY_LEVEL,
    )
    preferred_locations = models.TextField(
        blank=True,
        help_text="Enter one acceptable location per line.",
    )
    preferred_work_arrangement = models.CharField(
        max_length=20,
        choices=PreferredWorkArrangement.choices,
        default=PreferredWorkArrangement.FLEXIBLE,
    )
    preferred_employment_type = models.CharField(
        max_length=20,
        choices=JobPosting.EmploymentType.choices,
        default=JobPosting.EmploymentType.FULL_TIME,
    )
    minimum_salary = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional minimum annual salary in U.S. dollars.",
    )
    work_authorization = models.CharField(max_length=300, blank=True)

    priorities = models.TextField(
        blank=True,
        help_text="Enter one priority per line.",
    )
    deal_breakers = models.TextField(
        blank=True,
        help_text="Enter one non-negotiable or disqualifier per line.",
    )
    additional_context = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "career profile"
        verbose_name_plural = "career profile"

    @classmethod
    def get_solo(cls):
        profile, _ = cls.objects.get_or_create(pk=1)
        return profile

    def __str__(self):
        return f"{self.full_name}'s career profile"
