"""CLI commands: run, review, ab, replay, report, experiments. Wired into cli.py with register(app).
Every command prints a cost line at exit."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import typer

from shipharness.config import Settings
from shipharness.config.prices import REPO_ROOT
from shipharness.config.profiles import PROFILE_HELP, PROFILES
from shipharness.datasets.names import (
    EXTRA_ALIASES,
    FEATURE_ALIASES,
    UnknownFeature,
    feature_code,
    feature_label,
    section_label,
)
from shipharness.layout import DATASETS_DIR

FEATURES_FILE = REPO_ROOT / DATASETS_DIR / "teamtrack-features-v1.jsonl"
FEATURE_HELP = (
    "Feature: a readable name ("
    + ", ".join(FEATURE_ALIASES.values())
    + ") or its code (F1-F7), in any case; e.g. version-checks or F4. Earlier names still work: "
    + ", ".join(f"{alias} ({code})" for alias, code in EXTRA_ALIASES.items())
    + "."
)
SECTION_HELP = "demo-1..demo-4 (the layer stacks of Sections 1 to 4) or final."


def _section_name(section: str) -> str:
    """'Section 3: Scope and sandbox' for demo-3; the id itself for anything else (final)."""
    number = section.removeprefix("demo-")
    return section_label(int(number)) if number in ("1", "2", "3", "4") else section


def _feature_option(value: str | None) -> str | None:
    """--feature callback: an alias or a code becomes the code; an unknown name is refused (exit 2)
    with every valid name and code."""
    if value is None:
        return None
    try:
        return feature_code(value)
    except UnknownFeature as exc:
        raise typer.BadParameter(str(exc)) from None


def _settings() -> Settings:
    return Settings()


def _runtime(settings: Settings, project: str, **kw: Any) -> Any:
    from shipharness.ab.runtime import build_runtime

    return build_runtime(settings, project=project, **kw)


# LangSmith project and cost session per purpose. Class projects hold class runs only.
PURPOSE_HELP = "class (needs SHIPHARNESS_CLASS_DATE), pilot, or assignment: the LangSmith project."
OTHER_PURPOSES = {
    "pilot": ("shipharness-pilot", "pilot"),
    "assignment": ("shipharness-assignments", "assignment"),
}


def _trace_target(settings: Settings, purpose: str) -> tuple[str, str]:
    """(LangSmith project, cost session id) for a command's purpose."""
    if purpose in OTHER_PURPOSES:
        return OTHER_PURPOSES[purpose]
    if purpose != "class":
        typer.echo(f"x unknown purpose {purpose!r}: class, pilot, or assignment")
        raise typer.Exit(2)
    day = settings.shipharness_class_date
    if not day:
        typer.echo(
            "x SHIPHARNESS_CLASS_DATE is not set: set it in .env to the class day (YYYY-MM-DD) "
            "for class commands, or pass --purpose pilot for a pilot run"
        )
        raise typer.Exit(2)
    return f"shipharness-class-{day}", day


def _key_problem(settings: Settings) -> str | None:
    """None when OpenAI accepts the key for the agent model (a model metadata request: no tokens,
    no cost); otherwise the error type, never the key or the message text."""
    import openai

    from shipharness.ab import clients

    try:
        clients.make_openai_client(settings, timeout_s=30).models.retrieve(settings.openai_model)
    except openai.AuthenticationError:
        return "invalid key (AuthenticationError)"
    except openai.PermissionDeniedError:
        return "no access (PermissionDeniedError)"
    except openai.NotFoundError:
        return f"no access to {settings.openai_model} (NotFoundError)"
    except openai.APIConnectionError:
        return "OpenAI unreachable (APIConnectionError)"
    except openai.APIError as exc:
        return type(exc).__name__
    return None


