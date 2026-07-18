from copy import deepcopy

from django.test import SimpleTestCase

from .models import JobPosting, JobRequirement
from .services.ai_job_extraction import (
    AI_EXTRACTION_INSTRUCTIONS,
    AI_JOB_EXTRACTION_JSON_SCHEMA,
    StructuredAIJobExtractor,
    build_ai_extraction_input,
)
from .services.job_extraction import (
    JobExtractionError,
    JobExtractionRequest,
    extract_job,
)


LISTING_TEXT = """
Job Title: Embedded Software Engineer
Company: Example Medical
Location: Philadelphia, PA

Required Qualifications
- Bachelor's degree in Electrical Engineering
- 2 years of embedded C experience
- Must be authorized to work in the United States; no sponsorship available

Preferred Qualifications
- Medical-device experience

Responsibilities
- Develop and test firmware for connected medical devices

Application deadline: 2026-08-15
"""


def valid_payload():
    return {
        "job": {
            "title": "Embedded Software Engineer",
            "company": "Example Medical",
            "location": "Philadelphia, PA",
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "work_arrangement": JobPosting.WorkArrangement.UNKNOWN,
            "salary_text": "",
            "date_posted": None,
            "deadline_status": JobPosting.DeadlineStatus.CONFIRMED,
            "application_deadline": "2026-08-15",
        },
        "requirements": {
            "role_family": "Embedded Software Engineering",
            "seniority_level": JobRequirement.SeniorityLevel.EARLY_CAREER,
            "industry": "Medical devices",
            "required_skills": ["Embedded C"],
            "preferred_skills": ["Medical-device experience"],
            "required_education": ["Bachelor's degree in Electrical Engineering"],
            "preferred_education": [],
            "minimum_years_experience": 2,
            "maximum_years_experience": None,
            "responsibilities": [
                "Develop and test firmware for connected medical devices"
            ],
            "certifications": [],
            "work_authorization_requirements": [
                "Must be authorized to work in the United States"
            ],
            "hard_disqualifiers": ["No sponsorship available"],
            "requirement_notes": "Review against the original listing.",
        },
        "evidence": [
            {
                "field": "minimum_years_experience",
                "quote": "2 years of embedded C experience",
                "explanation": "The listing explicitly states a two-year requirement.",
            },
            {
                "field": "hard_disqualifiers",
                "quote": "no sponsorship available",
                "explanation": "The listing explicitly excludes sponsorship.",
            },
        ],
        "warnings": ["Work arrangement was not stated."],
    }


class RecordingBackend:
    def __init__(self, payload=None):
        self.payload = payload or valid_payload()
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


class AISchemaDesignTests(SimpleTestCase):
    def test_root_and_nested_objects_reject_additional_properties(self):
        schema = AI_JOB_EXTRACTION_JSON_SCHEMA

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["job"]["additionalProperties"])
        self.assertFalse(
            schema["properties"]["requirements"]["additionalProperties"]
        )
        self.assertFalse(
            schema["properties"]["evidence"]["items"]["additionalProperties"]
        )

    def test_schema_requires_every_controlled_field(self):
        schema = AI_JOB_EXTRACTION_JSON_SCHEMA
        job_schema = schema["properties"]["job"]
        requirements_schema = schema["properties"]["requirements"]

        self.assertEqual(
            set(job_schema["required"]),
            set(job_schema["properties"]),
        )
        self.assertEqual(
            set(requirements_schema["required"]),
            set(requirements_schema["properties"]),
        )

    def test_prompt_teaches_evidence_and_unknown_handling(self):
        self.assertIn("Use only facts stated in the listing", AI_EXTRACTION_INSTRUCTIONS)
        self.assertIn("Do not infer", AI_EXTRACTION_INSTRUCTIONS)
        self.assertIn("untrusted source data", AI_EXTRACTION_INSTRUCTIONS)
        self.assertIn("short verbatim excerpts", AI_EXTRACTION_INSTRUCTIONS)

    def test_input_places_source_metadata_outside_listing_delimiters(self):
        request = JobExtractionRequest(
            listing_text=LISTING_TEXT,
            source_url="https://example.com/jobs/embedded",
            source_label="Company website",
        )

        rendered = build_ai_extraction_input(request)

        self.assertIn("Source label: Company website", rendered)
        self.assertIn("JOB LISTING START", rendered)
        self.assertIn("JOB LISTING END", rendered)
        self.assertLess(rendered.index("SOURCE METADATA"), rendered.index("JOB LISTING START"))


