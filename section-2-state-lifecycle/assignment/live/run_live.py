"""Run shipharness with your state layer in place of the course's (calls OpenAI and LangSmith).

Required live step (SPEC.md, "Evidence to hand in"), once, after your layer is final:

    uv run python section-2-state-lifecycle/assignment/live/run_live.py --impl <folder> \
        --forced-stops

It runs one A/B on F2-canonical with a four-session budget (three forced stops) and writes the
evidence the grader checks to `<folder>/live/`. Optional live variant: everything after `--` is
passed to the `shipharness` CLI unchanged:

    uv run python section-2-state-lifecycle/assignment/live/run_live.py --impl <folder> -- \
        ab --example F2-reworded-pm --layers instructions,state --no-reviewer --purpose assignment

Your `ResumableStateLayer` is registered under the name "state", so every harness arm that uses
the state layer uses yours. The scenarios of the self-check use the test stand-in agent instead;
this script is the only place in A2 where the course model runs.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
if str(ASSIGNMENT) not in sys.path:
    sys.path.insert(0, str(ASSIGNMENT))

from a2_scenario import live_evidence as le  # noqa: E402
from a2_scenario.report import load_layer, shown  # noqa: E402

from shipharness.harness.base import BaseLayer, register_layer  # noqa: E402

Runner = Callable[[list[str]], tuple[int, str]]


def install(impl: Path) -> type[BaseLayer]:
    """Register the layer from `<impl>/a2_state` as "state", after the course layers."""
    importlib.import_module("shipharness.harness.layers")  # the course layers register first
    layer = load_layer(impl)
    register_layer(layer)
    return layer


def _path_arg(path: Path) -> str:
    """`path` relative to the working directory when it is inside it, else absolute."""
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(Path(path).resolve())


# Four sessions end in a handoff each, and every handoff runs the visible suite: that needs more
# than the default 120 s of harness time. A caller's own HARNESS_TIMEOUT_S is kept.
LIVE_HARNESS_TIMEOUT_S = "600"
# Each session starts with the status command and the visible suite (about 225 s on the
# course machine), so the 300 s agent limit could end a session before its turn budget.
LIVE_RUN_TIMEOUT_S = "900"


def child_env(base: Mapping[str, str]) -> dict[str, str]:
    """The environment of the child process that runs the live A/B."""
    env = {**base, "PYTHONUNBUFFERED": "1"}
    env.setdefault("HARNESS_TIMEOUT_S", LIVE_HARNESS_TIMEOUT_S)
    env.setdefault("RUN_TIMEOUT_S", LIVE_RUN_TIMEOUT_S)
    return env


def run_child(impl: Path) -> Runner:
    """Run this script again with `-- <shipharness command>` and the layer installed, printing
    and keeping everything it writes to stdout."""

    def run(command: list[str]) -> tuple[int, str]:
        script = str(Path(__file__).resolve())
        argv = [sys.executable, script, "--impl", str(impl), "--", *command]
        env = child_env(os.environ)
        lines: list[str] = []
        with subprocess.Popen(argv, stdout=subprocess.PIPE, text=True, env=env) as child:
            assert child.stdout is not None
            for line in child.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                lines.append(line)
        return child.returncode, "".join(lines)

    return run


def forced_stops(
    impl: Path,
    *,
    argv: list[str],
    runner: Runner | None = None,
    runs_dir: Path | None = None,
    exports_dir: Path | None = None,
) -> int:
    """The required live step: one A/B on the four-session F2 task; evidence to `<impl>/live/`.
    Exit code: the A/B's (0 completed, 2 aborted by a cap or timeout, 1 error), 1 when the
    evidence is not valid, 2 when evidence is already there (it is never overwritten)."""
    impl = Path(impl)
    evidence = impl / le.EVIDENCE_DIR
    if (evidence / le.SUMMARY_FILE).exists():
        print(f"x {shown(evidence)} already holds a live run; move it away to run again")
        return 2
    if runs_dir is None or exports_dir is None:
        from shipharness.config import Settings

        settings = Settings()
        runs_dir = runs_dir or Path(settings.runs_dir)
        exports_dir = exports_dir or Path(settings.exports_dir)
    layer = load_layer(impl)
    layer_name = f"{layer.__module__}.{layer.__qualname__}"
    task = le.write_task(evidence)
    command = le.inner_command(_path_arg(task))
    print(
        f"Live step: {le.LIVE_EXAMPLE_ID}, session budget {list(le.LIVE_BUDGETS)}, model "
        f"{le.LIVE_MODEL}, layer {layer_name} from {shown(impl)}"
    )
    code, output = (runner or run_child(impl))(command)
    (evidence / le.OUTPUT_FILE).write_text(output, encoding="utf-8")
    ab_id = le.ab_id_from_output(output)
    if ab_id is None or not (Path(runs_dir) / ab_id / "ab.json").is_file():
        print(f"x the A/B did not finish (no A/B record); its output is in {shown(evidence)}")
        return code or 1
    le.collect_evidence(
        impl,
        ab_dir=Path(runs_dir) / ab_id,
        scores_dir=Path(exports_dir) / "scores",
        output=output,
        command=[
            f"python {shown(Path(__file__))} {' '.join(argv)}",
            "shipharness " + " ".join(le.inner_command(shown(task))),
        ],
        layer=layer_name,
    )
    problems = le.validate(impl)
    if problems:
        print(f"x live evidence in {shown(evidence)} is not valid:")
        for problem in problems:
            print(f"  - {problem}")
        return code or 1
    print(f"+ live evidence written to {shown(evidence)}: {le.describe(impl)}")
    return code


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    split = args.index("--") if "--" in args else len(args)
    parser = argparse.ArgumentParser(description="Run shipharness with your A2 state layer.")
    parser.add_argument("--impl", type=Path, default=ASSIGNMENT / "starter")
    parser.add_argument(
        "--forced-stops",
        action="store_true",
        help="the required live step: F2, four sessions, evidence to <impl>/live/",
    )
    options = parser.parse_args(args[:split])
    command = args[split + 1 :]
    if options.forced_stops:
        if command:
            parser.error("--forced-stops runs its own command; give nothing after --")
        return forced_stops(options.impl, argv=args)
    if not command:
        parser.error("give --forced-stops, or the shipharness command after --")
    layer = install(options.impl)
    print(f"state layer: {layer.__module__}.{layer.__qualname__} from {shown(options.impl)}")
    from shipharness.cli import app

    try:
        app(args=command, prog_name="shipharness")
    except SystemExit as exc:
        return int(exc.code or 0) if not isinstance(exc.code, str) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
