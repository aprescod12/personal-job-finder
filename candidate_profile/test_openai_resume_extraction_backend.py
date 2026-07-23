import json
import os
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from tracker.models import CareerProfile

from .models import ResumeSource
from .services.ai_resume_extraction import build_ai_resume_input
from .services.compact_ai_resume_extraction import (
    COMPACT_AI_RESUME_EXTRACTION_INSTRUCTIONS,
    COMPACT_AI_RESUME_EXTRACTION_JSON_SCHEMA,
    COMPACT_AI_RESUME_SCHEMA_NAME,
    CompactStructuredAIResumeExtractor,
)
from .services.openai_resume_extraction import (
    OpenAIResumeExtractor,
    OpenAIResumeResponsesBackend,
)
from .services.resume_extraction import (
    ERROR_INVALID_RESPONSE,
    ResumeExtractionError,
    ResumeExtractionRequest,
    extract_resume,
)


RESUME_TEXT = """Amiri Prescod
amiri@example.com | +1 610-555-0100 | Philadelphia, PA | github.com/aprescod12

Professional Summary
Electrical engineer pursuing graduate study in biomedical engineering.

Education
Villanova University
B.S. Electrical Engineering | 2025
M.S. Biomedical Engineering Candidate | 2027

Experience
Engineering Intern
Medical Device Company | Summer 2025
Developed and tested embedded sensing prototypes.

Projects
Wearable Sensing Platform
Python, signal processing, embedded systems
Built a prototype for physiological data collection.

Technical Skills
Python, MATLAB, C, Embedded systems, Test and validation

Leadership and Activities
Student-Athlete
Villanova Track and Field
"""


def request_for_resume():
    return ResumeExtractionRequest(
        document_text=RESUME_TEXT,
        source_id=7,
        source_sha256="a" * 64,
        source_filename="amiri-resume.txt",
        source_label="Current engineering resume",
        document_parser_key="plain-text",
        document_parser_version="plain-text-v1",
    )


def valid_payload():
    return {
        "identity": {
            "full_name": "Amiri Prescod",
            "email": "amiri@example.com",
            "phone": "+1 610-555-0100",
            "location": "Philadelphia, PA",
            "links": ["github.com/aprescod12"],
        },
        "profile": {
            "professional_summary": (
                "Electrical engineer pursuing graduate study in biomedical engineering."
            ),
            "education": [
                {
                    "heading": "Villanova University",
                    "subheading": "B.S. Electrical Engineering",
                    "dates": "2025",
                    "details": ["M.S. Biomedical Engineering Candidate"],
                }
            ],
            "experience": [
                {
                    "heading": "Engineering Intern",
                    "subheading": "Medical Device Company",
                    "dates": "Summer 2025",
                    "details": [
                        "Developed and tested embedded sensing prototypes."
                    ],
                }
            ],
            "projects": [
                {
                    "heading": "Wearable Sensing Platform",
                    "subheading": "Python, signal processing, embedded systems",
                    "dates": "",
                    "details": [
                        "Built a prototype for physiological data collection."
                    ],
                }
            ],
            "skills": [
                "Python",
                "MATLAB",
                "C",
                "Embedded systems",
                "Test and validation",
            ],
            "certifications": [],
            "leadership": [
                {
                    "heading": "Student-Athlete",
                    "subheading": "Villanova Track and Field",
                    "dates": "",
                    "details": [],
                }
            ],
        },
        "warnings": ["No certifications section was present."],
    }


def completed_response(payload=None):
    return SimpleNamespace(
        status="completed",
        output_text=json.dumps(payload or valid_payload()),
        output=[],
        incomplete_details=None,
    )


def incomplete_response(reason="max_tokens", payload=None):
    return SimpleNamespace(
        status="incomplete",
        output_text=json.dumps(payload or valid_payload()),
        output=[],
        incomplete_details=SimpleNamespace(reason=reason),
    )


class RecordingResponsesResource:
    def __init__(self, *, response=None, responses=None, error=None):
        self.responses_to_return = list(
            responses or ([] if response is None else [response])
        )
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if not self.responses_to_return:
            raise AssertionError("No fake OpenAI response remains.")
        return self.responses_to_return.pop(0)


class RecordingClient:
    def __init__(self, *, response=None, responses=None, error=None):
        self.responses = RecordingResponsesResource(
            response=response,
            responses=responses,
            error=error,
        )


