import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from candidate_profile.services.openai_resume_extraction import OpenAIResumeExtractor
from candidate_profile.services.resume_deterministic import DeterministicResumeExtractor
from candidate_profile.services.resume_extraction import ResumeExtractionError
from candidate_profile.services.resume_extraction_evaluation import (
    DEFAULT_CASES_ROOT,
    ResumeEvaluationError,
    evaluation_failures,
    run_comparison,
    run_evaluation,
)


class Command(BaseCommand):
    help = (
        "Evaluate resume extraction with the deterministic provider, an explicitly "
        "enabled live OpenAI provider, or a side-by-side comparison."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cases-root")
        parser.add_argument("--output")
        parser.add_argument(
            "--provider",
            choices=("deterministic", "openai", "compare"),
            default="deterministic",
            help=(
                "Choose deterministic, live OpenAI, or compare. The default remains "
                "fully offline and is the only mode used in CI."
            ),
        )
        parser.add_argument(
            "--allow-live-openai",
            action="store_true",
            help=(
                "Acknowledge that openai/compare mode makes billable network requests. "
                "RESUME_AI_ENABLED and OPENAI_API_KEY are still required."
            ),
        )
        parser.add_argument(
            "--minimum-agreement",
            type=float,
            default=0.0,
            help="Fail when the selected provider is below this agreement percentage.",
        )
        parser.add_argument(
            "--fail-on-regression",
            action="store_true",
            help="In compare mode, fail when any case is classified as a regression.",
        )

    @staticmethod
    def _openai_extractor(options):
        if not options["allow_live_openai"]:
            raise CommandError(
                "OpenAI evaluation requires --allow-live-openai so API usage cannot "
                "start accidentally."
            )
        try:
            return OpenAIResumeExtractor()
        except ResumeExtractionError as exc:
            raise CommandError(str(exc)) from exc

    def handle(self, *args, **options):
        cases_root = options.get("cases_root") or DEFAULT_CASES_ROOT
        provider = options["provider"]
        try:
            if provider == "deterministic":
                report = run_evaluation(
                    cases_root,
                    extractor=DeterministicResumeExtractor(),
                )
            elif provider == "openai":
                report = run_evaluation(
                    cases_root,
                    extractor=self._openai_extractor(options),
                )
            else:
                report = run_comparison(
                    cases_root,
                    candidate_extractor=self._openai_extractor(options),
                )
        except (ResumeEvaluationError, ResumeExtractionError) as exc:
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

        if provider == "compare":
            baseline_failures = evaluation_failures(report["baseline"])
            candidate_failures = evaluation_failures(
                report["candidate"],
                minimum_agreement=options["minimum_agreement"],
            )
            failures = [
                *(f"Baseline: {message}" for message in baseline_failures),
                *(f"Candidate: {message}" for message in candidate_failures),
            ]
            if options["fail_on_regression"] and report["regressions"]:
                failures.append(
                    f"OpenAI comparison recorded {len(report['regressions'])} "
                    "case regression(s)."
                )
        else:
            failures = evaluation_failures(
                report,
                minimum_agreement=options["minimum_agreement"],
            )

        if failures:
            raise CommandError(" ".join(failures))
