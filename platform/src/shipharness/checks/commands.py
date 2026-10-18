"""`shipharness check`: run the house-rule checks against a FastAPI app directory."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from shipharness.checks.base import CheckResult
from shipharness.checks.builtin import RULE_LABELS
from shipharness.checks.runner import (
    EXIT_ERROR,
    exit_code,
    load_baseline,
    resolve_names,
    run_checks,
    stdout_to_stderr,
)
from shipharness.datasets.names import referee_check_label, rule_label

DEFAULT_RULES = "R1,R2,R3,R4,R5,R6,R7"
_SHOWN_PER_CHECK = 10


def _named(check: str) -> str:
    """'r1_tenant (House rule 1: Tenant isolation)' for a house-rule check, 'Flaky tests
    (flakiness)' for a code-named referee check; other names as is."""
    if (plain := referee_check_label(check)) != check:
        return plain
    code = RULE_LABELS.get(check, check)
    label = rule_label(code)
    return f"{check} ({label})" if label != code else check


def _cost(to_stderr: bool) -> None:
    typer.echo("Cost: $0.000000 (no model calls)", err=to_stderr)


def _render(results: list[CheckResult]) -> None:
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        typer.echo(
            f"{status}  {_named(r.check)}  new={r.new_violations} "
            f"baseline={r.baseline_violations} probes={r.total_probes} {r.duration_ms} ms"
            + (f" seed={r.seed}" if r.seed is not None else "")
        )
        new = [f for f in r.findings if f.counted and not f.baseline]
        for f in new[:_SHOWN_PER_CHECK]:
            where = f"{f.endpoint}: " if f.endpoint else ""
            typer.echo(f"      [{f.severity}] {where}{f.detail}")
        if len(new) > _SHOWN_PER_CHECK:
            typer.echo(f"      ... {len(new) - _SHOWN_PER_CHECK} more (use --json)")


def check(
    app_dir: Path = typer.Option(
        Path("platform/teamtrack"), "--app", help="App directory (the build)."
    ),
    rules: str = typer.Option(
        DEFAULT_RULES,
        "--rules",
        help="House rules by id (R1 is House rule 1: Tenant isolation, ... R7 is House rule 7: "
        "Migrations) or check names, comma separated.",
    ),
    baseline: Path | None = typer.Option(
        None, "--baseline", help="Earlier `--json` output; only new violations count."
    ),
    as_json: bool = typer.Option(False, "--json", help="Print one JSON document."),
    adapter: str | None = typer.Option(
        None, "--adapter", help="Tenant app adapter as module:attr (default: TeamTrack)."
    ),
    checkpoint: str = typer.Option("m1-base", help="Checkpoint for default exemptions."),
    feature: str = typer.Option("-", help="Feature id recorded in the context."),
    seed: int = typer.Option(
        0, help="Schemathesis / Hypothesis seed (House rule 3: API conventions)."
    ),
    params: Path | None = typer.Option(None, "--params", help="JSON file with check params."),
) -> None:
    """Check an app against the house rules. Exit 0 none new, 3 new violations, 1 error."""
    try:
        names = resolve_names(rules)
        extra = json.loads(params.read_text(encoding="utf-8")) if params else {}
        if adapter:
            extra["adapter"] = adapter
        known = load_baseline(baseline)
        if not app_dir.is_dir():
            raise ValueError(f"app directory not found: {app_dir}")
    except (ValueError, OSError) as exc:
        typer.echo(f"error: {exc}", err=True)
        _cost(as_json)
        raise typer.Exit(EXIT_ERROR) from None
    typer.echo("UNSANDBOXED: the checks import and run this app's code on this machine.", err=True)

    def progress(label: str, done: int, total: int, text: str) -> None:
        if done == total:
            typer.echo(f"  {text}", err=True)

    with stdout_to_stderr():
        results, crashed = run_checks(
            app_dir,
            names,
            checkpoint=checkpoint,
            feature_id=feature,
            seed=seed,
            params=extra,
            baseline=known,
            progress=progress,
        )
    if as_json:
        typer.echo(json.dumps({"results": [r.model_dump(mode="json") for r in results]}))
    else:
        _render(results)
    _cost(as_json)
    raise typer.Exit(exit_code(results, crashed))


def register(app: typer.Typer) -> None:
    app.command("check")(check)
