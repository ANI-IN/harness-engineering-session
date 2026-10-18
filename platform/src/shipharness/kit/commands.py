"""CLI: `shipharness init --target <dir>` and `shipharness init --check <dir>` (see `register`)."""

from __future__ import annotations

from pathlib import Path

import typer

_COST = "Cost: $0.000000 (no model calls)"


def _fail(message: str) -> None:
    typer.echo(f"x {message}")
    typer.echo(_COST)
    raise typer.Exit(1)


def _install(target: Path, skills: str, force: bool) -> None:
    from shipharness.kit.files import TEMPLATES, install

    try:
        report = install(target, skills=skills, force=force)
    except ValueError as exc:
        _fail(str(exc))
        return
    typer.echo(f"Kit: {TEMPLATES} -> {target}")
    for rel in report.written:
        typer.echo(f"+ {rel}")
    for rel in report.overwritten:
        typer.echo(f"~ overwrote {rel}")
    for rel in report.skipped:
        typer.echo(f"! skipped {rel}: exists with other content (--force overwrites)")
    typer.echo(
        f"wrote {len(report.written)} files, {len(report.overwritten)} overwritten, "
        f"{len(report.skipped)} skipped, {len(report.unchanged)} unchanged"
    )
    typer.echo(f"Next: fill the REPLACE markers, then run: shipharness init --check {target}")
    typer.echo(_COST)


def _check(target: Path) -> None:
    from shipharness.kit.files import template_files
    from shipharness.kit.markers import unfilled

    if not target.is_dir():
        _fail(f"directory not found: {target}")
    markers, missing = unfilled(target)
    if len(missing) == len(template_files()):
        _fail(f"no kit files in {target}: run shipharness init --target {target} first")
    for marker in markers:
        typer.echo(f"{marker.path}:{marker.line}: {marker.text}")
    for rel in missing:
        typer.echo(f"- {rel}: not present (deleted, or never installed)")
    files = len({m.path for m in markers})
    if markers:
        typer.echo(f"x {len(markers)} REPLACE markers left in {files} files")
    else:
        typer.echo("+ no REPLACE markers left in the kit files")
    typer.echo(_COST)
    raise typer.Exit(1 if markers else 0)


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init(
        target: Path | None = typer.Option(
            None, "--target", help="Repository to copy the kit into (an existing directory)."
        ),
        check: Path | None = typer.Option(
            None, "--check", help="Repository to scan for REPLACE markers still unfilled."
        ),
        skills: str = typer.Option(
            "both", "--skills", help="Install the four skills into claude, agents, or both."
        ),
        force: bool = typer.Option(False, "--force", help="Overwrite files that differ."),
    ) -> None:
        """Copy the harness starter kit into a repository, or list its unfilled REPLACE markers.

        Deterministic: no model calls, no network. Existing files are skipped and listed unless
        --force. Exit 0 on success; with --check, 1 while markers remain."""
        if (target is None) == (check is None):
            _fail("give exactly one of --target <dir> or --check <dir>")
        if check is not None:
            _check(check)
        elif target is not None:
            _install(target, skills, force)
