from hashlib import sha256
from pathlib import Path

from django import forms
from django.db import transaction

from .models import ALLOWED_RESUME_EXTENSIONS, ResumeReviewClaim, ResumeSource


MAX_RESUME_BYTES = 5 * 1024 * 1024


class ResumeSourceUploadForm(forms.Form):
    label = forms.CharField(
        required=False,
        max_length=120,
        help_text="Optional version label, such as Medical Device Resume — July 2026.",
    )
    document = forms.FileField(
        label="Resume file",
        help_text="PDF, DOCX, or TXT. Maximum size: 5 MB.",
    )
    make_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Use this as the active resume source",
        help_text="Only one resume version can be active at a time.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Optional notes about the role family or audience for this version.",
    )

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.document_sha256 = ""

    def clean_document(self):
        document = self.cleaned_data["document"]
        extension = Path(document.name).suffix.casefold()

        if extension not in ALLOWED_RESUME_EXTENSIONS:
            raise forms.ValidationError("Upload a PDF, DOCX, or plain-text resume.")
        if document.size > MAX_RESUME_BYTES:
            raise forms.ValidationError("Resume files must be 5 MB or smaller.")

        digest = sha256()
        for chunk in document.chunks():
            digest.update(chunk)
        document.seek(0)
        self.document_sha256 = digest.hexdigest()
        return document

    def clean(self):
        cleaned_data = super().clean()
        if (
            self.profile
            and self.document_sha256
            and ResumeSource.objects.filter(
                profile=self.profile,
                sha256=self.document_sha256,
            ).exists()
        ):
            self.add_error(
                "document",
                "This exact resume file is already stored for your profile.",
            )
        return cleaned_data

    @transaction.atomic
    def save(self):
        if not self.is_valid():
            raise ValueError("Cannot save an invalid resume upload form.")
        if self.profile is None:
            raise ValueError("A career profile is required to save a resume source.")

        document = self.cleaned_data["document"]
        existing_sources = ResumeSource.objects.filter(profile=self.profile)
        make_active = self.cleaned_data.get("make_active", False) or not existing_sources.exists()

        if make_active:
            existing_sources.filter(is_active=True).update(is_active=False)

        return ResumeSource.objects.create(
            profile=self.profile,
            document=document,
            original_filename=Path(document.name).name,
            label=self.cleaned_data.get("label", "").strip(),
            content_type=getattr(document, "content_type", "") or "",
            file_size=document.size,
            sha256=self.document_sha256,
            is_active=make_active,
            notes=self.cleaned_data.get("notes", "").strip(),
        )


class ResumeReviewClaimForm(forms.Form):
    decision = forms.ChoiceField(
        choices=ResumeReviewClaim.Decision.choices,
        label="Review decision",
    )
    value_text = forms.CharField(
        required=False,
        label="Reviewed value",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    heading = forms.CharField(required=False, max_length=500)
    subheading = forms.CharField(required=False, max_length=500)
    dates = forms.CharField(required=False, max_length=300)
    details = forms.CharField(
        required=False,
        help_text="Enter one supporting detail per line.",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def __init__(self, *args, claim, **kwargs):
        self.claim = claim
        initial = kwargs.setdefault("initial", {})
        initial["decision"] = claim.decision
        value = claim.reviewed_value
        if claim.claim_type == ResumeReviewClaim.ClaimType.ENTRY:
            value = value if isinstance(value, dict) else {}
            initial.update(
                {
                    "heading": value.get("heading", ""),
                    "subheading": value.get("subheading", ""),
                    "dates": value.get("dates", ""),
                    "details": "\n".join(value.get("details", [])),
                }
            )
        else:
            initial["value_text"] = value if isinstance(value, str) else ""
        super().__init__(*args, **kwargs)

        if claim.is_applied or not claim.review.is_open:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        cleaned = super().clean()
        if self.claim.is_applied:
            self.reviewed_value = self.claim.reviewed_value
            return cleaned

        if self.claim.claim_type == ResumeReviewClaim.ClaimType.ENTRY:
            reviewed_value = {
                "heading": (cleaned.get("heading") or "").strip(),
                "subheading": (cleaned.get("subheading") or "").strip(),
                "dates": (cleaned.get("dates") or "").strip(),
                "details": [
                    line.strip()
                    for line in (cleaned.get("details") or "").splitlines()
                    if line.strip()
                ],
            }
            has_value = any(
                (
                    reviewed_value["heading"],
                    reviewed_value["subheading"],
                    reviewed_value["dates"],
                    reviewed_value["details"],
                )
            )
        else:
            reviewed_value = (cleaned.get("value_text") or "").strip()
            has_value = bool(reviewed_value)

        if (
            cleaned.get("decision") == ResumeReviewClaim.Decision.APPROVED
            and not has_value
        ):
            raise forms.ValidationError("An approved claim must contain a reviewed value.")

        self.reviewed_value = reviewed_value
        return cleaned

    def save(self):
        if not self.is_valid():
            raise ValueError("Cannot save an invalid claim review form.")
        if self.claim.is_applied:
            return self.claim

        self.claim.decision = self.cleaned_data["decision"]
        self.claim.reviewed_value = self.reviewed_value
        self.claim.save(update_fields=["decision", "reviewed_value", "updated_at"])
        return self.claim
