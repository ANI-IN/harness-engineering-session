"""`shipharness testgen`: filtered test generation (the integrator wires `register` into cli.py)."""

from __future__ import annotations

from pathlib import Path

import typer

from shipharness.config import Settings
from shipharness.config.prices import REPO_ROOT
from shipharness.runner.model import ModelClient, OpenAIModelClient
from shipharness.sandbox import UNSANDBOXED_BANNER
from shipharness.testgen.targets import TARGETS_FILE

COURSE_ROOT = REPO_ROOT  # where TeamTrack, .shipharness/libs/, and mutant refs resolve


class MissingKey(RuntimeError):
    pass


def load_settings() -> Settings:
    return Settings()


def make_client(settings: Settings) -> ModelClient:
    """Production OpenAI client (max_retries=0: the runner classifies and retries errors)."""
    if settings.openai_api_key is None:
        raise MissingKey("OPENAI_API_KEY is missing: add it to .env at the repo root")
    from openai import OpenAI

    from shipharness.tracing import make_tracer

    raw = OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0)
    return OpenAIModelClient(make_tracer(settings, "shipharness-testgen").wrap_openai(raw))


def _cost_line(spent_usd: float, note: str) -> None:
    typer.echo(f"Cost: ${spent_usd:.6f} ({note})")


def register(app: typer.Typer) -> None:
    @app.command()
    def testgen(
        target: str | None = typer.Option(
            None,
            help="A testgen-targets-v1 target id (e.g. TG-boltons-listutils): fills the repo, "
            "module, existing tests, mutants, and target metadata. Explicit options override.",
        ),
        targets_file: Path = typer.Option(
            TARGETS_FILE, "--targets-file", help="Targets JSONL for --target."
        ),
        repo: Path | None = typer.Option(None, help="Repository with a pytest suite."),
        module: str | None = typer.Option(None, help="Repo-relative path of the module to test."),
        layers: str = typer.Option("none", help="none or verify."),
        max_tests: int = typer.Option(10, "--max-tests", help="Test functions to evaluate."),
        sandbox: str = typer.Option(
            "",
            help="local (UNSANDBOXED, your environment) or docker; default: docker with "
            "--image, else local.",
        ),
        image: str = typer.Option("", help="Prepared container image for this repo."),
        tests: list[str] = typer.Option(  # noqa: B008
            [], "--tests", help="Existing test paths (default: the repo's configured suite)."
        ),
        visible_tests: str | None = typer.Option(
            None,
            "--visible-tests",
            help="Directory of the tests the agent runs with run_visible_tests and the verify "
            "gate runs (default: the directory that holds the --tests paths, else tests).",
        ),
        python: str | None = typer.Option(
            None,
            help="Python command inside the sandbox (default: python, or the library's venv "
            "python for a --target library).",
        ),
        out: Path | None = typer.Option(None, help="Directory for kept tests and the report."),
        doctest_modules: bool = typer.Option(
            False,
            "--doctest-modules/--no-doctest-modules",
            help="Run the existing suite with --doctest-modules, so the module's doctests "
            "count in the baseline (Filter 3: Adds coverage or catches a mutant).",
        ),
    ) -> None:
        """Generate tests for one module and keep only those that pass all five filters."""
        from shipharness.testgen.run import TestgenOptions, run_testgen
        from shipharness.testgen.targets import TargetError, resolve_target

        kind = sandbox or ("docker" if image else "local")
        if kind not in ("local", "docker"):
            typer.echo(f"x --sandbox must be local or docker, got {kind!r}")
            _cost_line(0.0, "no model calls")
            raise typer.Exit(1)
        if kind == "docker" and not image:
            typer.echo("x --sandbox docker needs --image (a prepared image for this repo)")
            _cost_line(0.0, "no model calls")
            raise typer.Exit(1)
        mutants: Path | None = None
        mutant_set: str | None = None
        metadata = None
        if target:
            try:
                resolved = resolve_target(
                    target,
                    targets_file,
                    COURSE_ROOT,
                    need_python=kind == "local" and python is None,
                )
            except TargetError as exc:
                typer.echo(f"x {exc}")
                _cost_line(0.0, "no model calls")
                raise typer.Exit(1) from None
            repo = repo or resolved.repo
            module = module or resolved.module
            tests = list(tests) or resolved.existing_tests
            python = python or resolved.python
            mutants, mutant_set, metadata = resolved.mutants, resolved.mutant_set, resolved.metadata
            typer.echo(f"target {target}: {module} in {repo}")
        if repo is None or module is None:
            typer.echo("x give --target <id>, or both --repo and --module")
            _cost_line(0.0, "no model calls")
            raise typer.Exit(1)
        if not repo.is_dir():
            typer.echo(f"x repository not found: {repo}")
            _cost_line(0.0, "no model calls")
            raise typer.Exit(1)
        settings = load_settings()
        try:
            client = make_client(settings)
        except MissingKey as exc:
            typer.echo(f"x {exc}")
            _cost_line(0.0, "no model calls")
            raise typer.Exit(1) from None
        if kind == "local":
            typer.echo(f"! {UNSANDBOXED_BANNER}: generated tests run on this machine")
        options = TestgenOptions(
            repo=repo,
            module=module,
            layers=layers,
            max_tests=max_tests,
            sandbox=kind,  # type: ignore[arg-type]
            image=image or None,
            existing_tests=list(tests),
            mutants=mutants,
            mutant_set=mutant_set,
            python=python or "python",
            out_dir=out,
            doctest_modules=doctest_modules,
            target_metadata=metadata,  # its baseline_includes_doctests wins
            visible_tests_dir=visible_tests,
        )
        result = run_testgen(options, settings, client=client)
        if result.baseline_includes_doctests:
            typer.echo("Baseline: existing suite with doctests (--doctest-modules)")
        else:
            typer.echo("Baseline: existing suite without doctests")
        evaluated = len({r.test_id for r in result.results})
        typer.echo(
            f"testgen {result.run_id}: {result.status}; kept {len(result.kept)} of "
            f"{evaluated} proposed tests"
        )
        for test_id in result.kept:
            typer.echo(f"+ {test_id}")
        for test_id, res in result.discarded.items():
            typer.echo(f"- {test_id}: filter {res.filter}: {res.reason}")
        for test_id in result.not_evaluated:
            typer.echo(f"- {test_id}: not evaluated (over --max-tests {max_tests})")
        if result.error:
            typer.echo(f"x {result.error}")
        if result.out_dir is not None and result.out_dir.exists():
            typer.echo(f"Kept tests and report: {result.out_dir}")
        _cost_line(result.cost_usd, f"testgen, model {settings.openai_model}")
        raise typer.Exit(result.exit_code)
