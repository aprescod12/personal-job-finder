import json
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string


DEFAULT_EXTRACTOR_PATH = (
    "candidate_profile.services.resume_deterministic.DeterministicResumeExtractor"
)

ERROR_CONFIGURATION = "configuration"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_PROVIDER_FAILURE = "provider_failure"

IDENTITY_DEFAULTS = {
    "full_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "links": [],
}

PROFILE_DEFAULTS = {
    "professional_summary": "",
    "education": [],
    "experience": [],
    "projects": [],
    "skills": [],
    "certifications": [],
    "leadership": [],
}


class ResumeExtractionError(RuntimeError):
    """Raised when a configured resume extractor cannot produce a safe draft."""

    def __init__(
        self,
        message: str,
        *,
        category: str = ERROR_PROVIDER_FAILURE,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ResumeExtractionRequest:
    document_text: str
    source_id: int
    source_sha256: str
    source_filename: str
    source_label: str = ""
    document_parser_key: str = ""
    document_parser_version: str = ""

    def __post_init__(self):
        if not self.document_text or not self.document_text.strip():
            raise ResumeExtractionError(
                "Readable resume text is required for extraction.",
                category=ERROR_CONFIGURATION,
            )
        if not self.source_id or self.source_id < 1:
            raise ResumeExtractionError(
                "A stored resume source is required for extraction.",
                category=ERROR_CONFIGURATION,
            )
        if len(self.source_sha256) != 64:
            raise ResumeExtractionError(
                "The resume source fingerprint is invalid.",
                category=ERROR_CONFIGURATION,
            )
        if not self.source_filename.strip():
            raise ResumeExtractionError(
                "The resume source filename is required.",
                category=ERROR_CONFIGURATION,
            )


@dataclass(slots=True)
class ResumeExtractionResult:
    provider_key: str
    provider_label: str
    provider_version: str
    extraction_mode: str
    identity: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        identity = deepcopy(IDENTITY_DEFAULTS)
        identity.update(self.identity)

        profile = deepcopy(PROFILE_DEFAULTS)
        profile.update(self.profile)

        payload = {
            "provider": {
                "key": self.provider_key,
                "label": self.provider_label,
                "version": self.provider_version,
                "mode": self.extraction_mode,
            },
            "identity": identity,
            "profile": profile,
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
        }

        try:
            json.dumps(payload)
        except (TypeError, ValueError) as exc:
            raise ResumeExtractionError(
                "The resume extractor returned data that cannot be stored safely.",
                category=ERROR_INVALID_RESPONSE,
            ) from exc

        return payload


class BaseResumeExtractor(ABC):
    """Contract implemented by deterministic and future AI resume extractors."""

    provider_key = "base"
    provider_label = "Base resume extractor"
    provider_version = "unversioned"
    extraction_mode = "unknown"
    requires_ai_enabled = False

    @abstractmethod
    def extract(self, request: ResumeExtractionRequest) -> ResumeExtractionResult:
        """Return a reviewable draft without writing to the database."""

    def result(
        self,
        *,
        identity: dict[str, Any],
        profile: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> ResumeExtractionResult:
        return ResumeExtractionResult(
            provider_key=self.provider_key,
            provider_label=self.provider_label,
            provider_version=self.provider_version,
            extraction_mode=self.extraction_mode,
            identity=identity,
            profile=profile,
            evidence=evidence or [],
            warnings=warnings or [],
        )


def get_resume_extractor(extractor_path: str | None = None) -> BaseResumeExtractor:
    path = extractor_path or getattr(
        settings,
        "RESUME_EXTRACTOR",
        DEFAULT_EXTRACTOR_PATH,
    )

    try:
        extractor_class = import_string(path)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ResumeExtractionError(
            f"The configured resume extractor could not be loaded: {path}.",
            category=ERROR_CONFIGURATION,
        ) from exc

    try:
        extractor = extractor_class()
    except ResumeExtractionError:
        raise
    except TypeError as exc:
        raise ResumeExtractionError(
            f"The configured resume extractor could not be initialized: {path}.",
            category=ERROR_CONFIGURATION,
        ) from exc

    if not isinstance(extractor, BaseResumeExtractor):
        raise ResumeExtractionError(
            "The configured resume extractor must implement BaseResumeExtractor.",
            category=ERROR_CONFIGURATION,
        )

    if extractor.requires_ai_enabled and not getattr(
        settings,
        "RESUME_AI_ENABLED",
        False,
    ):
        raise ResumeExtractionError(
            "AI resume extraction is disabled by the RESUME_AI_ENABLED safety switch.",
            category=ERROR_CONFIGURATION,
        )

    return extractor


def execute_resume_extractor(
    request: ResumeExtractionRequest,
    extractor: BaseResumeExtractor,
) -> ResumeExtractionResult:
    result = extractor.extract(request)
    if not isinstance(result, ResumeExtractionResult):
        raise ResumeExtractionError(
            "The resume extraction provider did not return a ResumeExtractionResult.",
            category=ERROR_INVALID_RESPONSE,
        )
    result.to_dict()
    return result


def extract_resume(
    request: ResumeExtractionRequest,
    *,
    extractor: BaseResumeExtractor | None = None,
) -> dict[str, Any]:
    active_extractor = extractor or get_resume_extractor()
    result = execute_resume_extractor(request, active_extractor)
    return result.to_dict()
