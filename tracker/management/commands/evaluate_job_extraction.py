from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tracker.services.job_extraction_evaluation import DEFAULT_CASES_ROOT
from tracker.services.job_extraction_evaluation_runner import (
    SUPPORTED_PROVIDER,
    evaluate_cases,
    render_json_report,
    render_markdown_report,
    write_report,
)


class Command(BaseCommand):
    help = (
        "Run the offline job-extraction benchmark against stored ground truth. "
        "Step 3D.4 supports only the deterministic extractor."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            default=SUPPORTED_PROVIDER,
            choices=[SUPPORTED_PROVIDER],
            help="Extraction provider to evaluate.",
        )
        parser.add_argument(
            "--format",
            dest="report_format",
            default="markdown",
            choices=["markdown", "json"],
            help="Report format printed to stdout or written to --output.",
        )
        parser.add_argument(
            "--output",
            help="Optional report file path. Parent directories are created.",
        )
        parser.add_argument(
            "--case",
            dest="case_ids",
            action="append",
            default=[],
            help="Evaluate one case ID. Repeat to select multiple cases.",
        )
        parser.add_argument(
            "--root",
            default=str(DEFAULT_CASES_ROOT),
            help="Alternate evaluation-case root directory.",
        )

    def handle(self, *args, **options):
        try:
            run = evaluate_cases(
                provider=options["provider"],
                cases_root=Path(options["root"]),
                case_ids=options["case_ids"],
            )
            if options["output"]:
                destination = write_report(
                    run,
                    output=options["output"],
                    report_format=options["report_format"],
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote {run.case_count}-case {options['report_format']} "
                        f"evaluation report to {destination}."
                    )
                )
                return

            if options["report_format"] == "json":
                report = render_json_report(run)
            else:
                report = render_markdown_report(run)
            self.stdout.write(report, ending="")
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
