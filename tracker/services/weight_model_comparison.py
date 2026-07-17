from __future__ import annotations

from dataclasses import dataclass

from tracker.models import JobCalibration, JobRequirement
from tracker.validation_batch import VALIDATION_SOURCE

from . import strategy_matching


MODEL_A_KEY = "industry_balanced"
MODEL_B_KEY = "skills_priority"
LIVE_MODEL_KEY = MODEL_A_KEY

MODEL_A_LABEL = "Model A · Balanced industry and skills"
MODEL_B_LABEL = "Model B · Required-skills priority"

MODEL_A_WEIGHTS = {
    "role": 10,
    "required_skills": 20,
    "preferred_skills": 10,
    "education": 15,
    "experience": 15,
    "industry": 20,
    "location_arrangement": 5,
    "employment_type": 5,
}

MODEL_B_WEIGHTS = {
    **MODEL_A_WEIGHTS,
    "required_skills": 25,
    "industry": 15,
}

RATING_ORDER = {
    JobCalibration.HumanRating.NOT_ELIGIBLE: 0,
    JobCalibration.HumanRating.WEAK: 1,
    JobCalibration.HumanRating.POSSIBLE: 2,
    JobCalibration.HumanRating.GOOD: 3,
    JobCalibration.HumanRating.STRONG: 4,
}

TRACK_TO_OPPORTUNITY = {
    "PRIORITY ROLE": JobCalibration.OpportunityType.PRIORITY,
    "ADJACENT OPPORTUNITY": JobCalibration.OpportunityType.ADJACENT,
    "OUTSIDE PRIORITY": JobCalibration.OpportunityType.OUTSIDE,
}


@dataclass(frozen=True)
class ModelPrediction:
    model_key: str
    model_label: str
    score: int
    classification: str
    human_rating: str
    opportunity_type: str
    matcher_version: str

    @property
    def human_rating_label(self):
        return dict(JobCalibration.HumanRating.choices).get(
            self.human_rating,
            "Needs evidence",
        )

    @property
    def opportunity_label(self):
        return dict(JobCalibration.OpportunityType.choices).get(
            self.opportunity_type,
            "Needs evidence",
        )


@dataclass(frozen=True)
class WeightComparisonRow:
    calibration: JobCalibration
    model_a: ModelPrediction
    model_b: ModelPrediction
    model_a_distance: int | None
    model_b_distance: int | None
    outcome: str

    @property
    def job(self):
        return self.calibration.job

    @property
    def score_delta(self):
        return self.model_b.score - self.model_a.score

    @property
    def score_delta_label(self):
        if self.score_delta > 0:
            return f"+{self.score_delta}"
        return str(self.score_delta)

    @property
    def classification_changed(self):
        return self.model_a.classification != self.model_b.classification


@dataclass(frozen=True)
class ModelMetrics:
    model_key: str
    model_label: str
    weights: dict[str, int]
    reviewed_count: int
    comparable_count: int
    agreement_count: int
    agreement_percent: int
    lane_comparable_count: int
    lane_agreement_count: int
    lane_agreement_percent: int
    false_strong_count: int
    false_weak_count: int
    false_disqualification_count: int
    mean_rating_distance: float


@dataclass(frozen=True)
class WeightModelComparison:
    rows: list[WeightComparisonRow]
    model_a: ModelMetrics
    model_b: ModelMetrics
    reviewed_count: int
    expected_count: int
    validation_complete: bool
    changed_classification_count: int
    model_b_wins: int
    model_a_wins: int
    ties: int
    recommendation: str
    recommendation_detail: str
    recommended_model_key: str
    live_model_key: str = LIVE_MODEL_KEY


def _classification_to_human_rating(classification):
    return JobCalibration.PREDICTED_RATING_MAP.get(classification, "")


def _rating_distance(predicted_rating, human_rating):
    if predicted_rating not in RATING_ORDER or human_rating not in RATING_ORDER:
        return None
    return abs(RATING_ORDER[predicted_rating] - RATING_ORDER[human_rating])


