from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from django.conf import settings

from .ai_job_extraction import StructuredAIJobExtractor
from .job_extraction import JobExtractionError

OPENAI_BACKEND_VERSION = "openai-responses-structured-v1"


class OpenAIResponsesBackend:
    """Structured-output backend for the OpenAI Responses API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_output_tokens: int | None = None,
        client: Any | None = None,
    ):
        self.model = (
            model
            or getattr(settings, "OPENAI_JOB_EXTRACTION_MODEL", "gpt-5-mini")
        ).strip()
        self.timeout_seconds = timeout_seconds or getattr(
            settings,
            "OPENAI_JOB_EXTRACTION_TIMEOUT_SECONDS",
            30,
        )
        self.max_output_tokens = max_output_tokens or getattr(
            settings,
            "OPENAI_JOB_EXTRACTION_MAX_OUTPUT_TOKENS",
            4000,
        )
        self.client = client

    def _get_client(self):
        if self.client is not None:
            return self.client
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise JobExtractionError(
                "OpenAI extraction is not configured. Add the API key to the local environment."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise JobExtractionError(
                "The OpenAI Python package is not installed. Install project dependencies first."
            ) from exc
        return OpenAI(timeout=self.timeout_seconds, max_retries=1)

    @staticmethod
    def _provider_error(exc: Exception) -> JobExtractionError:
        messages = {
            "AuthenticationError": "OpenAI authentication failed. Check the local API key.",
            "PermissionDeniedError": "The OpenAI project cannot use the configured model.",
            "RateLimitError": "OpenAI rate or usage limits prevented extraction.",
            "APITimeoutError": "The OpenAI extraction request timed out.",
            "APIConnectionError": "The application could not connect to OpenAI.",
            "BadRequestError": "OpenAI rejected the structured extraction request.",
            "NotFoundError": "The configured OpenAI model was not found.",
        }
        return JobExtractionError(
            messages.get(type(exc).__name__, "The OpenAI extraction request failed.")
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
            raise JobExtractionError("OpenAI extraction has no configured model.")

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
        except JobExtractionError:
            raise
        except Exception as exc:
            raise self._provider_error(exc) from exc

        status = str(getattr(response, "status", "") or "").strip()
        if status and status != "completed":
            raise JobExtractionError(
                f"OpenAI extraction did not complete successfully (status: {status})."
            )

        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            if self._find_refusal(response):
                raise JobExtractionError(
                    "OpenAI declined to produce the structured extraction."
                )
            raise JobExtractionError("OpenAI returned no structured extraction content.")

        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise JobExtractionError(
                "OpenAI returned content that was not valid JSON."
            ) from exc
        if not isinstance(payload, Mapping):
            raise JobExtractionError(
                "OpenAI returned JSON whose top-level value was not an object."
            )
        return payload


class OpenAIJobExtractor(StructuredAIJobExtractor):
    provider_key = "openai_structured"
    provider_label = "OpenAI structured extractor"
    provider_version = OPENAI_BACKEND_VERSION
    extraction_mode = "ai"

    def __init__(self, backend: OpenAIResponsesBackend | None = None):
        if backend is None:
            if not getattr(settings, "JOB_INTAKE_AI_ENABLED", False):
                raise JobExtractionError(
                    "AI job extraction is disabled. Enable it only after local configuration is ready."
                )
            backend = OpenAIResponsesBackend()
        super().__init__(backend=backend)
