import hashlib
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from tracker.models import CareerProfile

from .models import ResumeSource


class ResumeSourceWorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix="job-finder-resume-tests-")
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.professional_headline = "Electrical Engineer"
        self.profile.skills = "Python\nEmbedded systems"
        self.profile.save()

    @staticmethod
    def _upload(name="amiri-resume.pdf", content=b"%PDF-1.4\nresume-v1"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def _post_upload(self, *, upload=None, label="Medical Device Resume", active=True):
        data = {
            "label": label,
            "document": upload or self._upload(),
            "notes": "Stage 5 source foundation test.",
        }
        if active:
            data["make_active"] = "on"
        return self.client.post(
            reverse("candidate_profile:resume_source_list"),
            data,
        )

    def test_resume_page_discloses_source_only_boundary(self):
        response = self.client.get(reverse("candidate_profile:resume_source_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SOURCE STORAGE ONLY")
        self.assertContains(response, "does not parse it")
        self.assertContains(response, "does not")

    def test_first_upload_is_stored_fingerprinted_and_active(self):
        content = b"%PDF-1.4\nresume-v1"
        response = self._post_upload(upload=self._upload(content=content))

        source = ResumeSource.objects.get()
        self.assertRedirects(response, reverse("candidate_profile:resume_source_list"))
        self.assertEqual(source.profile, self.profile)
        self.assertEqual(source.original_filename, "amiri-resume.pdf")
        self.assertEqual(source.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(source.file_size, len(content))
        self.assertTrue(source.is_active)
        self.assertEqual(source.review_status, ResumeSource.ReviewStatus.PENDING)

    def test_upload_does_not_change_structured_career_profile(self):
        before = {
            "professional_headline": self.profile.professional_headline,
            "skills": self.profile.skills,
            "updated_at": self.profile.updated_at,
        }

        self._post_upload()
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.professional_headline, before["professional_headline"])
        self.assertEqual(self.profile.skills, before["skills"])
        self.assertEqual(self.profile.updated_at, before["updated_at"])

    def test_exact_file_content_cannot_be_uploaded_twice(self):
        content = b"%PDF-1.4\nidentical-resume"
        self._post_upload(upload=self._upload("first.pdf", content))

        response = self._post_upload(
            upload=self._upload("renamed-copy.pdf", content),
            label="Renamed duplicate",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This exact resume file is already stored")
        self.assertEqual(ResumeSource.objects.count(), 1)

    def test_unsupported_file_extension_is_rejected(self):
        upload = SimpleUploadedFile(
            "resume.exe",
            b"not-a-resume",
            content_type="application/octet-stream",
        )

        response = self._post_upload(upload=upload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a PDF, DOCX, or plain-text resume")
        self.assertFalse(ResumeSource.objects.exists())

    def test_new_active_upload_deactivates_previous_source(self):
        self._post_upload(
            upload=self._upload("resume-v1.pdf", b"%PDF-1.4\nversion-one"),
            label="Version one",
        )
        first = ResumeSource.objects.get()

        self._post_upload(
            upload=self._upload("resume-v2.pdf", b"%PDF-1.4\nversion-two"),
            label="Version two",
        )

        first.refresh_from_db()
        second = ResumeSource.objects.exclude(id=first.id).get()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertEqual(ResumeSource.objects.filter(is_active=True).count(), 1)

    def test_stored_version_can_be_activated_explicitly(self):
        self._post_upload(
            upload=self._upload("resume-v1.pdf", b"%PDF-1.4\nversion-one"),
            label="Version one",
        )
        first = ResumeSource.objects.get()
        self._post_upload(
            upload=self._upload("resume-v2.pdf", b"%PDF-1.4\nversion-two"),
            label="Version two",
        )
        second = ResumeSource.objects.exclude(id=first.id).get()

        response = self.client.post(
            reverse("candidate_profile:activate_resume_source", args=[first.id])
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertRedirects(response, reverse("candidate_profile:resume_source_list"))
        self.assertTrue(first.is_active)
        self.assertFalse(second.is_active)
        self.assertEqual(ResumeSource.objects.filter(is_active=True).count(), 1)
