from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import CareerProfile, JobCalibration, JobPosting, JobRequirement
from .services.matching import CategoryScore, MatchResult
from .services.weight_model_comparison import (
    LIVE_MODEL_KEY,
    MODEL_A_KEY,
    MODEL_B_KEY,
    build_weight_model_comparison,
)
from .validation_batch import VALIDATION_SOURCE


class WeightModelComparisonTests(TestCase):
    def setUp(self):
        self.profile = CareerProfile.get_solo()

    def make_calibration(self, title, human_rating):
        job = JobPosting.objects.create(
            title=title,
            company=f"{title} Company",
            source=VALIDATION_SOURCE,
        )
        JobRequirement.objects.create(
            job=job,
            role_family="Engineering",
            industry="Medical devices",
            required_skills="Python",
        )
        calibration = JobCalibration.objects.create(
            job=job,
            human_rating=human_rating,
            opportunity_type=JobCalibration.OpportunityType.ADJACENT,
            notes="Blind holdout judgment.",
            predicted_score=50,
            predicted_classification="POSSIBLE MATCH",
            predicted_track="ADJACENT OPPORTUNITY",
        )
        return calibration

    def result_with_fractions(
        self,
        required_fraction,
        industry_fraction,
        *,
        other_fraction=0.683333,
        blockers=None,
    ):
        weights = {
            "role": 10,
            "required_skills": 20,
            "preferred_skills": 10,
            "education": 15,
            "experience": 15,
            "industry": 20,
            "location_arrangement": 5,
            "employment_type": 5,
        }
        categories = []
        for key, weight in weights.items():
            fraction = other_fraction
            if key == "required_skills":
                fraction = required_fraction
            elif key == "industry":
                fraction = industry_fraction
            categories.append(
                CategoryScore(
                    key=key,
                    label=key.replace("_", " ").title(),
                    weight=weight,
                    earned=weight * fraction,
                    available=True,
                    explanation="Test evidence.",
                )
            )
        result = MatchResult(
            score=0,
            classification="POSSIBLE MATCH",
            track="ADJACENT OPPORTUNITY",
            evidence_coverage=100,
            categories=categories,
            confirmed_blockers=blockers or [],
        )
        result.matcher_version = "2.3-controlled-semantic"
        return result

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_model_b_can_improve_holdout_agreement(self, analyze):
        self.make_calibration(
            "Skills-sensitive role",
            JobCalibration.HumanRating.GOOD,
        )
        analyze.return_value = self.result_with_fractions(0.9, 0.2)

        comparison = build_weight_model_comparison(
            self.profile,
            expected_count=1,
        )

        row = comparison.rows[0]
        self.assertEqual(row.model_a.classification, "POSSIBLE MATCH")
        self.assertEqual(row.model_b.classification, "GOOD MATCH")
        self.assertEqual(comparison.model_a.agreement_count, 0)
        self.assertEqual(comparison.model_b.agreement_count, 1)
        self.assertEqual(comparison.recommended_model_key, MODEL_B_KEY)
        self.assertEqual(comparison.recommendation, "MODEL B PERFORMED BETTER")
        self.assertEqual(comparison.live_model_key, MODEL_A_KEY)

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_model_a_is_kept_when_industry_weight_performs_better(self, analyze):
        self.make_calibration(
            "Industry-sensitive role",
            JobCalibration.HumanRating.GOOD,
        )
        analyze.return_value = self.result_with_fractions(
            0.2,
            0.9,
            other_fraction=0.72,
        )

        comparison = build_weight_model_comparison(
            self.profile,
            expected_count=1,
        )

        self.assertEqual(comparison.model_a.agreement_count, 1)
        self.assertEqual(comparison.model_b.agreement_count, 0)
        self.assertEqual(comparison.recommended_model_key, MODEL_A_KEY)
        self.assertEqual(comparison.recommendation, "MODEL A PERFORMED BETTER")
        self.assertEqual(LIVE_MODEL_KEY, MODEL_A_KEY)

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_disqualification_is_identical_under_both_weight_models(self, analyze):
        self.make_calibration(
            "Blocked role",
            JobCalibration.HumanRating.NOT_ELIGIBLE,
        )
        analyze.return_value = self.result_with_fractions(
            1.0,
            1.0,
            blockers=["Confirmed work-authorization conflict."],
        )

        comparison = build_weight_model_comparison(
            self.profile,
            expected_count=1,
        )
        row = comparison.rows[0]

        self.assertEqual(row.model_a.classification, "DISQUALIFIED")
        self.assertEqual(row.model_b.classification, "DISQUALIFIED")
        self.assertEqual(comparison.model_a.false_disqualification_count, 0)
        self.assertEqual(comparison.model_b.false_disqualification_count, 0)

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_incomplete_holdout_never_recommends_switching(self, analyze):
        self.make_calibration(
            "Only one reviewed role",
            JobCalibration.HumanRating.STRONG,
        )
        analyze.return_value = self.result_with_fractions(0.9, 0.2)

        comparison = build_weight_model_comparison(
            self.profile,
            expected_count=10,
        )

        self.assertFalse(comparison.validation_complete)
        self.assertEqual(comparison.recommended_model_key, "")
        self.assertEqual(comparison.recommendation, "HOLDOUT INCOMPLETE")
        self.assertEqual(comparison.live_model_key, MODEL_A_KEY)

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_report_does_not_modify_saved_judgment_or_snapshot(self, analyze):
        calibration = self.make_calibration(
            "Preserved role",
            JobCalibration.HumanRating.POSSIBLE,
        )
        analyze.return_value = self.result_with_fractions(0.9, 0.2)

        build_weight_model_comparison(self.profile, expected_count=1)
        calibration.refresh_from_db()

        self.assertEqual(calibration.human_rating, JobCalibration.HumanRating.POSSIBLE)
        self.assertEqual(calibration.predicted_score, 50)
        self.assertEqual(calibration.predicted_classification, "POSSIBLE MATCH")
        self.assertEqual(calibration.predicted_track, "ADJACENT OPPORTUNITY")

    @patch(
        "tracker.services.weight_model_comparison.strategy_matching.analyze_job_match"
    )
    def test_comparison_page_renders_both_models(self, analyze):
        self.make_calibration(
            "Rendered role",
            JobCalibration.HumanRating.GOOD,
        )
        analyze.return_value = self.result_with_fractions(0.9, 0.2)

        response = self.client.get(reverse("weight_model_comparison"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COMPARE THE WEIGHTS")
        self.assertContains(response, "REQUIRED SKILLS")
        self.assertContains(response, "INDUSTRY")
        self.assertContains(response, "Model A")
        self.assertContains(response, "Model B")