class OpenAIResumeBackendRequestTests(TestCase):
    def test_backend_sends_compact_strict_schema_without_provider_storage(self):
        client = RecordingClient(response=completed_response())
        backend = OpenAIResumeResponsesBackend(
            model="gpt-5-mini",
            timeout_seconds=19,
            max_output_tokens=3200,
            retry_max_output_tokens=6400,
            max_input_chars=20000,
            reasoning_effort="low",
            client=client,
        )

        result = backend.generate_structured(
            schema_name=COMPACT_AI_RESUME_SCHEMA_NAME,
            schema=COMPACT_AI_RESUME_EXTRACTION_JSON_SCHEMA,
            instructions=COMPACT_AI_RESUME_EXTRACTION_INSTRUCTIONS,
            input_text=build_ai_resume_input(request_for_resume()),
        )

        self.assertEqual(result["identity"]["full_name"], "Amiri Prescod")
        api_request = client.responses.calls[0]
        self.assertEqual(api_request["model"], "gpt-5-mini")
        self.assertEqual(
            api_request["instructions"],
            COMPACT_AI_RESUME_EXTRACTION_INSTRUCTIONS,
        )
        self.assertIn("RESUME TEXT START", api_request["input"])
        self.assertIn("amiri-resume.txt", api_request["input"])
        self.assertFalse(api_request["store"])
        self.assertEqual(api_request["timeout"], 19)
        self.assertEqual(api_request["max_output_tokens"], 3200)
        self.assertEqual(api_request["reasoning"], {"effort": "low"})
        self.assertEqual(api_request["text"]["format"]["type"], "json_schema")
        self.assertEqual(
            api_request["text"]["format"]["name"],
            COMPACT_AI_RESUME_SCHEMA_NAME,
        )
        self.assertEqual(
            api_request["text"]["format"]["schema"],
            COMPACT_AI_RESUME_EXTRACTION_JSON_SCHEMA,
        )
        self.assertTrue(api_request["text"]["format"]["strict"])
        self.assertNotIn(
            "evidence",
            COMPACT_AI_RESUME_EXTRACTION_JSON_SCHEMA["properties"],
        )
        entry_schema = COMPACT_AI_RESUME_EXTRACTION_JSON_SCHEMA["properties"][
            "profile"
        ]["properties"]["education"]["items"]
        self.assertNotIn("source_text", entry_schema["properties"])

    def test_max_output_incomplete_retries_once_with_larger_budget(self):
        client = RecordingClient(
            responses=[
                incomplete_response("max_tokens"),
                completed_response(),
            ]
        )
        backend = OpenAIResumeResponsesBackend(
            max_output_tokens=3000,
            retry_max_output_tokens=7000,
            client=client,
        )

        result = backend.generate_structured(
            schema_name="test_schema",
            schema={"type": "object"},
            instructions="Extract.",
            input_text=RESUME_TEXT,
        )

        self.assertEqual(len(client.responses.calls), 2)
        self.assertEqual(client.responses.calls[0]["max_output_tokens"], 3000)
        self.assertEqual(client.responses.calls[1]["max_output_tokens"], 7000)
        self.assertIn("bounded output-limit retry", " ".join(result["warnings"]))

    def test_max_output_incomplete_stops_after_one_bounded_retry(self):
        client = RecordingClient(
            responses=[
                incomplete_response("max_tokens"),
                incomplete_response("max_output_tokens"),
            ]
        )
        backend = OpenAIResumeResponsesBackend(
            max_output_tokens=3000,
            retry_max_output_tokens=7000,
            client=client,
        )

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "after one bounded retry",
        ) as context:
            backend.generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=RESUME_TEXT,
            )
        self.assertEqual(len(client.responses.calls), 2)
        self.assertFalse(context.exception.retryable)

    def test_non_output_incomplete_is_not_retried_or_accepted(self):
        client = RecordingClient(response=incomplete_response("content_filter"))
        backend = OpenAIResumeResponsesBackend(
            max_output_tokens=3000,
            retry_max_output_tokens=7000,
            client=client,
        )

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "reason: content_filter",
        ):
            backend.generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=RESUME_TEXT,
            )
        self.assertEqual(len(client.responses.calls), 1)

    def test_oversized_input_is_rejected_before_api_call(self):
        client = RecordingClient(response=completed_response())
        backend = OpenAIResumeResponsesBackend(client=client, max_input_chars=20)

        with self.assertRaisesMessage(ResumeExtractionError, "input limit"):
            backend.generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=RESUME_TEXT,
            )
        self.assertEqual(client.responses.calls, [])

    def test_missing_key_fails_before_creating_real_client(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(ResumeExtractionError, "not configured"):
                OpenAIResumeResponsesBackend()._get_client()

    def test_invalid_json_and_non_object_json_are_rejected(self):
        for output_text, expected in (
            ("not json", "not valid JSON"),
            ("[]", "top-level value"),
        ):
            client = RecordingClient(
                response=SimpleNamespace(
                    status="completed",
                    output_text=output_text,
                    output=[],
                    incomplete_details=None,
                )
            )
            with self.subTest(output_text=output_text):
                with self.assertRaisesMessage(ResumeExtractionError, expected):
                    OpenAIResumeResponsesBackend(client=client).generate_structured(
                        schema_name="test_schema",
                        schema={"type": "object"},
                        instructions="Extract.",
                        input_text=RESUME_TEXT,
                    )

    def test_refusal_is_reported_without_provider_text(self):
        refusal = SimpleNamespace(
            type="refusal",
            refusal="Provider-specific refusal detail",
        )
        client = RecordingClient(
            response=SimpleNamespace(
                status="completed",
                output_text="",
                output=[SimpleNamespace(content=[refusal])],
                incomplete_details=None,
            )
        )

        with self.assertRaisesMessage(ResumeExtractionError, "declined") as context:
            OpenAIResumeResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=RESUME_TEXT,
            )
        self.assertNotIn("Provider-specific", str(context.exception))

    def test_provider_error_is_sanitized(self):
        AuthenticationError = type("AuthenticationError", (Exception,), {})
        client = RecordingClient(
            error=AuthenticationError("secret provider response body")
        )

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "authentication failed",
        ) as context:
            OpenAIResumeResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=RESUME_TEXT,
            )
        self.assertNotIn("secret provider response", str(context.exception))


