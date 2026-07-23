import hashlib
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from tracker.models import CareerProfile

from .models import (
    CandidateProfileClaim,
    ResumeExtractionReview,
    ResumeReviewClaim,
    ResumeSource,
)
from .services.resume_claim_review import (
    apply_approved_claims,
    close_resume_review,
    create_resume_review,
)
from .services.resume_documents import extract_resume_document_text
from .services.resume_extraction import ResumeExtractionRequest
from .services.resume_extraction_coordinator import extract_resume_with_fallback
from .views import RESUME_EXTRACTION_SESSION_KEY


RESUME_TEXT = """Amiri Prescod
amiri@example.com | +1 610-555-0100 | Villanova, PA

Professional Summary
Electrical engineer focused on biomedical sensing.

Education
Villanova University
B.S. Electrical Engineering | 2026

Experience
Engineering Intern
Medical Device Company | Summer 2025
Developed and tested embedded sensing prototypes.

Projects
Wearable Sensing Platform
Python, signal processing, embedded systems
Built a prototype for physiological data collection.

Technical Skills
Python, MATLAB, C

Leadership and Activities
Student-Athlete
Villanova Track and Field
"""


@override_settings(
    RESUME_EXTRACTOR=(
        "candidate_profile.services.resume_deterministic.DeterministicResumeExtractor"
    ),
    RESUME_FALLBACK_ENABLED=True,
)
class ResumeClaimReviewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix="resume-claim-review-tests-")
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.professional_headline = "Manual headline"
        self.profile.education_summary = "Manual education summary"
        self.profile.skills = "Manual skill one\nManual skill two"
        self.profile.save()

        content = RESUME_TEXT.encode("utf-8")
        self.source = ResumeSource.objects.create(
            profile=self.profile,
            document=SimpleUploadedFile(
                "review-resume.txt",
                content,
                content_type="text/plain",
            ),
            original_filename="review-resume.txt",
            label="Controlled review resume",
            content_type="text/plain",
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            is_active=True,
        )

    def _create_review(self):
        document = extract_resume_document_text(self.source)
        request = ResumeExtractionRequest(
            document_text=document.text,
            source_id=self.source.id,
            source_sha256=self.source.sha256,
            source_filename=self.source.original_filename,
            source_label=self.source.display_label,
            document_parser_key=document.parser_key,
            document_parser_version=document.parser_version,
        )
        extraction = extract_resume_with_fallback(request)
        return create_resume_review(
            profile=self.profile,
            source=self.source,
            document=document,
            extraction=extraction,
        )

    @staticmethod
    def _post_data(review, *, decisions=None, edits=None, action="save"):
        decisions = decisions or {}
        edits = edits or {}
        data = {"action": action}
        for claim in review.claims.all():
            prefix = f"claim-{claim.id}"
            data[f"{prefix}-decision"] = decisions.get(
                claim.claim_key,
                claim.decision,
            )
            value = edits.get(claim.claim_key, claim.reviewed_value)
            if claim.claim_type == ResumeReviewClaim.ClaimType.ENTRY:
                value = value if isinstance(value, dict) else {}
                data[f"{prefix}-heading"] = value.get("heading", "")
                data[f"{prefix}-subheading"] = value.get("subheading", "")
                data[f"{prefix}-dates"] = value.get("dates", "")
                data[f"{prefix}-details"] = "\n".join(value.get("details", []))
            else:
                data[f"{prefix}-value_text"] = value
        return data

    def _activate_review_session(self, review):
        session = self.client.session
        session[RESUME_EXTRACTION_SESSION_KEY] = {"review_id": review.id}
        session.save()

    def test_extraction_creates_persistent_pending_claims_without_profile_changes(self):
        profile_updated_at = self.profile.updated_at
        review = self._create_review()

        self.assertEqual(review.status, ResumeExtractionReview.Status.PENDING)
        self.assertGreater(review.claims.count(), 5)
        self.assertFalse(review.claims.exclude(decision="pending").exists())
        self.assertEqual(review.provider_key, "deterministic")
        self.assertEqual(review.source_sha256, self.source.sha256)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.professional_headline, "Manual headline")
        self.assertEqual(self.profile.skills, "Manual skill one\nManual skill two")
        self.assertEqual(self.profile.updated_at, profile_updated_at)
        self.assertFalse(CandidateProfileClaim.objects.exists())

    def test_new_extraction_marks_older_open_review_stale(self):
        first = self._create_review()
        second = self._create_review()

        first.refresh_from_db()
        self.assertEqual(first.status, ResumeExtractionReview.Status.STALE)
        self.assertEqual(second.status, ResumeExtractionReview.Status.PENDING)
        self.assertIsNotNone(first.completed_at)

    def test_website_save_persists_edits_and_decisions_without_applying(self):
        review = self._create_review()
        self._activate_review_session(review)
        name_claim = review.claims.get(claim_key="identity.full_name")
        python_claim = review.claims.get(
            section=ResumeReviewClaim.Section.SKILLS,
            reviewed_value="Python",
        )
        data = self._post_data(
            review,
            decisions={
                name_claim.claim_key: ResumeReviewClaim.Decision.APPROVED,
                python_claim.claim_key: ResumeReviewClaim.Decision.REJECTED,
            },
            edits={name_claim.claim_key: "Amiri J. Prescod"},
            action="save",
        )

        response = self.client.post(
            reverse("candidate_profile:resume_extraction_review"),
            data,
        )

        self.assertRedirects(
            response,
            reverse("candidate_profile:resume_extraction_review"),
        )
        name_claim.refresh_from_db()
        python_claim.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(name_claim.reviewed_value, "Amiri J. Prescod")
        self.assertEqual(name_claim.decision, ResumeReviewClaim.Decision.APPROVED)
        self.assertEqual(python_claim.decision, ResumeReviewClaim.Decision.REJECTED)
        self.assertEqual(review.status, ResumeExtractionReview.Status.IN_REVIEW)
        self.assertFalse(CandidateProfileClaim.objects.exists())

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.professional_headline, "Manual headline")
        self.assertEqual(self.profile.skills, "Manual skill one\nManual skill two")

    def test_website_apply_persists_only_approved_claim_with_provenance(self):
        review = self._create_review()
        self._activate_review_session(review)
        name_claim = review.claims.get(claim_key="identity.full_name")
        data = self._post_data(
            review,
            decisions={name_claim.claim_key: ResumeReviewClaim.Decision.APPROVED},
            edits={name_claim.claim_key: "Amiri J. Prescod"},
            action="apply",
        )

        response = self.client.post(
            reverse("candidate_profile:resume_extraction_review"),
            data,
        )

        self.assertRedirects(
            response,
            reverse("candidate_profile:resume_extraction_review"),
        )
        claim = CandidateProfileClaim.objects.get()
        self.assertEqual(claim.value, "Amiri J. Prescod")
        self.assertEqual(claim.source_sha256, self.source.sha256)
        self.assertEqual(claim.source_label, self.source.display_label)
        self.assertEqual(claim.provider_key, review.provider_key)
        self.assertEqual(claim.provider_version, review.provider_version)
        self.assertEqual(claim.document_parser_version, review.document_parser_version)
        self.assertTrue(claim.source_text)

        name_claim.refresh_from_db()
        self.assertIsNotNone(name_claim.applied_at)
        self.assertFalse(name_claim.is_editable)
        self.assertEqual(
            review.claims.filter(applied_at__isnull=False).count(),
            1,
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Amiri Prescod")
        self.assertEqual(self.profile.professional_headline, "Manual headline")

    def test_reapproved_scalar_supersedes_prior_active_claim(self):
        first_review = self._create_review()
        first_claim = first_review.claims.get(claim_key="identity.full_name")
        first_claim.decision = ResumeReviewClaim.Decision.APPROVED
        first_claim.reviewed_value = "Amiri Prescod"
        first_claim.save()
        apply_approved_claims(first_review)
        first_evidence = CandidateProfileClaim.objects.get(is_active=True)

        second_review = self._create_review()
        second_claim = second_review.claims.get(claim_key="identity.full_name")
        second_claim.decision = ResumeReviewClaim.Decision.APPROVED
        second_claim.reviewed_value = "Amiri J. Prescod"
        second_claim.save()
        apply_approved_claims(second_review)

        first_evidence.refresh_from_db()
        second_evidence = CandidateProfileClaim.objects.get(is_active=True)
        self.assertFalse(first_evidence.is_active)
        self.assertIsNotNone(first_evidence.superseded_at)
        self.assertEqual(second_evidence.value, "Amiri J. Prescod")
        self.assertEqual(CandidateProfileClaim.objects.count(), 2)

    def test_deleting_resume_keeps_approved_claim_provenance_snapshot(self):
        review = self._create_review()
        claim = review.claims.get(claim_key="identity.full_name")
        claim.decision = ResumeReviewClaim.Decision.APPROVED
        claim.save()
        apply_approved_claims(review)
        evidence_id = CandidateProfileClaim.objects.get().id

        self.source.delete()

        evidence = CandidateProfileClaim.objects.get(id=evidence_id)
        self.assertIsNone(evidence.source)
        self.assertIsNone(evidence.review_claim)
        self.assertEqual(evidence.source_sha256, self.source.sha256)
        self.assertEqual(evidence.source_filename, "review-resume.txt")

    def test_closing_unapplied_review_rejects_pending_claims(self):
        review = self._create_review()
        close_resume_review(review)

        review.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(review.status, ResumeExtractionReview.Status.DISCARDED)
        self.assertFalse(
            review.claims.exclude(decision=ResumeReviewClaim.Decision.REJECTED).exists()
        )
        self.assertEqual(self.source.review_status, ResumeSource.ReviewStatus.REJECTED)
        self.assertFalse(CandidateProfileClaim.objects.exists())

    def test_review_and_approved_claim_pages_disclose_boundaries(self):
        review = self._create_review()
        self._activate_review_session(review)

        response = self.client.get(
            reverse("candidate_profile:resume_extraction_review")
        )
        self.assertContains(response, "MANUAL PROFILE UNCHANGED")
        self.assertContains(response, "SAVE REVIEW ONLY")
        self.assertContains(response, "APPLY APPROVED CLAIMS")
        self.assertContains(response, "VIEW SOURCE EVIDENCE")

        response = self.client.get(reverse("candidate_profile:candidate_claim_list"))
        self.assertContains(response, "ACTIVE CANDIDATE CLAIMS")
        self.assertContains(response, "NOTHING HAS BEEN APPROVED YET")
