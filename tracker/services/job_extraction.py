import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string


DEFAULT_EXTRACTOR_PATH = "tracker.services.job_intake.DeterministicJobExtractor"

JOB_FIELD_DEFAULTS = {
    "title": "",
    "company": "",
    "location": "",
    "job_url": "",
    "source": "",
    "employment_type": "unknown",
    "work_arrangement": "unknown",
    "deadline_status": "unknown",
    "application_deadline": "",
    "description": "",
    "next_action": "Verify listing and review requirements",
}

REQUIREMENT_FIELD_DEFAULTS = {
    "role_family": "",
    "seniority_level": "unknown",
    "industry": "",
    "required_skills": "",
    "preferred_skills": "",
    "required_education": "",
    "preferred_education": "",
    "minimum_years_experience": None,
    "maximum_years_experience": None,
    "responsibilities": "",
    "certifications": "",
    "work_authorization_requirements": "",
    "hard_disqualifiers": "",
    "requirement_notes": "",
}


class JobExtractionError(RuntimeError):
    """Raised when a configured extraction provider cannot produce a safe draft."""


@dataclass(frozen=True, slots=True)
class JobExtractionRequest:
    listing_text: str
    source_url: str = ""
    source_label: str = ""

    def __post_init__(self):
        if not self.listing_text or not self.listing_text.strip():
            raise JobExtractionError("Listing text is required for extraction.")


@dataclass(slots=True)
class JobExtractionResult:
    provider_key: str
    provider_label: str
    provider_version: str
    extraction_mode: str
    job: dict[str, Any] = field(default_factory=dict)
    requirements: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        job = {**JOB_FIELD_DEFAULTS, **self.job}
        requirements = {**REQUIREMENT_FIELD_DEFAULTS, **self.requirements}
        payload = {
            "provider": {
                "key": self.provider_key,
                "label": self.provider_label,
                "version": self.provider_version,
                "mode": self.extraction_mode,
            },
            # Retained for compatibility with the Stage 4 Step 1 review template and
            # any existing session drafts.
            "parser_version": self.provider_version,
            "job": job,
            "requirements": requirements,
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
        }

        try:
            json.dumps(payload)
        except (TypeError, ValueError) as exc:
            raise JobExtractionError(
                "The extraction provider returned data that cannot be stored safely."
            ) from exc

        return payload


class BaseJobExtractor(ABC):
    """Contract implemented by every deterministic or AI extraction provider."""

    provider_key = "base"
    provider_label = "Base extractor"
    provider_version = "unversioned"
    extraction_mode = "unknown"

    @abstractmethod
    def extract(self, request: JobExtractionRequest) -> JobExtractionResult:
        """Return a reviewable draft without writing to the database."""

    def result(
        self,
        *,
        job: dict[str, Any],
        requirements: dict[str, Any],
        evidence: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> JobExtractionResult:
        return JobExtractionResult(
            provider_key=self.provider_key,
            provider_label=self.provider_label,
            provider_version=self.provider_version,
            extraction_mode=self.extraction_mode,
            job=job,
            requirements=requirements,
            evidence=evidence or [],
            warnings=warnings or [],
        )


def get_job_extractor(extractor_path: str | None = None) -> BaseJobExtractor:
    path = extractor_path or getattr(
        settings,
        "JOB_INTAKE_EXTRACTOR",
        DEFAULT_EXTRACTOR_PATH,
    )

    try:
        extractor_class = import_string(path)
    except (ImportError, AttributeError, ValueError) as exc:
        raise JobExtractionError(
            f"The configured job extractor could not be loaded: {path}."
        ) from exc

    try:
        extractor = extractor_class()
    except TypeError as exc:
        raise JobExtractionError(
            f"The configured job extractor could not be initialized: {path}."
        ) from exc

    if not isinstance(extractor, BaseJobExtractor):
        raise JobExtractionError(
            "The configured job extractor must implement BaseJobExtractor."
        )

    return extractor


def extract_job(
    listing_text: str,
    *,
    source_url: str = "",
    source_label: str = "",
    extractor: BaseJobExtractor | None = None,
) -> dict[str, Any]:
    request = JobExtractionRequest(
        listing_text=listing_text,
        source_url=source_url,
        source_label=source_label,
    )
    active_extractor = extractor or get_job_extractor()
    result = active_extractor.extract(request)

    if not isinstance(result, JobExtractionResult):
        raise JobExtractionError(
            "The extraction provider did not return a JobExtractionResult."
        )

    return result.to_dict()