class CompactAIResumeValidationTests(TestCase):
    @staticmethod
    def extractor_for(payload):
        class FakeBackend:
            def generate_structured(self, **kwargs):
                return payload

        return CompactStructuredAIResumeExtractor(backend=FakeBackend())

    def test_injected_openai_backend_returns_local_evidence_without_database_write(self):
        class FakeBackend:
            def generate_structured(self, **kwargs):
                return valid_payload()

        profile_count_before = CareerProfile.objects.count()
        source_count_before = ResumeSource.objects.count()

        result = extract_resume(
            request_for_resume(),
            extractor=OpenAIResumeExtractor(backend=FakeBackend()),
        )

        self.assertEqual(result["provider"]["key"], "openai_resume_structured")
        self.assertEqual(result["provider"]["mode"], "ai")
        self.assertEqual(result["identity"]["full_name"], "Amiri Prescod")
        self.assertIn("Python", result["profile"]["skills"])
        self.assertTrue(result["evidence"])
        self.assertTrue(
            all(item["source_text"] in RESUME_TEXT for item in result["evidence"])
        )
        self.assertEqual(CareerProfile.objects.count(), profile_count_before)
        self.assertEqual(ResumeSource.objects.count(), source_count_before)

    def test_hallucinated_skill_is_rejected_by_grounding_validation(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["skills"].append("Rust")

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "profile.skills[5]",
        ) as context:
            self.extractor_for(payload).extract(request_for_resume())
        self.assertEqual(context.exception.category, ERROR_INVALID_RESPONSE)

    def test_provider_cannot_send_removed_source_text_field(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["experience"][0]["source_text"] = "Engineering Intern"

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "unsupported keys: source_text",
        ):
            self.extractor_for(payload).extract(request_for_resume())

    def test_provider_cannot_send_removed_evidence_list(self):
        payload = deepcopy(valid_payload())
        payload["evidence"] = []

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "unsupported keys: evidence",
        ):
            self.extractor_for(payload).extract(request_for_resume())

    def test_extra_payload_key_is_rejected(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["target_role"] = "Biomedical Engineer"

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "unsupported keys: target_role",
        ):
            self.extractor_for(payload).extract(request_for_resume())

    @override_settings(RESUME_AI_ENABLED=False)
    def test_openai_extractor_cannot_activate_while_switch_is_disabled(self):
        with self.assertRaisesMessage(ResumeExtractionError, "disabled"):
            OpenAIResumeExtractor()