class StructuredAIExtractorTests(SimpleTestCase):
    def test_valid_payload_becomes_standard_reviewable_extraction(self):
        backend = RecordingBackend()
        extractor = StructuredAIJobExtractor(backend=backend)

        result = extract_job(
            LISTING_TEXT,
            source_url="https://example.com/jobs/embedded",
            source_label="Company website",
            extractor=extractor,
        )

        self.assertEqual(result["provider"]["key"], "structured_ai")
        self.assertEqual(result["provider"]["mode"], "ai")
        self.assertEqual(result["job"]["title"], "Embedded Software Engineer")
        self.assertEqual(
            result["job"]["job_url"],
            "https://example.com/jobs/embedded",
        )
        self.assertEqual(result["job"]["source"], "Company website")
        self.assertEqual(result["job"]["description"], LISTING_TEXT.strip())
        self.assertEqual(result["requirements"]["required_skills"], "Embedded C")
        self.assertIn("2 years of embedded C experience", result["evidence"][0])
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(
            backend.calls[0]["schema"],
            AI_JOB_EXTRACTION_JSON_SCHEMA,
        )

    def test_application_owned_source_metadata_overrides_model_output(self):
        payload = valid_payload()
        payload["job"]["title"] = "Embedded Software Engineer"
        backend = RecordingBackend(payload)

        result = extract_job(
            LISTING_TEXT,
            source_url="https://trusted.example/job/123",
            source_label="Trusted import",
            extractor=StructuredAIJobExtractor(backend=backend),
        )

        self.assertEqual(result["job"]["job_url"], "https://trusted.example/job/123")
        self.assertEqual(result["job"]["source"], "Trusted import")

    def test_missing_backend_fails_before_any_model_call(self):
        with self.assertRaisesMessage(
            JobExtractionError,
            "not connected to a model backend yet",
        ):
            extract_job(LISTING_TEXT, extractor=StructuredAIJobExtractor())

    def test_invalid_enum_is_rejected(self):
        payload = valid_payload()
        payload["job"]["employment_type"] = "permanent"

        with self.assertRaisesMessage(JobExtractionError, "unsupported value"):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )

    def test_extra_model_field_is_rejected(self):
        payload = valid_payload()
        payload["job"]["invented_score"] = 99

        with self.assertRaisesMessage(JobExtractionError, "unsupported keys"):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )

    def test_confirmed_deadline_without_date_is_rejected(self):
        payload = valid_payload()
        payload["job"]["application_deadline"] = None

        with self.assertRaisesMessage(
            JobExtractionError,
            "confirmed without providing a date",
        ):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )

    def test_non_iso_date_is_rejected(self):
        payload = valid_payload()
        payload["job"]["application_deadline"] = "August 15, 2026"

        with self.assertRaisesMessage(JobExtractionError, "YYYY-MM-DD"):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )

    def test_invalid_experience_range_is_rejected(self):
        payload = valid_payload()
        payload["requirements"]["minimum_years_experience"] = 5
        payload["requirements"]["maximum_years_experience"] = 2

        with self.assertRaisesMessage(
            JobExtractionError,
            "maximum experience value below the minimum",
        ):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )

    def test_evidence_objects_cannot_contain_uncontrolled_fields(self):
        payload = deepcopy(valid_payload())
        payload["evidence"][0]["confidence"] = 0.97

        with self.assertRaisesMessage(JobExtractionError, "unsupported keys"):
            extract_job(
                LISTING_TEXT,
                extractor=StructuredAIJobExtractor(
                    backend=RecordingBackend(payload)
                ),
            )
