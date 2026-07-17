from __future__ import annotations

from dataclasses import dataclass

from tracker.models import JobCalibration, JobRequirement

from . import strategy_matching


TRACK_TO_OPPORTUNITY = {
    "PRIORITY ROLE": JobCalibration.OpportunityType.PRIORITY,
    "ADJACENT OPPORTUNITY": JobCalibration.OpportunityType.ADJACENT,
    "OUTSIDE PRIORITY": JobCalibration.OpportunityType.OUTSIDE,
}

RATING_LABELS = dict(JobCalibration.HumanRating.choices)
OPPORTUNITY_LABELS = dict(JobCalibration.OpportunityType.choices)


@dataclass(frozen=True)
class CalibrationReportRow:
    calibration: JobCalibration
    current_result: object
    current_rating: str
    rating_status: str
    current_opportunity_type: str
    lane_status: str
    change_status: str
    score_delta: int | None
    strategy_changed: bool

    @property
    def job(self):
        return self.calibration.job

    @property
    def current_rating_label(self):
        return RATING_LABELS.get(self.current_rating, "Needs evidence")

    @property
    def current_opportunity_label(self):
        return OPPORTUNITY_LABELS.get(
            self.current_opportunity_type,
            "Needs evidence",
        )

    @property
    def saved_score_label(self):
        if self.calibration.predicted_score is None:
            return "Not scored"
        return f"{self.calibration.predicted_score}/100"

    @property
    def current_score_label(self):
        if not self.current_result.has_requirements:
            return "Not scored"
        return f"{self.current_result.score}/100"

    @property
    def score_delta_label(self):
        if self.score_delta is None:
            return "No comparison"
        if self.score_delta > 0:
            return f"+{self.score_delta}"
        return str(self.score_delta)

    @property
    def needs_attention(self):
        return self.rating_status == "REVIEW" or self.lane_status == "REVIEW"


@dataclass(frozen=True)
class CalibrationReport:
    rows: list[CalibrationReportRow]
    reviewed_count: int
    rating_comparable_count: int
    rating_aligned_count: int
    rating_agreement_percent: int
    lane_comparable_count: int
    lane_aligned_count: int
    lane_agreement_percent: int
    strategy_changed_count: int
    improved_count: int
    regressed_count: int
    attention_count: int
    matcher_version: str


def _current_rating(classification):
    return JobCalibration.PREDICTED_RATING_MAP.get(classification, "")


def _rating_status(current_rating, calibration):
    if not current_rating:
        return "NEEDS EVIDENCE"
    if current_rating == calibration.human_rating:
        return "ALIGNED"
    return "REVIEW"


def _lane_status(current_opportunity_type, calibration):
    if calibration.opportunity_type == JobCalibration.OpportunityType.UNSURE:
        return "NOT SCORED"
    if not current_opportunity_type:
        return "NEEDS EVIDENCE"
    if current_opportunity_type == calibration.opportunity_type:
        return "ALIGNED"
    return "REVIEW"


def _change_status(calibration, rating_status):
    saved_status = calibration.agreement_status

    if rating_status == "NEEDS EVIDENCE":
        return "NEEDS EVIDENCE"
    if rating_status == "ALIGNED" and saved_status != "ALIGNED":
        return "IMPROVED"
    if rating_status != "ALIGNED" and saved_status == "ALIGNED":
        return "REGRESSED"
    if rating_status == "ALIGNED":
        return "STABLE ALIGNED"
    return "STILL REVIEW"


def build_calibration_report(profile, calibrations):
    calibrations = list(calibrations)
    job_ids = [calibration.job_id for calibration in calibrations]
    requirements_by_job = {
        requirement.job_id: requirement
        for requirement in JobRequirement.objects.filter(job_id__in=job_ids)
    }

    rows = []
    matcher_version = "Current matcher"

    for calibration in calibrations:
        requirement = requirements_by_job.get(calibration.job_id)
        current_result = strategy_matching.analyze_job_match(
            profile,
            calibration.job,
            requirement,
        )
        matcher_version = getattr(
            current_result,
            "matcher_version",
            matcher_version,
        )
        current_rating = _current_rating(current_result.classification)
        rating_status = _rating_status(current_rating, calibration)
        current_opportunity_type = TRACK_TO_OPPORTUNITY.get(
            current_result.track,
            "",
        )
        lane_status = _lane_status(current_opportunity_type, calibration)
        change_status = _change_status(calibration, rating_status)

        current_score = (
            current_result.score if current_result.has_requirements else None
        )
        if current_score is None or calibration.predicted_score is None:
            score_delta = None
        else:
            score_delta = current_score - calibration.predicted_score

        strategy_changed = any(
            (
                score_delta not in (None, 0),
                current_result.classification
                != calibration.predicted_classification,
                current_result.track != calibration.predicted_track,
            )
        )

        rows.append(
            CalibrationReportRow(
                calibration=calibration,
                current_result=current_result,
                current_rating=current_rating,
                rating_status=rating_status,
                current_opportunity_type=current_opportunity_type,
                lane_status=lane_status,
                change_status=change_status,
                score_delta=score_delta,
                strategy_changed=strategy_changed,
            )
        )

    rating_comparable = [
        row for row in rows if row.rating_status != "NEEDS EVIDENCE"
    ]
    rating_aligned = [
        row for row in rating_comparable if row.rating_status == "ALIGNED"
    ]
    lane_comparable = [
        row
        for row in rows
        if row.lane_status not in {"NOT SCORED", "NEEDS EVIDENCE"}
    ]
    lane_aligned = [
        row for row in lane_comparable if row.lane_status == "ALIGNED"
    ]

    rows.sort(
        key=lambda row: (
            not row.needs_attention,
            row.change_status != "REGRESSED",
            row.job.company.casefold(),
            row.job.title.casefold(),
        )
    )

    return CalibrationReport(
        rows=rows,
        reviewed_count=len(rows),
        rating_comparable_count=len(rating_comparable),
        rating_aligned_count=len(rating_aligned),
        rating_agreement_percent=(
            round(100 * len(rating_aligned) / len(rating_comparable))
            if rating_comparable
            else 0
        ),
        lane_comparable_count=len(lane_comparable),
        lane_aligned_count=len(lane_aligned),
        lane_agreement_percent=(
            round(100 * len(lane_aligned) / len(lane_comparable))
            if lane_comparable
            else 0
        ),
        strategy_changed_count=sum(row.strategy_changed for row in rows),
        improved_count=sum(row.change_status == "IMPROVED" for row in rows),
        regressed_count=sum(row.change_status == "REGRESSED" for row in rows),
        attention_count=sum(row.needs_attention for row in rows),
        matcher_version=matcher_version,
    )
