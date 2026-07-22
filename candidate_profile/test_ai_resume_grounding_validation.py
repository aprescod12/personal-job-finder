from copy import deepcopy

from django.test import SimpleTestCase

from .services.ai_resume_extraction import StructuredAIResumeExtractor
from .services.resume_extraction import ResumeExtractionError, ResumeExtractionRequest


RESUME_TEXT = """Case Person
case@example.com

Education
Villanova University
B.S. Electrical Engineering | 2025
M.S. Biomedical Engineering Candidate | 2027

Experience
Engineering Intern
Medical Device Company | Summer 2025
Developed and tested embedded sensing prototypes.
"""


def request_for_resume():
    return ResumeExtractionRequest(
        document_text=RESUME_TEXT,
        source_id=1,
        source_sha256="a" * 64,
        source_filename="case-resume.txt",
        source_label="Grounding validation case",
        document_parser_key="test-text",
        document_parser_version="v1",
    )


def valid_payload():
    return {
        "identity": {
            "full_name": "Case Person",
            "email": "case@example.com",
            "phone": "",
            "location": "",
            "links": [],
        },
        "profile": {
            "professional_summary": "",
            "education": [
                {
                    "heading": "Villanova University",
                    "subheading": "B.S. Electrical Engineering",
                    "dates": "2025",
                    "details": ["M.S. Biomedical Engineering Candidate"],
                    "source_text": (
                        "Villanova University\n"
                        "B.S. Electrical Engineering | 2025\n"
                        "M.S. Biomedical Engineering Candidate | 2027"
                    ),
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
                    "source_text": (
                        "Engineering Intern\n"
                        "Medical Device Company | Summer 2025\n"
                        "Developed and tested embedded sensing prototypes."
                    ),
                }
            ],
            "projects": [],
            "skills": [],
            "certifications": [],
            "leadership": [],
        },
        "evidence": [
            {
                "field": "profile.education",
                "source_text": (
                    "Villanova University\n"
                    "B.S. Electrical Engineering | 2025"
                ),
                "note": "The education entry appears in the resume.",
            }
        ],
        "warnings": [],
    }


class StructuredResumeGroundingBoundaryTests(SimpleTestCase):
    @staticmethod
    def extract(payload):
        class FakeBackend:
            def generate_structured(self, **kwargs):
                return payload

        return StructuredAIResumeExtractor(backend=FakeBackend()).extract(
            request_for_resume()
        )

    def test_document_grounded_heading_survives_incomplete_entry_excerpt(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["education"][0]["source_text"] = (
            "B.S. Electrical Engineering | 2025\n"
            "M.S. Biomedical Engineering Candidate | 2027"
        )

        result = self.extract(payload).to_dict()

        self.assertEqual(
            result["profile"]["education"][0]["heading"],
            "Villanova University",
        )
        self.assertTrue(
            any(
                "profile.education[0].heading" in warning
                for warning in result["warnings"]
            )
        )

    def test_minor_punctuation_normalization_remains_document_grounded(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["education"][0]["subheading"] = (
            "BS Electrical Engineering"
        )

        result = self.extract(payload).to_dict()

        self.assertEqual(
            result["profile"]["education"][0]["subheading"],
            "BS Electrical Engineering",
        )
        self.assertFalse(
            any(
                "profile.education[0].subheading" in warning
                for warning in result["warnings"]
            )
        )

    def test_invented_heading_is_still_rejected_against_full_document(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["education"][0]["heading"] = "Stanford University"

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "profile.education[0].heading",
        ):
            self.extract(payload)

    def test_entry_source_excerpt_must_still_be_verbatim(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["education"][0]["source_text"] = (
            "Invented education excerpt"
        )

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "not a verbatim excerpt",
        ):
            self.extract(payload)

    def test_source_excerpt_cannot_use_punctuation_normalization(self):
        payload = deepcopy(valid_payload())
        payload["profile"]["education"][0]["source_text"] = (
            "Villanova University\nBS Electrical Engineering | 2025"
        )

        with self.assertRaisesMessage(
            ResumeExtractionError,
            "not a verbatim excerpt",
        ):
            self.extract(payload)

    def test_provider_and_validator_warnings_are_combined_without_duplicates(self):
        payload = deepcopy(valid_payload())
        payload["warnings"] = ["Review manually.", "Review manually."]
        payload["profile"]["education"][0]["source_text"] = (
            "B.S. Electrical Engineering | 2025"
        )

        result = self.extract(payload).to_dict()

        self.assertEqual(result["warnings"].count("Review manually."), 1)
        self.assertTrue(
            any(
                "profile.education[0].heading" in warning
                for warning in result["warnings"]
            )
        )
