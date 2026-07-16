from django import forms

from .models import JobPosting


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            "title",
            "company",
            "location",
            "job_url",
            "source",
            "employment_type",
            "work_arrangement",
            "salary_text",
            "date_posted",
            "application_deadline",
            "status",
            "next_action",
            "next_action_date",
            "description",
            "notes",
        ]
        widgets = {
            "date_posted": forms.DateInput(attrs={"type": "date"}),
            "application_deadline": forms.DateInput(attrs={"type": "date"}),
            "next_action_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 10}),
            "notes": forms.Textarea(attrs={"rows": 5}),
        }
