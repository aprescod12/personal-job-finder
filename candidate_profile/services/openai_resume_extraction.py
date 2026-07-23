from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from django.conf import settings

from .compact_ai_resume_extraction import CompactStructuredAIResumeExtractor
from .resume_extraction import (
    ERROR_CONFIGURATION,
    ERROR_INVALID_RESPONSE,
    ERROR_PROVIDER_FAILURE,
    ResumeExtractionError,
)


OPENAI_RESUME_BACKEND_VERSION = "openai-responses-resume-v4"
_MAX_OUTPUT_REASONS = {"max_tokens", "max_output_tokens"}


class OpenAIResumeResponsesBackend:
    """Structured-output backend with one bounded output-limit retry."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_output_tokens: int | None = None,
        retry_max_output_tokens: int | None = None,
        max_input_chars: int | None = None,
        reasoning_effort: str | None = None,
        client: Any | None = None,
    ):
        self.model = (
            model
            or getattr(settings, "OPENAI_RESUME_EXTRACTION_MODEL", "gpt-5-mini")
        ).strip()
        self.timeout_seconds = timeout_seconds or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_TIMEOUT_SECONDS",
            120,
        )
        self.max_output_tokens = max_output_tokens or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_MAX_OUTPUT_TOKENS",
            8000,
        )
        configured_retry_tokens = retry_max_output_tokens or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_RETRY_MAX_OUTPUT_TOKENS",
            12000,
        )
        self.retry_max_output_tokens = max(
            self.max_output_tokens,
            configured_retry_tokens,
        )
        self.max_input_chars = max_input_chars or getattr(
            settings,
            "OPENAI_RESUME_EXTRACTION_MAX_INPUT_CHARS",
            60000,
        )
        self.reasoning_effort = (
            reasoning_effort
            or getattr(settings, "OPENAI_RESUME_EXTRACTION_REASONING_EFFORT", "low")
        ).strip()
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

    @staticmethod
    def _incomplete_reason(response: Any) -> str:
        details = getattr(response, "incomplete_details", None)
        if isinstance(details, Mapping):
            reason = details.get("reason", "")
        else:
            reason = getattr(details, "reason", "")
        reason = str(reason or "").strip()
        if reason in _MAX_OUTPUT_REASONS:
            return "max_output_tokens"
        if reason == "content_filter":
            return "content_filter"
        return "unknown"

    def _request_payload(
        self,
        *,
        schema_name: str,
        schema: Mapping[str, Any],
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": dict(schema),
                    "strict": True,
                }
            },
            "max_output_tokens": max_output_tokens,
            "store": False,
            "timeout": self.timeout_seconds,
        }
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

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

        client = self._get_client()
        token_budgets = [self.max_output_tokens]
        if self.retry_max_output_tokens > self.max_output_tokens:
            token_budgets.append(self.retry_max_output_tokens)

        response = None
        used_output_retry = False
        for attempt_index, token_budget in enumerate(token_budgets):
            try:
                response = client.responses.create(
                    **self._request_payload(
                        schema_name=schema_name,
                        schema=schema,
                        instructions=instructions,
                        input_text=input_text,
                        max_output_tokens=token_budget,
                    )
                )
            except ResumeExtractionError:
                raise
            except Exception as exc:
                raise self._provider_error(exc) from exc

            status = str(getattr(response, "status", "") or "").strip()
            if not status or status == "completed":
                break

            if status == "incomplete":
                reason = self._incomplete_reason(response)
                can_retry = (
                    reason == "max_output_tokens"
                    and attempt_index == 0
                    and len(token_budgets) > 1
                )
                if can_retry:
                    used_output_retry = True
                    continue
                if reason == "max_output_tokens":
                    raise ResumeExtractionError(
                        "OpenAI resume extraction reached the output limit after one bounded retry (reason: max_output_tokens).",
                        category=ERROR_INVALID_RESPONSE,
                        retryable=False,
                    )
                raise ResumeExtractionError(
                    f"OpenAI resume extraction did not complete successfully (reason: {reason}).",
                    category=ERROR_INVALID_RESPONSE,
                    retryable=False,
                )

            raise ResumeExtractionError(
                f"OpenAI resume extraction did not complete successfully (status: {status}).",
                category=ERROR_PROVIDER_FAILURE,
                retryable=status in {"queued", "in_progress"},
            )

        if response is None:  # pragma: no cover - defensive boundary
            raise ResumeExtractionError(
                "OpenAI resume extraction returned no response.",
                category=ERROR_PROVIDER_FAILURE,
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

        if used_output_retry and isinstance(payload.get("warnings"), list):
            payload = dict(payload)
            payload["warnings"] = [
                *payload["warnings"],
                "OpenAI completed extraction after one bounded output-limit retry.",
            ]
        return payload


class OpenAIResumeExtractor(CompactStructuredAIResumeExtractor):
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
