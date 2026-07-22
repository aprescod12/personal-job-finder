from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from django.conf import settings

from .ai_resume_extraction import StructuredAIResumeExtractor
from .resume_extraction import (
    ERROR_CONFIGURATION,
    ERROR_INVALID_RESPONSE,
    ERROR_PROVIDER_FAILURE,
    ResumeExtractionError,
)


OPENAI_RESUME_BACKEND_VERSION = "openai-responses-resume-v2"


class OpenAIResumeResponsesBackend:
    """Structured-output backend for resume extraction with the Responses API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_output_tokens: int | None = None,
        max_input_chars: int | None = None,
        client: Any | None = None,
    ):
        self.model = (
            model
            or getattr(settings, "OPENAI_RESUME_EXTRACTION_MODEL", "gpt-5-mini")
        ).strip()
        self.timeout_seconds = timeout_seconds or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_TIMEOUT_SECONDS",
            30,
        )
        self.max_output_tokens = max_output_tokens or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_MAX_OUTPUT_TOKENS",
            5000,
        )
        self.max_input_chars = max_input_chars or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_MAX_INPUT_CHARS",
            60000,
        )
        self.client = client

    def _get_client(self):
        if self.client is not None:
            return self.client
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise ResumeExtractionError(
                "OpenAI resume extraction is not configured. Add the API key to the local environment.",
                category=ERROR_CONFIGURATION,
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ResumeExtractionError(
                "The OpenAI Python package is not installed. Install project dependencies first.",
                category=ERROR_CONFIGURATION,
            ) from exc
        return OpenAI(timeout=self.timeout_seconds, max_retries=1)

    @staticmethod
    def _provider_error(exc: Exception) -> ResumeExtractionError:
        failures = {
            "AuthenticationError": (
                "OpenAI authentication failed. Check the local API key.",
                ERROR_CONFIGURATION,
                False,
            ),
            "PermissionDeniedError": (
                "The OpenAI project cannot use the configured resume-extraction model.",
                ERROR_CONFIGURATION,
                False,
            ),
            "RateLimitError": (
                "OpenAI rate or usage limits prevented resume extraction.",
                ERROR_PROVIDER_FAILURE,
                True,
            ),
            "APITimeoutError": (
                "The OpenAI resume-extraction request timed out.",
                ERROR_PROVIDER_FAILURE,
                True,
            ),
            "APIConnectionError": (
                "The application could not connect to OpenAI for resume extraction.",
                ERROR_PROVIDER_FAILURE,
                True,
            ),
            "BadRequestError": (
                "OpenAI rejected the structured resume-extraction request.",
                ERROR_INVALID_RESPONSE,
                False,
            ),
            "NotFoundError": (
                "The configured OpenAI resume-extraction model was not found.",
                ERROR_CONFIGURATION,
                False,
            ),
        }
        message, category, retryable = failures.get(
            type(exc).__name__,
            (
                "The OpenAI resume-extraction request failed.",
                ERROR_PROVIDER_FAILURE,
                False,
            ),
        )
        return ResumeExtractionError(
            message,
            category=category,
            retryable=retryable,
        )

    @staticmethod
    def _find_refusal(response: Any) -> str:
        for output_item in getattr(response, "output", None) or []:
            for content_item in getattr(output_item, "content", None) or []:
                if getattr(content_item, "type", "") == "refusal":
                    return str(getattr(content_item, "refusal", "")).strip()
        return ""

    def generate_structured(
        self,
        *,
        schema_name: str,
        schema: Mapping[str, Any],
        instructions: str,
        input_text: str,
    ) -> Mapping[str, Any]:
        if not self.model:
            raise ResumeExtractionError(
                "OpenAI resume extraction has no configured model.",
                category=ERROR_CONFIGURATION,
            )
        if len(input_text) > self.max_input_chars:
            raise ResumeExtractionError(
                "The parsed resume text exceeds the configured AI input limit.",
                category=ERROR_CONFIGURATION,
            )

        try:
            response = self._get_client().responses.create(
                model=self.model,
                instructions=instructions,
                input=input_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": dict(schema),
                        "strict": True,
                    }
                },
                max_output_tokens=self.max_output_tokens,
                store=False,
                timeout=self.timeout_seconds,
            )
        except ResumeExtractionError:
            raise
        except Exception as exc:
            raise self._provider_error(exc) from exc

        status = str(getattr(response, "status", "") or "").strip()
        if status and status != "completed":
            raise ResumeExtractionError(
                f"OpenAI resume extraction did not complete successfully (status: {status}).",
                category=ERROR_INVALID_RESPONSE,
                retryable=status in {"incomplete", "queued", "in_progress"},
            )

        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            if self._find_refusal(response):
                raise ResumeExtractionError(
                    "OpenAI declined to produce the structured resume extraction.",
                    category=ERROR_INVALID_RESPONSE,
                )
            raise ResumeExtractionError(
                "OpenAI returned no structured resume-extraction content.",
                category=ERROR_INVALID_RESPONSE,
            )

        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ResumeExtractionError(
                "OpenAI returned resume content that was not valid JSON.",
                category=ERROR_INVALID_RESPONSE,
            ) from exc
        if not isinstance(payload, Mapping):
            raise ResumeExtractionError(
                "OpenAI returned resume JSON whose top-level value was not an object.",
                category=ERROR_INVALID_RESPONSE,
            )
        return payload


class OpenAIResumeExtractor(StructuredAIResumeExtractor):
    provider_key = "openai_resume_structured"
    provider_label = "OpenAI structured resume extractor"
    provider_version = OPENAI_RESUME_BACKEND_VERSION
    extraction_mode = "ai"
    requires_ai_enabled = True

    def __init__(self, backend: OpenAIResumeResponsesBackend | None = None):
        if backend is None:
            if not getattr(settings, "RESUME_AI_ENABLED", False):
                raise ResumeExtractionError(
                    "AI resume extraction is disabled. Enable it only after local configuration is ready.",
                    category=ERROR_CONFIGURATION,
                )
            backend = OpenAIResumeResponsesBackend()
        super().__init__(backend=backend)
