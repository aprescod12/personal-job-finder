from django.test import TestCase
from django.urls import reverse

from tracker.models import CareerProfile, JobPosting, JobRequirement
from tracker.services.strategy_matching import analyze_job_match

from candidate_profile.models import CandidateProfileClaim, ResumeReviewClaim
from candidate_profile.services.candidate_profile_composition import (
    COMPOSITION_VERSION,
    ActivatedCandidateProfileAdapter,
    activate_candidate_profile_snapshot,
    compose_candidate_profile_snapshot,
    effective_matching_profile,
)
from candidate_profile.snapshot_models import (
    CandidateProfileSnapshot,
    CandidateProfileSnapshotClaim,
)


class CandidateProfileCompositionTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()
        self.profile.full_name = "Manual Name"
        self.profile.target_roles = "Test Engineer"
        self.profile.target_industries = "Medical devices"
        self.profile.skills = "MATLAB"
        self.profile.education_summary = "Manually reviewed education note"
        self.profile.additional_context = "Manual context"
        self.profile.preferred_locations = "Philadelphia, PA"
        self.profile.save()

    def _claim(
        self,
        *,
        field_path,
        value,
        section,
        claim_key=None,
        semantic_key=None,
        is_active=True,
    ):
        index = CandidateProfileClaim.objects.count() + 1
        return CandidateProfileClaim.objects.create(
            profile=self.profile,
            section=section,
            claim_key=claim_key or f"{field_path}.{index}",
            field_path=field_path,
            semantic_key=semantic_key or f"semantic-{index:04d}",
            value=value,
            source_text=str(value),
            evidence_note="Approved test evidence",
            source_sha256=f"{index:064x}"[-64:],
            source_label="Test résumé",
            source_filename="resume.txt",
            provider_key="test-provider",
            provider_version="test-v1",
            provider_mode="ai",
            document_parser_key="plain-text",
            document_parser_version="reader-v1",
            is_active=is_active,
        )

    def test_composition_uses_active_claims_and_deduplicates_skills(self):
        name = self._claim(
            field_path="identity.full_name",
            value="Amiri Prescod",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.full_name",
        )
        python = self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
            claim_key="profile.skills.0",
        )
        self._claim(
            field_path="profile.skills",
            value="python",
            section=ResumeReviewClaim.Section.SKILLS,
            claim_key="profile.skills.1",
        )
        self._claim(
            field_path="profile.skills",
            value="C++",
            section=ResumeReviewClaim.Section.SKILLS,
            is_active=False,
        )

        snapshot, created = compose_candidate_profile_snapshot(self.profile)

        self.assertTrue(created)
        self.assertEqual(snapshot.composition_version, COMPOSITION_VERSION)
        self.assertEqual(snapshot.identity["full_name"], "Amiri Prescod")
        self.assertEqual(snapshot.profile_data["skills"], ["Python"])
        self.assertEqual(snapshot.source_claim_count, 2)
        self.assertEqual(
            set(snapshot.source_claim_links.values_list("candidate_claim_id", flat=True)),
            {name.id, python.id},
        )

    def test_newest_scalar_claim_wins_and_warning_is_visible(self):
        old = self._claim(
            field_path="identity.email",
            value="old@example.com",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.email.old",
        )
        new = self._claim(
            field_path="identity.email",
            value="new@example.com",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.email.new",
        )

        snapshot, _ = compose_candidate_profile_snapshot(self.profile)

        self.assertEqual(snapshot.identity["emails"], ["new@example.com"])
        self.assertTrue(any("Collapsed 1 older claim variant" in item for item in snapshot.warnings))
        self.assertFalse(
            snapshot.source_claim_links.filter(candidate_claim=old).exists()
        )
        self.assertTrue(
            snapshot.source_claim_links.filter(candidate_claim=new).exists()
        )

    def test_recomposing_unchanged_claims_reuses_snapshot(self):
        self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )

        first, first_created = compose_candidate_profile_snapshot(self.profile)
        second, second_created = compose_candidate_profile_snapshot(self.profile)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(CandidateProfileSnapshot.objects.count(), 1)

    def test_activation_archives_previous_version(self):
        first_claim = self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )
        first, _ = compose_candidate_profile_snapshot(self.profile)
        activate_candidate_profile_snapshot(first)

        first_claim.is_active = False
        first_claim.save(update_fields=["is_active"])
        self._claim(
            field_path="profile.skills",
            value="C++",
            section=ResumeReviewClaim.Section.SKILLS,
        )
        second, _ = compose_candidate_profile_snapshot(self.profile)
        second, changed = activate_candidate_profile_snapshot(second)

        self.assertTrue(changed)
        first.refresh_from_db()
        self.assertEqual(first.status, CandidateProfileSnapshot.Status.ARCHIVED)
        self.assertIsNotNone(first.archived_at)
        self.assertEqual(second.status, CandidateProfileSnapshot.Status.ACTIVE)
        self.assertEqual(
            CandidateProfileSnapshot.objects.filter(
                profile=self.profile,
                status=CandidateProfileSnapshot.Status.ACTIVE,
            ).count(),
            1,
        )

    def test_effective_profile_combines_snapshot_evidence_with_manual_preferences(self):
        self._claim(
            field_path="identity.full_name",
            value="Amiri Prescod",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.full_name",
        )
        self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )
        self._claim(
            field_path="profile.education",
            value={
                "heading": "B.S. Electrical Engineering",
                "subheading": "Villanova University",
                "dates": "May 2026",
                "details": ["Minor in Computer Science"],
            },
            section=ResumeReviewClaim.Section.EDUCATION,
            claim_key="profile.education.0",
        )
        snapshot, _ = compose_candidate_profile_snapshot(self.profile)
        activate_candidate_profile_snapshot(snapshot)

        effective = effective_matching_profile(self.profile)

        self.assertIsInstance(effective, ActivatedCandidateProfileAdapter)
        self.assertEqual(effective.full_name, "Amiri Prescod")
        self.assertEqual(effective.target_roles, "Test Engineer")
        self.assertEqual(effective.preferred_locations, "Philadelphia, PA")
        self.assertEqual(effective.skills.splitlines(), ["Python", "MATLAB"])
        self.assertIn("B.S. Electrical Engineering", effective.education_summary)
        self.assertIn("Manually reviewed education note", effective.education_summary)
        self.assertEqual(effective.candidate_snapshot_version, snapshot.version)

    def test_matcher_ignores_draft_and_uses_activated_snapshot(self):
        self.profile.skills = ""
        self.profile.education_summary = ""
        self.profile.additional_context = ""
        self.profile.save()
        self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )
        snapshot, _ = compose_candidate_profile_snapshot(self.profile)
        job = JobPosting.objects.create(
            title="Test Engineer",
            company="Medical Device Company",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
        )
        requirements = JobRequirement.objects.create(
            job=job,
            role_family="Test Engineer",
            industry="Medical devices",
            required_skills="Python",
        )

        before = analyze_job_match(self.profile, job, requirements)
        activate_candidate_profile_snapshot(snapshot)
        after = analyze_job_match(self.profile, job, requirements)

        self.assertIsNone(before.candidate_snapshot_version)
        self.assertTrue(any(item.requirement == "Python" for item in before.gaps))
        self.assertEqual(after.candidate_snapshot_version, snapshot.version)
        self.assertEqual(after.candidate_snapshot_id, snapshot.id)
        self.assertTrue(
            any(item.requirement == "Python" for item in after.direct_matches)
        )

    def test_composition_and_activation_do_not_mutate_manual_profile(self):
        fields_before = {
            "full_name": self.profile.full_name,
            "skills": self.profile.skills,
            "education_summary": self.profile.education_summary,
            "target_roles": self.profile.target_roles,
            "preferred_locations": self.profile.preferred_locations,
        }
        self._claim(
            field_path="identity.full_name",
            value="Amiri Prescod",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.full_name",
        )
        self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )

        snapshot, _ = compose_candidate_profile_snapshot(self.profile)
        activate_candidate_profile_snapshot(snapshot)
        self.profile.refresh_from_db()

        for field, expected in fields_before.items():
            self.assertEqual(getattr(self.profile, field), expected)


