from django import forms
from django.db import transaction

from .forms import normalize_line_list
from .models import JobPosting, JobRequirement


class JobIntakePasteForm(forms.Form):
    source_url = forms.URLField(
        required=False,
        max_length=1000,
        label="Direct job URL",
        help_text="Optional. Paste the exact employer role URL when you have it.",
    )
    source_label = forms.CharField(
        required=False,
        max_length=100,
        label="Source",
        help_text="Examples: Company website, Handshake, LinkedIn, referral.",
    )
    raw_text = forms.CharField(
        label="Job listing text",
        min_length=40,
        widget=forms.Textarea(
            attrs={
                "rows": 22,
                "placeholder": (
                    "Paste the complete job listing here. Include the title, company, "
                    "location, responsibilities, qualifications, and deadline when available."
                ),
            }
        ),
    )


class JobIntakeReviewForm(forms.Form):
    LIST_FIELDS = (
        "required_skills",
        "preferred_skills",
        "required_education",
        "preferred_education",
        "responsibilities",
        "certifications",
        "work_authorization_requirements",
        "hard_disqualifiers",
    )

    title = forms.CharField(max_length=200)
    company = forms.CharField(max_length=200)
    location = forms.CharField(max_length=200, required=False)
    job_url = forms.URLField(max_length=1000, required=False, label="Direct company job URL")
    source = forms.CharField(max_length=100, required=False)
    employment_type = forms.ChoiceField(choices=JobPosting.EmploymentType.choices)
    work_arrangement = forms.ChoiceField(choices=JobPosting.WorkArrangement.choices)
    deadline_status = forms.ChoiceField(choices=JobPosting.DeadlineStatus.choices)
    application_deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    next_action = forms.CharField(max_length=300, required=False)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12}),
    )

    role_family = forms.CharField(max_length=200, required=False)
    seniority_level = forms.ChoiceField(choices=JobRequirement.SeniorityLevel.choices)
    industry = forms.CharField(max_length=200, required=False)
    required_skills = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 7}))
    preferred_skills = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 6}))
    required_education = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    preferred_education = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    minimum_years_experience = forms.IntegerField(required=False, min_value=0, max_value=60)
    maximum_years_experience = forms.IntegerField(required=False, min_value=0, max_value=60)
    responsibilities = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 7}))
    certifications = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    work_authorization_requirements = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    hard_disqualifiers = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    requirement_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def clean(self):
        cleaned_data = super().clean()
        deadline = cleaned_data.get("application_deadline")
        deadline_status = cleaned_data.get("deadline_status")

        if deadline and deadline_status != JobPosting.DeadlineStatus.CONFIRMED:
            cleaned_data["deadline_status"] = JobPosting.DeadlineStatus.CONFIRMED
        elif deadline_status == JobPosting.DeadlineStatus.CONFIRMED and not deadline:
            self.add_error("application_deadline", "Enter the confirmed application deadline.")

        minimum = cleaned_data.get("minimum_years_experience")
        maximum = cleaned_data.get("maximum_years_experience")
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error(
                "maximum_years_experience",
                "Maximum experience cannot be lower than minimum experience.",
            )

        for field_name in self.LIST_FIELDS:
            cleaned_data[field_name] = normalize_line_list(cleaned_data.get(field_name, ""))

        return cleaned_data

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        job = JobPosting.objects.create(
            title=data["title"],
            company=data["company"],
            location=data.get("location", ""),
            job_url=data.get("job_url", ""),
            source=data.get("source", ""),
            employment_type=data["employment_type"],
            work_arrangement=data["work_arrangement"],
            deadline_status=data["deadline_status"],
            application_deadline=data.get("application_deadline"),
            status=JobPosting.Status.SAVED,
            listing_status=JobPosting.ListingStatus.UNVERIFIED,
            next_action=data.get("next_action", ""),
            description=data.get("description", ""),
            notes=(
                "Created from a reviewed Stage 4 intake draft. "
                "Listing availability and extracted requirements still require human verification."
            ),
        )
        JobRequirement.objects.create(
            job=job,
            role_family=data.get("role_family", ""),
            seniority_level=data["seniority_level"],
            industry=data.get("industry", ""),
            required_skills=data.get("required_skills", ""),
            preferred_skills=data.get("preferred_skills", ""),
            required_education=data.get("required_education", ""),
            preferred_education=data.get("preferred_education", ""),
            minimum_years_experience=data.get("minimum_years_experience"),
            maximum_years_experience=data.get("maximum_years_experience"),
            responsibilities=data.get("responsibilities", ""),
            certifications=data.get("certifications", ""),
            work_authorization_requirements=data.get("work_authorization_requirements", ""),
            hard_disqualifiers=data.get("hard_disqualifiers", ""),
            requirement_notes=data.get("requirement_notes", ""),
        )
        return job