def _live_guard(settings: Settings, deps: Any, arm: str = "bare") -> None:
    """Every live A/B (demo-N, final, pilot) calls OpenAI: refuse before any arm starts when the key
    is missing or rejected, or the runtime would use a stand-in model client. Never falls back to a
    scripted or recorded run; replay (RECORDING) is the explicit fallback."""
    from shipharness.runner.model import OpenAIModelClient

    key = settings.openai_api_key.get_secret_value().strip() if settings.openai_api_key else ""
    if not key:
        typer.echo(
            "x OPENAI_API_KEY is missing: live A/B runs call OpenAI and never fall back to a "
            "stand-in; add the key to .env (or use make replay, which shows RECORDING)"
        )
        raise typer.Exit(2)
    problem = _key_problem(settings)
    if problem:
        typer.echo(f"x OpenAI refused the key: {problem}; no arm was started")
        raise typer.Exit(2)
    try:
        client = deps.client_factory(arm)
    except Exception as exc:  # noqa: BLE001 - reported as one line
        typer.echo(f"x the live OpenAI client could not be created: {type(exc).__name__}")
        raise typer.Exit(2) from None
    if not isinstance(client, OpenAIModelClient):
        typer.echo("x live A/B runs need the OpenAI client; a stand-in model client is refused")
        raise typer.Exit(2)


def _purpose_runtime(settings: Settings, purpose: str, **kw: Any) -> Any:
    from shipharness.config import UnknownModelPrice

    project, session = _trace_target(settings, purpose)
    try:
        return _runtime(settings, project, session_id=session, **kw)
    except UnknownModelPrice as exc:  # e.g. the Fast tier for a model without Fast rates
        typer.echo(f"x {exc.args[0] if exc.args else exc}")
        raise typer.Exit(2) from None


ARMS_HELP = "both (A/B, default) or harness (the harness arm alone: harness in action)."
ARMS_CHOICES: dict[str, tuple[str, ...]] = {"both": ("bare", "harness"), "harness": ("harness",)}


def _load_task(dataset: Path, feature: str | None, example: str | None, variant: str) -> Any:
    from shipharness.ab.demo import ABTask

    if not dataset.is_file():
        typer.echo(f"x dataset not found: {dataset}")
        raise typer.Exit(1)
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        meta, inputs = data.get("metadata", {}), data["inputs"]
        if example and meta.get("example_id") == example:
            return ABTask.from_dataset_line(data)
        if not example and inputs["feature_id"] == feature and inputs["variant"] == variant:
            return ABTask.from_dataset_line(data)
    typer.echo(f"x no task for feature={feature} example={example} variant={variant}")
    raise typer.Exit(1)


def _exit_code(statuses: list[str]) -> int:
    if any(s == "ERROR" for s in statuses):
        return 1
    return 2 if any(s.startswith("ABORTED") for s in statuses) else 0


def record_line(record: Any, claims: dict[str, str] | None = None) -> str:
    """The line `shipharness ab` prints per arm, in plain words ("House rule 1: Tenant isolation,
    new violations: 0"). The ScoreRecord export keeps the machine field names. `claims` is the
    arm's claim per phase (AgentRunResult.claims): "agent said: done (build) · not done (test
    phase)"; without it, the record's one claim ("agent said: done")."""
    from shipharness.console.labels import claim_words, measure_words

    claim = claim_words(claims if claims is not None else {"build": record.claim})
    outcome = "passed" if record.passed_primary else "failed"
    verdict = (
        f"primary measure {outcome} · " if record.primary else ""
    )  # none registered: no verdict
    return (
        f"  {record.arm:<8} {record.status:<17} {claim} · {measure_words(record.primary)} · "
        f"{verdict}"
        f"hidden tests {record.hidden_passed} of {record.hidden_total} · "
        f"mutants killed {record.mutants_killed} of {record.mutants_total} · "
        f"reviewer {record.reviewer_verdict or 'not run'} · cost ${record.cost_usd:.4f}"
    )


def _print_record(record: Any, claims: dict[str, str] | None = None) -> None:
    typer.echo(record_line(record, claims))


