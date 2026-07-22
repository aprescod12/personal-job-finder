import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from candidate_profile.services.resume_extraction_evaluation import (
    DEFAULT_CASES_ROOT,
    ResumeEvaluationError,
    run_evaluation,
)


class Command(BaseCommand):
    help = "Run the offline deterministic resume-extraction evaluation suite."

    def add_arguments(self, parser):
        parser.add_argument("--cases-root")
        parser.add_argument("--output")
        parser.add_argument(
            "--minimum-agreement",
            type=float,
            default=0.0,
            help="Fail when aggregate agreement is below this percentage.",
        )

    def handle(self, *args, **options):
        cases_root = options.get("cases_root") or DEFAULT_CASES_ROOT
        try:
            report = run_evaluation(cases_root)
        except ResumeEvaluationError as exc:
            raise CommandError(str(exc)) from exc

        output_text = json.dumps(report, indent=2, sort_keys=True)
        output_path = options.get("output")
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output_text + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote resume evaluation report to {path}")
        else:
            self.stdout.write(output_text)

        if report["forbidden_hit_count"]:
            raise CommandError("Resume evaluation produced forbidden claims.")
        if report["critical_passed"] != report["critical_total"]:
            raise CommandError("Resume evaluation missed one or more critical claims.")
        if report["agreement_percent"] < options["minimum_agreement"]:
            raise CommandError(
                f"Agreement {report['agreement_percent']}% is below the required "
                f"{options['minimum_agreement']}%."
            )
