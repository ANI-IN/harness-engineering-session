"""Command-line entry point: `shipharness <command>`."""

from __future__ import annotations

from pathlib import Path

import typer

from shipharness import __version__
from shipharness.config import Settings
from shipharness.datasets.names import EXTRA_ALIASES, valid_feature_names

HELP_HEADER = "Module 1: Harness Engineering for Coding Agents"
HELP = (
    f"{HELP_HEADER}\n\n"
    "Run a coding agent with and without a harness, judge both runs, and check your own repository."
    f"\n\n--feature takes a readable name or its code: {valid_feature_names()}. Earlier names "
    "still work: " + ", ".join(f"{alias} ({code})" for alias, code in EXTRA_ALIASES.items()) + "."
)

app = typer.Typer(
    name="shipharness",
    help=HELP,
    no_args_is_help=True,
    add_completion=False,
)
datasets_app = typer.Typer(help="Validate and upload the LangSmith datasets.", no_args_is_help=True)
app.add_typer(datasets_app, name="datasets")


def _register_commands() -> None:
    """Commands contributed by subsystem packages (each exposes register(app))."""
    from shipharness.ab.commands import register as register_ab
    from shipharness.checks.commands import register as register_checks
    from shipharness.kit.commands import register as register_kit
    from shipharness.skills_cli.commands import register as register_skills
    from shipharness.testgen.commands import register as register_testgen

    register_checks(app)
    register_kit(app)
    register_skills(app)
    register_testgen(app)
    register_ab(app)


_register_commands()


def load_settings() -> Settings:
    return Settings()


def print_cost_summary(spent_usd: float = 0.0, note: str = "no model calls") -> None:
    typer.echo(f"Cost: ${spent_usd:.6f} ({note})")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"shipharness {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the version."
    ),
) -> None:
    """Module 1: Harness Engineering for Coding Agents."""


@app.command()
def doctor(
    offline: bool = typer.Option(False, "--offline", help="Do not contact OpenAI or LangSmith."),
    purpose: str = typer.Option(
        "class", help="class (also checks SHIPHARNESS_CLASS_DATE), pilot, or assignment."
    ),
) -> None:
    """Check Python, tools, the container runtime, both API keys, prices, and the class date."""
    from shipharness.config.class_date import PURPOSE_CHOICES, PURPOSES
    from shipharness.doctor import run_doctor

    if purpose not in PURPOSES:
        typer.echo(f"x unknown --purpose {purpose!r}: {PURPOSE_CHOICES}")
        raise typer.Exit(2)
    report = run_doctor(load_settings(), offline=offline, purpose=purpose)
    typer.echo(report.render())
    print_cost_summary()
    raise typer.Exit(0 if report.ok else 1)


@app.command()
def up(
    port: int = typer.Option(8000, help="Port for the TeamTrack API and board."),
    db: Path = typer.Option(Path(".shipharness/teamtrack.db"), help="SQLite file to use."),
) -> None:
    """Run the bundled TeamTrack base app and board on http://127.0.0.1:<port>/board."""
    from shipharness.teamtrack_host import serve

    db.parent.mkdir(parents=True, exist_ok=True)
    typer.echo(f"TeamTrack: http://127.0.0.1:{port}/board  (API docs: /docs)")
    serve(db, port=port)


def console_server_options(verbose: bool) -> dict[str, object]:
    """uvicorn logging for the console: quiet (warnings and errors) unless verbose."""
    return {"access_log": verbose, "log_level": "info" if verbose else "warning"}


@app.command()
def console(
    port: int = typer.Option(8765, help="Port for the live console."),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print a line per request and the server's info logs."
    ),
) -> None:
    """Run the live console on http://127.0.0.1:<port>/."""
    import uvicorn

    from shipharness.console.app import create_console_app

    settings = load_settings()
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Console: http://127.0.0.1:{port}/")
    if not verbose:
        typer.echo(
            "Only warnings and errors print here; "
            "make console VERBOSE=1 (--verbose) logs each request."
        )
    console_app = create_console_app(settings.runs_dir, exports_dir=settings.exports_dir)
    uvicorn.run(console_app, host="127.0.0.1", port=port, **console_server_options(verbose))


@app.command()
def verify(
    tag: str = typer.Option("class-v1", "--tag", help="Release tag whose record to compare."),
    repo: Path = typer.Option(Path("."), "--repo", help="Your clone (default: this folder)."),
) -> None:
    """Check that your copy matches a release tag: file content and checkpoint trees."""
    import subprocess

    from shipharness.freeze import verify_copy

    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode != 0:
        typer.echo(f"x {repo} is not a git clone of the course repository")
        raise typer.Exit(2)
    record, differences = verify_copy(Path(top.stdout.strip()), tag)
    if record is None:
        typer.echo(f"x tag {tag} not found: run `git fetch --tags`, then run this again")
        raise typer.Exit(2)
    if differences:
        for line in differences:
            typer.echo(line)
        raise typer.Exit(1)
    paths = record.get("paths") or record.get("frozen_paths") or []
    trees = record.get("checkpoint_trees", {})
    typer.echo(f"your copy matches {tag}: {len(paths)} paths, {len(trees)} checkpoint trees")


@datasets_app.command("validate")
def datasets_validate(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    kind: str = typer.Option(..., help="features or testgen"),
) -> None:
    """Validate one JSONL dataset file."""
    from shipharness.datasets import check_file

    errors = check_file(path, kind)  # type: ignore[arg-type]
    for error in errors[:50]:
        typer.echo(f"x {error}")
    lines = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    typer.echo(f"{'+ valid' if not errors else 'x invalid'}: {path} ({lines} lines)")
    raise typer.Exit(0 if not errors else 1)


@datasets_app.command("upload")
def datasets_upload() -> None:
    """Validate and upload teamtrack-features-v1 (60) and testgen-targets-v1 (40) to LangSmith."""
    from langsmith import Client

    from shipharness.datasets import (
        STANDARD_DATASETS,
        build_examples,
        check_file,
        load_lines,
        upload,
    )

    settings = load_settings()
    if settings.langsmith_api_key is None:
        typer.echo("x LANGSMITH_API_KEY is missing: add it to .env at the repo root")
        raise typer.Exit(1)
    client = Client(
        api_key=settings.langsmith_api_key.get_secret_value(), api_url=settings.langsmith_endpoint
    )
    for kind, (name, path, expected) in STANDARD_DATASETS.items():
        if not path.exists():
            typer.echo(f"x {path} not found (it ships with the repository: restore it with git)")
            raise typer.Exit(1)
        problems = check_file(path, kind)
        if problems:
            typer.echo(f"x {name}: {len(problems)} problem(s); first: {problems[0]}")
            raise typer.Exit(1)
        lines = load_lines(path, kind)
        if len(lines) != expected:
            typer.echo(f"x {name}: expected {expected} examples, found {len(lines)}")
            raise typer.Exit(1)
        try:
            count = upload(client, name, build_examples(lines))
        except ValueError as exc:
            typer.echo(f"x {exc}")
            raise typer.Exit(1) from None
        typer.echo(f"+ uploaded {name}: {count} examples")
    print_cost_summary()
