from django.core.exceptions import ValidationError
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