def _classification_for(score, confirmed_blockers, evidence_coverage):
    if confirmed_blockers:
        return "DISQUALIFIED"
    if evidence_coverage < 35:
        return "LOW CONFIDENCE"
    if score >= 80:
        return "STRONG MATCH"
    if score >= 65:
        return "GOOD MATCH"
    if score >= 50:
        return "POSSIBLE MATCH"
    return "WEAK MATCH"


def _prediction_from_result(result, *, model_key, model_label, weights):
    available_weight = 0
    earned = 0.0

    for category in result.categories:
        if not category.available:
            continue
        new_weight = weights[category.key]
        fraction = (
            max(0.0, min(1.0, category.earned / category.weight))
            if category.weight
            else 0.0
        )
        available_weight += new_weight
        earned += new_weight * fraction

    score = round(100 * earned / available_weight) if available_weight else 0
    classification = _classification_for(
        score,
        result.confirmed_blockers,
        round(available_weight),
    )

    return ModelPrediction(
        model_key=model_key,
        model_label=model_label,
        score=score,
        classification=classification,
        human_rating=_classification_to_human_rating(classification),
        opportunity_type=TRACK_TO_OPPORTUNITY.get(result.track, ""),
        matcher_version=getattr(result, "matcher_version", "Current matcher"),
    )


def _model_metrics(model_key, model_label, weights, rows, prediction_attribute):
    comparable = []
    lane_comparable = []
    false_strong = 0
    false_weak = 0
    false_disqualification = 0
    rating_distances = []

    for row in rows:
        prediction = getattr(row, prediction_attribute)
        calibration = row.calibration

        if prediction.human_rating:
            comparable.append(row)
            distance = _rating_distance(
                prediction.human_rating,
                calibration.human_rating,
            )
            if distance is not None:
                rating_distances.append(distance)

            if (
                prediction.human_rating == JobCalibration.HumanRating.STRONG
                and calibration.human_rating != JobCalibration.HumanRating.STRONG
            ):
                false_strong += 1

            if (
                prediction.human_rating == JobCalibration.HumanRating.WEAK
                and calibration.human_rating
                in {
                    JobCalibration.HumanRating.STRONG,
                    JobCalibration.HumanRating.GOOD,
                    JobCalibration.HumanRating.POSSIBLE,
                }
            ):
                false_weak += 1

            if (
                prediction.human_rating
                == JobCalibration.HumanRating.NOT_ELIGIBLE
                and calibration.human_rating
                != JobCalibration.HumanRating.NOT_ELIGIBLE
            ):
                false_disqualification += 1

        if (
            calibration.opportunity_type
            != JobCalibration.OpportunityType.UNSURE
            and prediction.opportunity_type
        ):
            lane_comparable.append(row)

    agreements = [
        row
        for row in comparable
        if getattr(row, prediction_attribute).human_rating
        == row.calibration.human_rating
    ]
    lane_agreements = [
        row
        for row in lane_comparable
        if getattr(row, prediction_attribute).opportunity_type
        == row.calibration.opportunity_type
    ]

    return ModelMetrics(
        model_key=model_key,
        model_label=model_label,
        weights=weights,
        reviewed_count=len(rows),
        comparable_count=len(comparable),
        agreement_count=len(agreements),
        agreement_percent=(
            round(100 * len(agreements) / len(comparable)) if comparable else 0
        ),
        lane_comparable_count=len(lane_comparable),
        lane_agreement_count=len(lane_agreements),
        lane_agreement_percent=(
            round(100 * len(lane_agreements) / len(lane_comparable))
            if lane_comparable
            else 0
        ),
        false_strong_count=false_strong,
        false_weak_count=false_weak,
        false_disqualification_count=false_disqualification,
        mean_rating_distance=(
            round(sum(rating_distances) / len(rating_distances), 2)
            if rating_distances
            else 0.0
        ),
    )


def _performance_key(metrics):
    return (
        metrics.agreement_count,
        -metrics.false_strong_count,
        -metrics.false_disqualification_count,
        -metrics.false_weak_count,
        -metrics.mean_rating_distance,
    )


