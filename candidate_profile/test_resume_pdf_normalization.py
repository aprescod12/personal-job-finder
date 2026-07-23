from django.test import SimpleTestCase

from .services.resume_deterministic import DeterministicResumeExtractor
from .services.resume_documents import (
    DOCUMENT_PARSER_VERSION,
    PDF_LAYOUT_SCALE_WEIGHT,
    _extract_pdf_page_text,
    _normalize_text,
)
from .services.resume_extraction import ResumeExtractionRequest


PDF_LAYOUT_TEXT = """                                  TAYLOR MORGAN
              taylor.morgan@example.com  |  (555) 010-2244  |  Northfield, PA
             WEBSITE: https://taylor.example.com  |  GITHUB: https://github.com/tmorgan
EDUCATION

Northfield University – College of Engineering, Northfield, PA
Master of Science in Biomedical Engineering | GPA: 4.00                            Expected May 2027
Bachelor of Science in Electrical Engineering, Minor in Computer Science | GPA: 3.20              May 2026

RESEARCH AND PROFESSIONAL EXPERIENCE
Research Assistant | Northfield University                                             Fall 2025-Summer 2026
   •  Acquired biomedical signals for human performance research.
   •  Built a desktop application to present collected data.

Facilities Team Lead | Northfield University Athletics                              Fall 2023-Summer 2026
   •  Led student employees through daily facility operations.
   •  Coordinated task assignments and issue escalation.

PROJECTS                  ______________________________________________________________________
Wearable Medical Monitoring Device
https://github.com/tmorgan/wearable-monitor
   •  Integrated fall detection, sleep-state analysis, and hardware-
      triggered emergency alerts.
   •  Designed deterministic event handling for rapid safety response.

Event Staffing Platform
https://github.com/tmorgan/event-staffing
   •  Built role-based shift registration, waitlists, attendance tracking, and reporting.

Track Training Application
https://github.com/tmorgan/track-training
   •  Built workout logging and performance tracking for track athletes.

LEADERSHIP & ACTIVITIES    ______________________________________________________________________
NCAA Student-Athlete | Northfield University                                           Fall 2022-Spring 2026
   •  Competed at the conference level while balancing engineering coursework.

Engineering Society Outreach Chair | Northfield University                         Spring 2023-Spring 2026
   •  Organized STEM outreach events for local high school students.

RELEVANT COURSEWORK_______________________________________________________________________
Embedded Systems | Medical Device Technology | Analysis of Biomedical Signals

SKILL S
Interpersonal: Leadership, Teamwork, Communication
Programming: Python, C, C++, MATLAB, TypeScript, SQL
"""


def request_for(text: str) -> ResumeExtractionRequest:
    return ResumeExtractionRequest(
        document_text=text,
        source_id=1,
        source_sha256="a" * 64,
        source_filename="layout-resume.pdf",
        source_label="Sanitized PDF layout resume",
        document_parser_key="pypdf",
        document_parser_version=DOCUMENT_PARSER_VERSION,
    )


class RecordingLayoutPage:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def extract_text(self, **kwargs):
        self.calls.append(kwargs)
        return self.text


class PlainOnlyPage:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def extract_text(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs:
            raise TypeError("layout mode unsupported")
        return self.text


class PDFResumeNormalizationTests(SimpleTestCase):
    def test_pdf_reader_requests_layout_preserving_extraction(self):
        page = RecordingLayoutPage("Taylor Morgan")

        text, used_layout = _extract_pdf_page_text(page)

        self.assertEqual(text, "Taylor Morgan")
        self.assertTrue(used_layout)
        self.assertEqual(
            page.calls,
            [
                {
                    "extraction_mode": "layout",
                    "layout_mode_scale_weight": PDF_LAYOUT_SCALE_WEIGHT,
                }
            ],
        )

    def test_pdf_reader_falls_back_when_layout_mode_is_unavailable(self):
        page = PlainOnlyPage("Taylor Morgan")

        text, used_layout = _extract_pdf_page_text(page)

        self.assertEqual(text, "Taylor Morgan")
        self.assertFalse(used_layout)
        self.assertEqual(len(page.calls), 2)
        self.assertEqual(page.calls[1], {})

    def test_normalization_removes_pdf_noise_and_joins_wrapped_bullets(self):
        noisy = (
            "PROJECTS    ____________________\n"
            "   ▪  Designed hardware-\n"
            "      triggered alerts with a zero\u200bwidth marker.\n"
            "   ◦  Removed a soft\u00adhyphen.\n"
        )

        normalized = _normalize_text(noisy)

        self.assertIn("PROJECTS", normalized.splitlines())
        self.assertNotIn("___", normalized)
        self.assertIn(
            "• Designed hardware-triggered alerts with a zerowidth marker.",
            normalized,
        )
        self.assertIn("• Removed a softhyphen.", normalized)

    def test_deterministic_fallback_recovers_pdf_layout_resume(self):
        normalized = _normalize_text(PDF_LAYOUT_TEXT)

        result = DeterministicResumeExtractor().extract(request_for(normalized)).to_dict()

        self.assertEqual(result["provider"]["version"], "deterministic-resume-v2")
        self.assertEqual(result["identity"]["full_name"], "TAYLOR MORGAN")
        self.assertEqual(result["identity"]["email"], "taylor.morgan@example.com")
        self.assertEqual(result["identity"]["phone"], "(555) 010-2244")
        self.assertEqual(result["identity"]["location"], "Northfield, PA")
        self.assertEqual(len(result["profile"]["education"]), 1)
        self.assertEqual(
            [entry["heading"] for entry in result["profile"]["experience"]],
            ["Research Assistant", "Facilities Team Lead"],
        )
        self.assertEqual(
            [entry["heading"] for entry in result["profile"]["projects"]],
            [
                "Wearable Medical Monitoring Device",
                "Event Staffing Platform",
                "Track Training Application",
            ],
        )
        self.assertEqual(
            [entry["heading"] for entry in result["profile"]["leadership"]],
            ["NCAA Student-Athlete", "Engineering Society Outreach Chair"],
        )
        self.assertIn("Python", result["profile"]["skills"])
        self.assertIn("SQL", result["profile"]["skills"])
        self.assertIn("Leadership", result["profile"]["skills"])
        leadership_text = " ".join(
            entry["source_text"] for entry in result["profile"]["leadership"]
        )
        self.assertNotIn("Medical Device Technology", leadership_text)
        self.assertFalse(
            any(warning.startswith("No ") for warning in result["warnings"])
        )
