from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tracker.services.job_extraction import JobExtractionError
from tracker.services.job_extraction_ai_evaluation import (
    render_ai_json_report,
    render_ai_markdown_report,
    run_ai_comparison,
    write_ai_report,
)
from tracker.services.job_extraction_evaluation import DEFAULT_CASES_ROOT


class Command(BaseCommand):
    help = (
        "Run an optional local AI job-extraction evaluation and compare it with "
        "the deterministic baseline. Live provider calls are disabled unless "
        "--allow-live-ai is supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-live-ai",
            action="store_true",
            help=(
                "Explicitly permit live model calls. One call is normally made "
                "for each selected evaluation case."
            ),
        )
        parser.add_argument(
            "--format",
            dest="report_format",
            default="markdown",
            choices=["markdown", "json"],
            help="Comparison report format printed to stdout or written to --output.",
        )
        parser.add_argument(
            "--output",
            help="Optional comparison report path. Parent directories are created.",
        )
        parser.add_argument(
            "--case",
            dest="case_ids",
            action="append",
            default=[],
            help=(
                "Evaluate one case ID. Repeat to select multiple cases. Omitting "
                "this option evaluates the full library."
            ),
        )
        parser.add_argument(
            "--root",
            default=str(DEFAULT_CASES_ROOT),
            help="Alternate evaluation-case root directory.",
        )

    def handle(self, *args, **options):
        if not options["allow_live_ai"]:
            raise CommandError(
                "Live AI evaluation is disabled. Re-run with --allow-live-ai only "
                "after confirming the local API key, enabled AI setting, selected "
                "cases, and expected provider cost."
            )

        try:
            comparison = run_ai_comparison(
                cases_root=Path(options["root"]),
                case_ids=options["case_ids"],
                allow_live_ai=True,
            )
            if options["output"]:
                destination = write_ai_report(
                    comparison,
                    output=options["output"],
                    report_format=options["report_format"],
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote {comparison.ai.evaluation.case_count}-case AI "
                        f"comparison report to {destination}."
                    )
                )
                return

            if options["report_format"] == "json":
                report = render_ai_json_report(comparison)
            else:
                report = render_ai_markdown_report(comparison)
            self.stdout.write(report, ending="")
        except (JobExtractionError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
