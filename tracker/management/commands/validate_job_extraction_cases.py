from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tracker.services.job_extraction_evaluation import (
    DEFAULT_CASES_ROOT,
    EvaluationCaseError,
    iter_evaluation_case_directories,
    load_evaluation_case,
)


class Command(BaseCommand):
    help = "Validate every machine-readable job extraction evaluation case."

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            help="Optional path to an alternate evaluation-case directory.",
        )

    def handle(self, *args, **options):
        root = Path(options["root"] or DEFAULT_CASES_ROOT).resolve()
        directories = iter_evaluation_case_directories(root)
        if not directories:
            raise CommandError(f"No evaluation cases found in {root}.")

        cases = []
        failures = []
        for directory in directories:
            try:
                cases.append(load_evaluation_case(directory))
            except EvaluationCaseError as exc:
                failures.append(f"{directory.name}: {exc}")

        if failures:
            details = "\n".join(f"- {failure}" for failure in failures)
            raise CommandError(
                "Job extraction evaluation-case validation failed:\n" + details
            )

        for case in cases:
            self.stdout.write(
                f"- {case.case_id}: {case.title} [{case.role_category}]"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Validated {len(cases)} job extraction evaluation case(s)."
            )
        )
