import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from .models import JobPosting, JobRequirement
from .services.ai_job_extraction import (
    AI_EXTRACTION_INSTRUCTIONS,
    AI_EXTRACTION_SCHEMA_NAME,
    AI_JOB_EXTRACTION_JSON_SCHEMA,
)
from .services.job_extraction import JobExtractionError, extract_job
from .services.openai_job_extraction import (
    OpenAIJobExtractor,
    OpenAIResponsesBackend,
)


LISTING_TEXT = """
Job Title: Biomedical Test Engineer
Company: Example Medical
Location: Boston, MA

Required Qualifications
- Bachelor's degree in Biomedical Engineering
- Python
- 1 year of medical-device testing experience

Responsibilities
- Develop and execute verification protocols
"""


def valid_payload():
    return {
        "job": {
            "title": "Biomedical Test Engineer",
            "company": "Example Medical",
            "location": "Boston, MA",
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.UNKNOWN,
            "salary_text": "",
            "date_posted": None,
            "deadline_status": JobPosting.DeadlineStatus.UNKNOWN,
            "application_deadline": None,
        },
        "requirements": {
            "role_family": "Biomedical Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Medical devices",
            "required_skills": ["Python", "Medical-device testing"],
            "preferred_skills": [],
            "required_education": ["Bachelor's degree in Biomedical Engineering"],
            "preferred_education": [],
            "minimum_years_experience": 1,
            "maximum_years_experience": None,
            "responsibilities": ["Develop and execute verification protocols"],
            "certifications": [],
            "work_authorization_requirements": [],
            "hard_disqualifiers": [],
            "requirement_notes": "Review all extracted fields.",
        },
        "evidence": [
            {
                "field": "minimum_years_experience",
                "quote": "1 year of medical-device testing experience",
                "explanation": "The listing states a one-year minimum.",
            }
        ],
        "warnings": ["No application deadline was stated."],
    }


class RecordingResponsesResource:
    def __init__(self, *, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class RecordingClient:
    def __init__(self, *, response=None, error=None):
        self.responses = RecordingResponsesResource(response=response, error=error)


class OpenAIBackendRequestTests(TestCase):
    def test_backend_sends_one_strict_schema_request_and_parses_json(self):
        response = SimpleNamespace(
            status="completed",
            output_text=json.dumps(valid_payload()),
            output=[],
        )
        client = RecordingClient(response=response)
        backend = OpenAIResponsesBackend(
            model="gpt-5-mini",
            timeout_seconds=17,
            max_output_tokens=2500,
            client=client,
        )

        result = backend.generate_structured(
            schema_name=AI_EXTRACTION_SCHEMA_NAME,
            schema=AI_JOB_EXTRACTION_JSON_SCHEMA,
            instructions=AI_EXTRACTION_INSTRUCTIONS,
            input_text=LISTING_TEXT,
        )

        self.assertEqual(result["job"]["title"], "Biomedical Test Engineer")
        self.assertEqual(len(client.responses.calls), 1)
        request = client.responses.calls[0]
        self.assertEqual(request["model"], "gpt-5-mini")
        self.assertEqual(request["instructions"], AI_EXTRACTION_INSTRUCTIONS)
        self.assertEqual(request["input"], LISTING_TEXT)
        self.assertFalse(request["store"])
        self.assertEqual(request["timeout"], 17)
        self.assertEqual(request["max_output_tokens"], 2500)
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertEqual(
            request["text"]["format"]["name"],
            AI_EXTRACTION_SCHEMA_NAME,
        )
        self.assertEqual(
            request["text"]["format"]["schema"],
            AI_JOB_EXTRACTION_JSON_SCHEMA,
        )
        self.assertTrue(request["text"]["format"]["strict"])

    def test_missing_key_fails_before_creating_a_real_client(self):
        with patch.dict(os.environ, {}, clear=True):
            backend = OpenAIResponsesBackend()
            with self.assertRaisesMessage(
                JobExtractionError,
                "not configured",
            ):
                backend._get_client()

    def test_invalid_json_is_rejected(self):
        client = RecordingClient(
            response=SimpleNamespace(
                status="completed",
                output_text="not json",
                output=[],
            )
        )
        with self.assertRaisesMessage(JobExtractionError, "not valid JSON"):
            OpenAIResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=LISTING_TEXT,
            )

    def test_non_object_json_is_rejected(self):
        client = RecordingClient(
            response=SimpleNamespace(
                status="completed",
                output_text="[]",
                output=[],
            )
        )
        with self.assertRaisesMessage(JobExtractionError, "top-level value"):
            OpenAIResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=LISTING_TEXT,
            )

    def test_refusal_is_reported_without_exposing_provider_text(self):
        refusal_content = SimpleNamespace(
            type="refusal",
            refusal="Provider-specific refusal detail",
        )
        client = RecordingClient(
            response=SimpleNamespace(
                status="completed",
                output_text="",
                output=[SimpleNamespace(content=[refusal_content])],
            )
        )
        with self.assertRaisesMessage(JobExtractionError, "declined") as context:
            OpenAIResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=LISTING_TEXT,
            )
        self.assertNotIn("Provider-specific", str(context.exception))

    def test_incomplete_response_is_rejected(self):
        client = RecordingClient(
            response=SimpleNamespace(
                status="incomplete",
                output_text=json.dumps(valid_payload()),
                output=[],
            )
        )
        with self.assertRaisesMessage(JobExtractionError, "status: incomplete"):
            OpenAIResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=LISTING_TEXT,
            )

    def test_provider_error_is_translated_without_leaking_raw_message(self):
        AuthenticationError = type("AuthenticationError", (Exception,), {})
        client = RecordingClient(
            error=AuthenticationError("secret provider response body"),
        )
        with self.assertRaisesMessage(JobExtractionError, "authentication failed") as context:
            OpenAIResponsesBackend(client=client).generate_structured(
                schema_name="test_schema",
                schema={"type": "object"},
                instructions="Extract.",
                input_text=LISTING_TEXT,
            )
        self.assertNotIn("secret provider response", str(context.exception))


class OpenAIExtractorIntegrationTests(TestCase):
    @override_settings(JOB_INTAKE_AI_ENABLED=False)
    def test_extractor_cannot_activate_while_ai_switch_is_disabled(self):
        with self.assertRaisesMessage(JobExtractionError, "disabled"):
            OpenAIJobExtractor()

    def test_injected_backend_produces_reviewable_result_without_database_write(self):
        class FakeBackend:
            def generate_structured(self, **kwargs):
                return valid_payload()

        result = extract_job(
            LISTING_TEXT,
            source_url="https://example.com/jobs/biomedical-test",
            source_label="Company website",
            extractor=OpenAIJobExtractor(backend=FakeBackend()),
        )

        self.assertEqual(result["provider"]["key"], "openai_structured")
        self.assertEqual(result["provider"]["mode"], "ai")
        self.assertEqual(result["job"]["title"], "Biomedical Test Engineer")
        self.assertEqual(
            result["requirements"]["required_skills"],
            "Python\nMedical-device testing",
        )
        self.assertEqual(JobPosting.objects.count(), 0)
        self.assertEqual(JobRequirement.objects.count(), 0)
