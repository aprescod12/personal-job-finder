from django.test import TestCase
from django.urls import reverse

from .models import JobCalibration, JobPosting
from .validation_batch import VALIDATION_BATCH, VALIDATION_SOURCE


class CalibrationNavigationTests(TestCase):
    def test_completed_holdout_button_opens_weight_comparison(self):
        for index in range(len(VALIDATION_BATCH)):
            job = JobPosting.objects.create(
                title=f"Validation role {index + 1}",
                company=f"Validation company {index + 1}",
                source=VALIDATION_SOURCE,
            )
            JobCalibration.objects.create(
                job=job,
                human_rating=JobCalibration.HumanRating.POSSIBLE,
                opportunity_type=JobCalibration.OpportunityType.ADJACENT,
            )

        response = self.client.get(reverse("calibration_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COMPARE WEIGHT MODELS")
        self.assertContains(
            response,
            f'href="{reverse("weight_model_comparison")}"',
            html=False,
        )
