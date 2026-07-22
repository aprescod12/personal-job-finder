from hashlib import sha256
from pathlib import Path

from django import forms
from django.db import transaction

from .models import ALLOWED_RESUME_EXTENSIONS, ResumeSource


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