def register(app: typer.Typer) -> None:
    @app.command("run")
    def run_cmd(
        feature: str = typer.Option(..., help=FEATURE_HELP, callback=_feature_option),
        checkpoint: str = typer.Option(..., help="Checkpoint tag, e.g. m1-s1-start."),
        ticket_file: Path = typer.Option(..., exists=True, dir_okay=False),
        layers: str = typer.Option("all", help="none, all, a list, or -<layer> removals."),
        workspace: Path | None = typer.Option(None, help="Existing arm workspace (git repo)."),
        from_working_tree: bool = typer.Option(False, help="Export the working tree, not a tag."),
        purpose: str = typer.Option("class", help=PURPOSE_HELP),
    ) -> None:
        """Run one agent (harness arm, or bare with --layers none) on a ticket."""
        from shipharness.ab.demo import ABTask, arm_specs, run_arm
        from shipharness.ab.runtime import cost_line
        from shipharness.ab.workspace import create_arm_workspace, new_run_id
        from shipharness.events import EventBus
        from shipharness.harness.base import parse_layers

        settings = _settings()
        names = parse_layers(layers)
        arm = "harness" if names else "bare"
        rt = _purpose_runtime(settings, purpose)
        task = ABTask(feature, checkpoint, ticket_file.read_text(encoding="utf-8"))
        run_id = new_run_id()
        ws = workspace or create_arm_workspace(
            run_id, arm, rt.course_repo, None if from_working_tree else checkpoint
        )
        spec = arm_specs(
            task,
            settings,
            ab_id=None,
            harness_layers=names,
            workspaces={arm: ws},
            run_ids={arm: run_id},
        )[arm]
        run_dir = Path(settings.runs_dir) / run_id
        deps = rt.ab_deps(None if from_working_tree else checkpoint)
        with EventBus(run_dir / "events.jsonl", ab_id=None) as bus:
            result = run_arm(task, spec, deps, bus, run_dir)
        typer.echo(f"{arm}: {result.status}, claim={result.claim}, turns={result.turns_total}")
        typer.echo(f"diff: {result.diff_path}  run log: {run_dir / 'events.jsonl'}")
        if result.error:
            typer.echo(f"error: {result.error}")
        typer.echo(cost_line(rt.cost))
        raise typer.Exit(_exit_code([result.status]))

    @app.command("review")
    def review_cmd(
        diff: Path = typer.Option(..., exists=True, dir_okay=False, help="Unified diff file."),
        task: str = typer.Option(..., help="Ticket text, or @file to read it from a file."),
        criteria: Path | None = typer.Option(None, help="Directory with SECURITY.md etc."),
        purpose: str = typer.Option("class", help=PURPOSE_HELP),
    ) -> None:
        """Blinded review of a diff by OPENAI_EVAL_MODEL (structured output)."""
        from shipharness.ab.runtime import cost_line
        from shipharness.reviewer import ReviewInput, blind, grading_criteria

        settings = _settings()
        rt = _purpose_runtime(settings, purpose)
        ticket = Path(task[1:]).read_text(encoding="utf-8") if task.startswith("@") else task
        text = grading_criteria(criteria) if criteria else grading_criteria()
        inp = ReviewInput(task=ticket, diff=blind(diff.read_bytes()), grading_criteria=text)
        outcome = rt.reviewer(inp)
        if outcome.review is not None:
            typer.echo(outcome.review.model_dump_json(indent=2))
        else:
            typer.echo(f"no verdict: {outcome.status} {outcome.detail}")
        typer.echo(cost_line(rt.cost))
        code = {"ok": 0, "cap": 2}.get(outcome.status, 1)
        raise typer.Exit(code)

    @app.command("ab")
    def ab_cmd(
        feature: str | None = typer.Option(
            None, help=f"{FEATURE_HELP} Runs its canonical variant.", callback=_feature_option
        ),
        example: str | None = typer.Option(None, help="Dataset example id, e.g. F1-canonical."),
        variant: str = typer.Option("canonical"),
        section: str | None = typer.Option(None, help=SECTION_HELP),
        layers: str | None = typer.Option(None, help="Harness arm layers (or -<layer>)."),
        dataset: Path = typer.Option(FEATURES_FILE, help="Features JSONL."),
        k: int = typer.Option(1, min=1, help="Repeat the A/B k times (every run is a dot)."),
        reviewer: bool = typer.Option(True, "--reviewer/--no-reviewer"),
        replay: str | None = typer.Option(None, help="Replay a recorded A/B or run id."),
        swap: str | None = typer.Option(
            None, help="Swap test on a recorded A/B or run id, or `latest` (of --section)."
        ),
        from_working_tree: bool = typer.Option(False, help="Export the working tree, not a tag."),
        preview: bool = typer.Option(
            True, "--preview/--no-preview", help="Board preview containers (off for batch runs)."
        ),
        purpose: str = typer.Option("class", help=PURPOSE_HELP),
        session_budget: str | None = typer.Option(
            None,
            help="Override the task's session turn budget, e.g. 12,38 (pre-registered levers).",
        ),
        profile: str = typer.Option("standard", help=PROFILE_HELP),
        arms: str = typer.Option("both", help=ARMS_HELP),
        max_tests: int | None = typer.Option(
            None,
            min=1,
            help="Demo setting for --arms harness only (make show-4): filter only the first N "
            "tests the test phase proposes. Never for an A/B.",
        ),
    ) -> None:
        """Same task, harness off vs on, both judged by the referee."""
        from shipharness.ab.demo import SINGLE_ARM_MODE, run_ab, section_layers
        from shipharness.ab.runtime import cost_line
        from shipharness.harness.base import parse_layers

        if replay or swap:
            _recorded(replay=replay, swap=swap, reviewer=reviewer, section=section, purpose=purpose)
            return
        if profile not in PROFILES:
            typer.echo(f"x unknown --profile {profile!r}: {', '.join(PROFILES)}")
            raise typer.Exit(2)
        if arms not in ARMS_CHOICES:
            typer.echo(f"x unknown --arms {arms!r}: both or harness")
            raise typer.Exit(2)
        run_arms = ARMS_CHOICES[arms]
        if max_tests is not None and run_arms != ("harness",):
            typer.echo("x --max-tests is a demo setting for --arms harness, never for an A/B")
            raise typer.Exit(2)
        settings = _settings()
        task = _load_task(dataset, feature, example, variant)
        if section == "final":  # make final hides its shell loop; this line names each A/B
            typer.echo(f"Final A/B: {feature_label(task.feature_id)}")
        if session_budget:
            try:
                turns = [int(part) for part in session_budget.split(",")]
            except ValueError:
                turns = []
            if not turns or min(turns) < 1:
                typer.echo(
                    f"x --session-budget takes positive integers, e.g. 12,38: {session_budget!r}"
                )
                raise typer.Exit(2)
            task = dataclasses.replace(task, session_budget=turns)
        if section:
            modifier = layers if layers and layers.startswith("-") else None
            names = section_layers(section, modifier)
        else:
            names = parse_layers(layers or "all")
        rt = _purpose_runtime(settings, purpose, final=section == "final", profile=profile)
        extra: dict[str, Any] = {} if preview else {"preview_factory": None}
        if max_tests is not None:
            extra["harness_kwargs"] = {"max_filtered_tests": max_tests}
        ref = None if from_working_tree else task.checkpoint
        deps = rt.ab_deps(ref, reviewer=reviewer, **extra)
        _live_guard(settings, deps, run_arms[0])
        mode = f", {SINGLE_ARM_MODE}" if run_arms == ("harness",) else ""
        statuses: list[str] = []
        for _ in range(k):
            result = run_ab(task, names, deps, section=section, arms=run_arms)  # type: ignore[arg-type]
            typer.echo(
                f"A/B {result.ab_id} ({feature_label(task.feature_id)}, layers={sorted(names)}, "
                f"profile={profile}{mode})"
            )
            for arm_run in result.arms.values():
                _print_record(arm_run.record, dict(arm_run.result.claims))
                statuses.append(arm_run.result.status)
        typer.echo(cost_line(rt.cost))
        raise typer.Exit(_exit_code(statuses))

    def _recorded(
        *,
        replay: str | None,
        swap: str | None,
        reviewer: bool,
        section: str | None = None,
        purpose: str = "class",
    ) -> None:
        from shipharness.ab.recorded import (
            RecordedDeps,
            SingleArmRecord,
            UnpinnedRecord,
            find_run_dir,
            load_ab,
            replay_ab,
        )
        from shipharness.ab.recorded import swap_test as run_swap
        from shipharness.ab.runtime import cost_line

        settings = _settings()
        wanted = (replay or swap) or ""
        try:
            run_dir = find_run_dir(Path(settings.runs_dir), wanted, section=section)
            source = load_ab(run_dir)
            source.export_ref()  # refuses a record without a pinned checkpoint commit
        except FileNotFoundError as exc:
            if wanted != "latest":
                hint = "check the A/B or run id"
            elif section:
                hint = f"run `make {section}` first, or pass AB=<id>"
            else:
                hint = "run an A/B first (make demo-N), or pass AB=<id>"
            typer.echo(f"x {exc}; {hint}")
            raise typer.Exit(2) from None
        except UnpinnedRecord as exc:
            typer.echo(f"x {exc}")
            raise typer.Exit(2) from None
        rt = _purpose_runtime(settings, purpose)
        deps = RecordedDeps(
            course_repo=rt.course_repo,
            referee_sandbox_factory=rt.referee_sandbox_factory,
            runs_dir=Path(settings.runs_dir),
            exports_dir=Path(settings.exports_dir),
            tracer=rt.tracer,
            reviewer=rt.reviewer if reviewer and replay else None,
            sandboxed=rt.sandboxed,
            container_paths=rt.sandboxed,
        )
        if swap:
            try:
                report = run_swap(run_dir, deps)
            except SingleArmRecord as exc:
                typer.echo(f"x {exc}")
                raise typer.Exit(2) from None
            verdict = "identical" if report.identical else "DIFFERENT"
            typer.echo(f"Swap test on {report.ab_id}: judged measures {verdict}")
            for arm, diffs in report.differences.items():
                for name, (before, after) in diffs.items():
                    typer.echo(f"  {arm} {name}: {before} -> {after}")
            typer.echo(cost_line(rt.cost))
            raise typer.Exit(0 if report.identical else 1)
        out = replay_ab(run_dir, deps)
        typer.echo(
            f"RECORDING: replay {out.ab_id} of {out.source_ab_id} ({out.events_replayed} events)"
        )
        for arm, record in out.records.items():
            _print_record(record, dict(source.arms[arm].result.claims))  # type: ignore[index]
        typer.echo(cost_line(rt.cost))

    @app.command("replay")
    def replay_cmd(
        run: str = typer.Argument(..., help="A/B id or run id."),
        reviewer: bool = typer.Option(False, "--reviewer/--no-reviewer"),
        purpose: str = typer.Option("class", help=PURPOSE_HELP),
    ) -> None:
        """Replay a recorded A/B (RECORDING) and re-run the referee live."""
        _recorded(replay=run, swap=None, reviewer=reviewer, purpose=purpose)

    @app.command("example")
    def example_cmd(
        section: str = typer.Option(
            ..., help="demo-1..demo-4: the layer stack and task of Sections 1 to 4."
        ),
        dataset: Path = typer.Option(FEATURES_FILE, help="Features JSONL (canonical tasks)."),
        preview: bool = typer.Option(
            True, "--preview/--no-preview", help="Board preview container (console screen 2)."
        ),
        profile: str = typer.Option("standard", help=PROFILE_HELP),
    ) -> None:
        """Constructed example: section N's layers on its canonical task, driven by scripted
        steps that make the mistake the layer exists to catch. No model, no API key, $0."""
        from shipharness.ab.demo import CONSTRUCTED_MODE
        from shipharness.ab.workspace import new_ab_id
        from shipharness.config import UnknownModelPrice
        from shipharness.examples import CONSTRUCTED_BADGE, SCENARIOS
        from shipharness.examples.run import (
            EXAMPLE_LEDGER,
            example_cost,
            example_cost_line,
            example_settings,
            example_task,
            run_example,
            summary_lines,
        )

        scenario = SCENARIOS.get(section)
        if scenario is None:
            typer.echo(f"x unknown --section {section!r}: {', '.join(SCENARIOS)}")
            raise typer.Exit(2)
        if profile not in PROFILES:
            typer.echo(f"x unknown --profile {profile!r}: {', '.join(PROFILES)}")
            raise typer.Exit(2)
        settings = example_settings(_settings())
        task = example_task(scenario, _load_task(dataset, scenario.feature, None, "canonical"))
        try:  # tracing is off: the project name is never used
            rt = _runtime(settings, "shipharness-examples", session_id="example", profile=profile)
        except UnknownModelPrice as exc:
            typer.echo(f"x {exc.args[0] if exc.args else exc}")
            raise typer.Exit(2) from None
        ab_id = new_ab_id()
        cost = example_cost(settings, Path(settings.runs_dir) / ab_id / EXAMPLE_LEDGER)
        extra: dict[str, Any] = {} if preview else {"preview_factory": None}
        deps = rt.ab_deps(task.checkpoint, reviewer=False, **extra)
        typer.echo(f"{CONSTRUCTED_BADGE} ({_section_name(section)}, {section}: {scenario.title})")
        result = run_example(scenario, task, deps, cost=cost, ab_id=ab_id)
        layers = sorted(result.arms["harness"].spec.layers)
        typer.echo(
            f"A/B {result.ab_id} ({feature_label(task.feature_id)}, layers={layers}, "
            f"profile={profile}, {CONSTRUCTED_MODE})"
        )
        for arm_run in result.arms.values():
            _print_record(arm_run.record, dict(arm_run.result.claims))
        typer.echo(f"What it demonstrates: {scenario.demonstrates}.")
        for line in summary_lines(result.run_dir):
            typer.echo(f"  {line}")
        typer.echo(example_cost_line(cost))
        raise typer.Exit(_exit_code([r.result.status for r in result.arms.values()]))

    @app.command("report")
    def report_cmd(
        exports: Path = typer.Option(Path("exports"), help="Exports directory."),
        out: Path | None = typer.Option(None, help="Output directory (default: exports)."),
        include_recorded: bool = typer.Option(False, help="Include replays."),
    ) -> None:
        """A/B report from exports/ only: dots per run and counts per arm."""
        from shipharness.ab.report import build_report, write_report
        from shipharness.console.labels import measure_label

        path = write_report(exports, out or exports, include_recorded)
        report = build_report(exports, include_recorded)
        for group in report["groups"]:
            counts = ", ".join(f"{a} {i['failing']} failing" for a, i in group["arms"].items())
            named = f"{feature_label(group['feature_id'])}; {measure_label(group['measure'])}"
            typer.echo(f"{named}: {counts}")
        typer.echo(f"report: {path}")
        typer.echo(f"Cost: $0.000000 (no model calls; runs in exports ${report['cost_usd']:.6f})")
        raise typer.Exit(0)

    @app.command("warm")
    def warm_cmd(
        profile: str = typer.Option("class", help=PROFILE_HELP),
        purpose: str = typer.Option(
            "class", help="class (checks SHIPHARNESS_CLASS_DATE first), pilot, or assignment."
        ),
        images_command: str | None = typer.Option(
            None, help="Command that builds the images (default: make images RUNTIME=<runtime>)."
        ),
        jobs: int = typer.Option(4, min=1, help="Baselines computed at the same time."),
        dataset: Path = typer.Option(FEATURES_FILE, help="Features JSONL (class tasks)."),
    ) -> None:
        """Prepare the class machine: images, containers, and baselines. No model calls."""
        from shipharness.ab import warm
        from shipharness.ab.runtime import cost_line
        from shipharness.ab.workspace import workspace_base
        from shipharness.config import UnknownModelPrice
        from shipharness.config.class_date import (
            PURPOSE_CHOICES,
            PURPOSES,
            class_date_fix,
            class_date_problem,
        )

        if profile not in PROFILES:
            typer.echo(f"x unknown --profile {profile!r}: {', '.join(PROFILES)}")
            raise typer.Exit(2)
        if purpose not in PURPOSES:
            typer.echo(f"x unknown --purpose {purpose!r}: {PURPOSE_CHOICES}")
            raise typer.Exit(2)
        loaded = _settings()
        problem = class_date_problem(loaded.shipharness_class_date) if purpose == "class" else None
        if problem:
            typer.echo(f"x {problem}: class runs need the class day (YYYY-MM-DD)")
            for line in class_date_fix():
                typer.echo(f"  {line}")
            typer.echo("warm: nothing done")
            raise typer.Exit(2)
        settings = loaded.model_copy(update={"langsmith_tracing": False})
        if settings.sandbox_mode != "docker":
            typer.echo("x SANDBOX_MODE=none: there are no containers or images to warm up")
            raise typer.Exit(2)
        try:
            rt = _runtime(settings, "shipharness-warm", session_id="warm", profile=profile)
        except UnknownModelPrice as exc:
            typer.echo(f"x {exc.args[0] if exc.args else exc}")
            raise typer.Exit(2) from None
        deps = rt.ab_deps(None, reviewer=False, preview_factory=None)
        cache = Path(settings.runs_dir).parent / "cache"
        ok = warm.warm_up(
            images=[settings.sandbox_image_agent, settings.sandbox_image_referee],
            digest=warm.image_source_digest(REPO_ROOT),
            stamp_path=cache / warm.IMAGE_STAMP,
            host=warm.WarmHost(runtime=settings.sandbox_runtime),
            images_command=images_command or f"make images RUNTIME={settings.sandbox_runtime}",
            repo=REPO_ROOT,
            tasks=warm.class_tasks(dataset),
            deps=deps,
            base=workspace_base() / "warm",
            jobs=jobs,
            echo=typer.echo,
        )
        typer.echo(cost_line(rt.cost))
        raise typer.Exit(0 if ok else 1)

    @app.command("experiments")
    def experiments_cmd(
        dataset: str = typer.Option("teamtrack-features-v1", help="LangSmith dataset."),
        split: str | None = typer.Option(None, help="Split, e.g. section-1."),
        k: int = typer.Option(2, min=1, help="num_repetitions per arm."),
        layers: str = typer.Option("all", help="Harness arm layers (or -<layer>)."),
        batch: str = typer.Option("batch-1", help="Batch label (project name and tags)."),
        reviewer: bool = typer.Option(False, "--reviewer/--no-reviewer"),
        from_working_tree: bool = typer.Option(False, help="Export the working tree, not tags."),
    ) -> None:
        """Both arms via LangSmith evaluate() with num_repetitions=k; scores to exports/."""
        from shipharness.ab.clients import make_langsmith_client
        from shipharness.ab.experiments import ExperimentPlan, run_experiments
        from shipharness.ab.runtime import cost_line
        from shipharness.harness.base import parse_layers

        settings = _settings()
        rt = _runtime(
            settings, "shipharness-experiments", experiment=True, session_id="experiments"
        )
        names = parse_layers(layers)
        plan = ExperimentPlan(
            dataset=dataset,
            split=split,
            k=k,
            harness_layers=names,
            batch=batch,
            from_working_tree=from_working_tree,
        )
        deps = rt.ab_deps(None, reviewer=reviewer)  # checkpoints come from each example
        exports = run_experiments(plan, deps, make_langsmith_client(settings))
        for arm, export in exports.items():
            typer.echo(f"{arm}: {export['name']} {export['stats']} {export.get('url') or ''}")
        typer.echo(cost_line(rt.cost))
        raise typer.Exit(0)
