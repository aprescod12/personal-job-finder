from django import forms

from .models import CareerProfile, JobPosting, JobRequirement


def normalize_line_list(value):
    items = []
    seen = set()

    for raw_item in (value or "").splitlines():
        item = raw_item.strip()
        normalized_item = item.casefold()
        if item and normalized_item not in seen:
            items.append(item)
            seen.add(normalized_item)

    return "\n".join(items)


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


class JobRequirementForm(forms.ModelForm):
    LIST_FIELDS = (
        "required_skills",
        "preferred_skills",
        "required_education",
        "preferred_education",
        "responsibilities",
        "certifications",
        "hard_disqualifiers",
    )

    class Meta:
        model = JobRequirement
        fields = [
            "role_family",
            "seniority_level",
            "industry",
            "required_skills",
            "preferred_skills",
            "required_education",
            "preferred_education",
            "minimum_years_experience",
            "maximum_years_experience",
            "responsibilities",
            "certifications",
            "work_authorization_requirements",
            "hard_disqualifiers",
            "requirement_notes",
        ]
        labels = {
            "role_family": "Role family",
            "seniority_level": "Seniority level",
            "industry": "Industry or domain",
            "minimum_years_experience": "Minimum years of experience",
            "maximum_years_experience": "Maximum years of experience",
            "work_authorization_requirements": "Work authorization requirements",
            "requirement_notes": "Interpretation notes",
        }
        widgets = {
            "role_family": forms.TextInput(
                attrs={"placeholder": "Verification and Validation Engineering"}
            ),
            "industry": forms.TextInput(attrs={"placeholder": "Medical devices"}),
            "required_skills": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": (
                        "Test protocol development\n"
                        "Requirements documentation\n"
                        "MATLAB"
                    ),
                }
            ),
            "preferred_skills": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "ISO 13485\nMedical-device experience",
                }
            ),
            "required_education": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Electrical Engineering\nBiomedical Engineering",
                }
            ),
            "preferred_education": forms.Textarea(attrs={"rows": 4}),
            "minimum_years_experience": forms.NumberInput(
                attrs={"min": 0, "max": 60}
            ),
            "maximum_years_experience": forms.NumberInput(
                attrs={"min": 0, "max": 60}
            ),
            "responsibilities": forms.Textarea(attrs={"rows": 7}),
            "certifications": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "ISO 13485\nFDA design controls",
                }
            ),
            "work_authorization_requirements": forms.Textarea(attrs={"rows": 4}),
            "hard_disqualifiers": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Active security clearance required\n"
                        "No sponsorship available"
                    ),
                }
            ),
            "requirement_notes": forms.Textarea(attrs={"rows": 5}),
        }

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.LIST_FIELDS:
            cleaned_data[field_name] = normalize_line_list(
                cleaned_data.get(field_name, "")
            )

        minimum = cleaned_data.get("minimum_years_experience")
        maximum = cleaned_data.get("maximum_years_experience")
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error(
                "maximum_years_experience",
                "Maximum experience cannot be lower than minimum experience.",
            )

        return cleaned_data


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
                    "placeholder": (
                        "Electrical Engineer | M.S. Biomedical Engineering Candidate"
                    )
                }
            ),
            "education_summary": forms.Textarea(attrs={"rows": 5}),
            "target_roles": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": (
                        "Biomedical Engineer\nSystems Engineer\nTest Engineer"
                    ),
                }
            ),
            "target_industries": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Medical devices\nHealthcare technology",
                }
            ),
            "skills": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": (
                        "Electrical engineering\nPython\nTesting and validation"
                    ),
                }
            ),
            "preferred_locations": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Philadelphia, PA\nRemote — United States",
                }
            ),
            "minimum_salary": forms.NumberInput(attrs={"min": 0, "step": 1000}),
            "work_authorization": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Optional — add only what is relevant to your search"
                    )
                }
            ),
            "priorities": forms.Textarea(attrs={"rows": 6}),
            "deal_breakers": forms.Textarea(attrs={"rows": 6}),
            "additional_context": forms.Textarea(attrs={"rows": 7}),
        }

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.LIST_FIELDS:
            cleaned_data[field_name] = normalize_line_list(
                cleaned_data.get(field_name, "")
            )

        return cleaned_data