class CandidateProfileSnapshotViewTests(CandidateProfileCompositionTests):
    def test_compose_endpoint_requires_post(self):
        response = self.client.get(
            reverse("candidate_profile:compose_candidate_snapshot")
        )
        self.assertEqual(response.status_code, 405)

    def test_website_composes_previews_and_activates_explicitly(self):
        self._claim(
            field_path="identity.full_name",
            value="Amiri Prescod",
            section=ResumeReviewClaim.Section.IDENTITY,
            claim_key="identity.full_name",
        )
        self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )

        compose_response = self.client.post(
            reverse("candidate_profile:compose_candidate_snapshot")
        )
        snapshot = CandidateProfileSnapshot.objects.get()

        self.assertRedirects(
            compose_response,
            reverse(
                "candidate_profile:candidate_snapshot_detail",
                args=[snapshot.id],
            ),
        )
        self.assertEqual(snapshot.status, CandidateProfileSnapshot.Status.DRAFT)

        detail = self.client.get(
            reverse(
                "candidate_profile:candidate_snapshot_detail",
                args=[snapshot.id],
            )
        )
        self.assertContains(detail, "NO MATCHING EFFECT")
        self.assertContains(detail, "Amiri Prescod")
        self.assertContains(detail, "Python")
        self.assertContains(detail, "ACTIVATE VERSION 1")

        activate_response = self.client.post(
            reverse(
                "candidate_profile:activate_candidate_snapshot",
                args=[snapshot.id],
            )
        )
        snapshot.refresh_from_db()
        self.assertRedirects(
            activate_response,
            reverse(
                "candidate_profile:candidate_snapshot_detail",
                args=[snapshot.id],
            ),
        )
        self.assertEqual(snapshot.status, CandidateProfileSnapshot.Status.ACTIVE)

        detail = self.client.get(
            reverse(
                "candidate_profile:candidate_snapshot_detail",
                args=[snapshot.id],
            )
        )
        self.assertContains(detail, "USED BY MATCHING")
        self.assertContains(detail, "CLAIMS USED TO BUILD THIS VERSION")

    def test_snapshot_lineage_is_immutable_after_claim_changes(self):
        claim = self._claim(
            field_path="profile.skills",
            value="Python",
            section=ResumeReviewClaim.Section.SKILLS,
        )
        snapshot, _ = compose_candidate_profile_snapshot(self.profile)
        link = CandidateProfileSnapshotClaim.objects.get(snapshot=snapshot)

        claim.value = "Changed later"
        claim.save(update_fields=["value"])
        link.refresh_from_db()
        snapshot.refresh_from_db()

        self.assertEqual(link.value, "Python")
        self.assertEqual(snapshot.profile_data["skills"], ["Python"])
