from django import forms

from .models import CareerProfile, JobPosting


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


class CareerProfileForm(forms.ModelForm):
    LIST_FIELDS = (
        "target_roles",
        "target_industries",
        "skills",
        "preferred_locations",
        "priorities",
        "deal_breakers",
    )

    class Meta:
        model = CareerProfile
        fields = [
            "full_name",
            "professional_headline",
            "education_summary",
            "target_roles",
            "target_industries",
            "skills",
            "experience_level",
            "preferred_locations",
            "preferred_work_arrangement",
            "preferred_employment_type",
            "minimum_salary",
            "work_authorization",
            "priorities",
            "deal_breakers",
            "additional_context",
        ]
        labels = {
            "professional_headline": "Professional headline",
            "education_summary": "Education",
            "preferred_work_arrangement": "Preferred work arrangement",
            "preferred_employment_type": "Preferred employment type",
            "minimum_salary": "Minimum annual salary",
            "work_authorization": "Work authorization or sponsorship needs",
            "additional_context": "Additional context",
        }
        widgets = {
            "professional_headline": forms.TextInput(
                attrs={
                    "placeholder": "Electrical Engineer | M.S. Biomedical Engineering Candidate"
                }
            ),
            "education_summary": forms.Textarea(attrs={"rows": 5}),
            "target_roles": forms.Textarea(
                attrs={"rows": 7, "placeholder": "Biomedical Engineer\nSystems Engineer\nTest Engineer"}
            ),
            "target_industries": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Medical devices\nHealthcare technology"}
            ),
            "skills": forms.Textarea(
                attrs={"rows": 8, "placeholder": "Electrical engineering\nPython\nTesting and validation"}
            ),
            "preferred_locations": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Philadelphia, PA\nRemote — United States"}
            ),
            "minimum_salary": forms.NumberInput(attrs={"min": 0, "step": 1000}),
            "work_authorization": forms.TextInput(
                attrs={"placeholder": "Optional — add only what is relevant to your search"}
            ),
            "priorities": forms.Textarea(attrs={"rows": 6}),
            "deal_breakers": forms.Textarea(attrs={"rows": 6}),
            "additional_context": forms.Textarea(attrs={"rows": 7}),
        }

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.LIST_FIELDS:
            value = cleaned_data.get(field_name, "")
            items = []
            seen = set()

            for raw_item in value.splitlines():
                item = raw_item.strip()
                normalized_item = item.casefold()
                if item and normalized_item not in seen:
                    items.append(item)
                    seen.add(normalized_item)

            cleaned_data[field_name] = "\n".join(items)

        return cleaned_data
