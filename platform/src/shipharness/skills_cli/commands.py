"""CLI: `shipharness skills validate <dir>`. Wired into cli.py by `register`."""

from __future__ import annotations

from pathlib import Path

import typer


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def register(app: typer.Typer) -> None:
    skills_app = typer.Typer(help="Validate Agent Skills folders.", no_args_is_help=True)

    @skills_app.command("validate")
    def validate(
        path: Path = typer.Argument(..., help="One skill folder, or a folder of skill folders."),
    ) -> None:
        """Errors: skills-ref checks (ASCII name charset). Warnings: 500 lines, reference depth,
        missing referenced files. Exit 0 when there are no errors, 1 otherwise."""
        from shipharness.skills_cli.validate import validate_path

        reports = validate_path(path)
        errors = warnings = 0
        for report in reports:
            label = report.folder.resolve().name
            for message in report.errors:
                typer.echo(f"x {label}: {message}")
            for message in report.warnings:
                typer.echo(f"! {label}: {message}")
            if report.ok:
                typer.echo(f"+ {label}: valid (SKILL.md {report.lines} lines)")
            errors += len(report.errors)
            warnings += len(report.warnings)
        typer.echo(
            f"{_plural(len(reports), 'skill')} checked, {_plural(errors, 'error')}, "
            f"{_plural(warnings, 'warning')}"
        )
        typer.echo("Cost: $0.000000 (no model calls)")
        raise typer.Exit(1 if errors else 0)

    app.add_typer(skills_app, name="skills")
