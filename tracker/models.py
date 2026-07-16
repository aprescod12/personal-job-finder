from django.db import models


class JobPosting(models.Model):
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
    next_action = models.CharField(max_length=300, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} at {self.company}"


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