def build_weight_model_comparison(profile, *, expected_count=10):
    calibrations = list(
        JobCalibration.objects.select_related("job")
        .filter(job__source=VALIDATION_SOURCE)
        .order_by("job__company", "job__title")
    )
    requirements_by_job = {
        requirement.job_id: requirement
        for requirement in JobRequirement.objects.filter(
            job_id__in=[calibration.job_id for calibration in calibrations]
        )
    }

    rows = []
    for calibration in calibrations:
        requirement = requirements_by_job.get(calibration.job_id)
        current_result = strategy_matching.analyze_job_match(
            profile,
            calibration.job,
            requirement,
        )
        model_a = _prediction_from_result(
            current_result,
            model_key=MODEL_A_KEY,
            model_label=MODEL_A_LABEL,
            weights=MODEL_A_WEIGHTS,
        )
        model_b = _prediction_from_result(
            current_result,
            model_key=MODEL_B_KEY,
            model_label=MODEL_B_LABEL,
            weights=MODEL_B_WEIGHTS,
        )
        model_a_distance = _rating_distance(
            model_a.human_rating,
            calibration.human_rating,
        )
        model_b_distance = _rating_distance(
            model_b.human_rating,
            calibration.human_rating,
        )

        if model_a_distance is None or model_b_distance is None:
            outcome = "NOT COMPARABLE"
        elif model_b_distance < model_a_distance:
            outcome = "MODEL B CLOSER"
        elif model_a_distance < model_b_distance:
            outcome = "MODEL A CLOSER"
        else:
            outcome = "TIE"

        rows.append(
            WeightComparisonRow(
                calibration=calibration,
                model_a=model_a,
                model_b=model_b,
                model_a_distance=model_a_distance,
                model_b_distance=model_b_distance,
                outcome=outcome,
            )
        )

    model_a_metrics = _model_metrics(
        MODEL_A_KEY,
        MODEL_A_LABEL,
        MODEL_A_WEIGHTS,
        rows,
        "model_a",
    )
    model_b_metrics = _model_metrics(
        MODEL_B_KEY,
        MODEL_B_LABEL,
        MODEL_B_WEIGHTS,
        rows,
        "model_b",
    )

    validation_complete = len(rows) >= expected_count
    model_a_key = _performance_key(model_a_metrics)
    model_b_key = _performance_key(model_b_metrics)

    if not validation_complete:
        recommendation = "HOLDOUT INCOMPLETE"
        recommendation_detail = (
            f"Only {len(rows)} of {expected_count} validation judgments are available. "
            "Model A remains live and Model B remains experimental."
        )
        recommended_model_key = ""
    elif model_b_key > model_a_key:
        recommendation = "MODEL B PERFORMED BETTER"
        recommendation_detail = (
            "The 25-point required-skills model performed better on this holdout, but "
            "Model A remains the live matcher by the current product decision."
        )
        recommended_model_key = MODEL_B_KEY
    elif model_a_key > model_b_key:
        recommendation = "MODEL A PERFORMED BETTER"
        recommendation_detail = (
            "The active balanced model performed better on the completed holdout. "
            "Model B remains available for future comparison."
        )
        recommended_model_key = MODEL_A_KEY
    else:
        recommendation = "NO MEASURED ADVANTAGE"
        recommendation_detail = (
            "The models performed equally on the completed holdout. Model A remains "
            "live while Model B is retained as an experimental comparison."
        )
        recommended_model_key = MODEL_A_KEY

    return WeightModelComparison(
        rows=rows,
        model_a=model_a_metrics,
        model_b=model_b_metrics,
        reviewed_count=len(rows),
        expected_count=expected_count,
        validation_complete=validation_complete,
        changed_classification_count=sum(
            row.classification_changed for row in rows
        ),
        model_b_wins=sum(row.outcome == "MODEL B CLOSER" for row in rows),
        model_a_wins=sum(row.outcome == "MODEL A CLOSER" for row in rows),
        ties=sum(row.outcome == "TIE" for row in rows),
        recommendation=recommendation,
        recommendation_detail=recommendation_detail,
        recommended_model_key=recommended_model_key,
    )


__all__ = (
    "MODEL_A_WEIGHTS",
    "MODEL_B_WEIGHTS",
    "MODEL_A_KEY",
    "MODEL_B_KEY",
    "LIVE_MODEL_KEY",
    "build_weight_model_comparison",
)
