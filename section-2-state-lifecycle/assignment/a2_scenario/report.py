"""Load a learner's layer, run scenarios, and print what happened (for check.py and grade.py)."""

from __future__ import annotations

import importlib
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from a2_scenario.measures import CRITERIA, Outcome, evaluate
from a2_scenario.runner import LayerFactory, ScenarioRun, run_scenario
from a2_scenario.scenarios import Scenario

PACKAGE = "a2_state"
_LOADED: list[str] = []


def load_layer(impl: Path) -> LayerFactory:
    """`<impl>/a2_state/layer.py` must define `ResumableStateLayer`. A new load replaces the last
    one, so one process can load two layer folders one after the other."""
    root = Path(impl).resolve()
    if not (root / PACKAGE / "layer.py").is_file():
        raise FileNotFoundError(f"{root / PACKAGE / 'layer.py'} not found (use --impl <folder>)")
    for name in [m for m in sys.modules if m == PACKAGE or m.startswith(PACKAGE + ".")]:
        del sys.modules[name]
    while _LOADED:
        old = _LOADED.pop()
        if old in sys.path:
            sys.path.remove(old)
    sys.path.insert(0, str(root))
    _LOADED.append(str(root))
    module = importlib.import_module(f"{PACKAGE}.layer")
    return module.ResumableStateLayer


def shown(path: Path) -> str:
    """`path` relative to the working directory when it is inside it (no host paths in output)."""
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return Path(path).name


@dataclass
class ScenarioResult:
    scenario: Scenario
    outcomes: list[Outcome]
    run: ScenarioRun | None
    error: str = ""

    @property
    def passed(self) -> bool:
        return all(o.fraction == 1.0 for o in self.outcomes)


def run_and_evaluate(factory: LayerFactory, scenario: Scenario, root: Path) -> ScenarioResult:
    try:
        run = run_scenario(factory, scenario, root)
    except Exception:
        error = traceback.format_exc()
        failed = [Outcome(c.key, 0.0, "the scenario did not run") for c in CRITERIA]
        return ScenarioResult(scenario, failed, None, error)
    return ScenarioResult(scenario, evaluate(run), run, "\n".join(run.errors))


def _slot_key(run: ScenarioRun, step_id: str, path: str) -> str:
    try:
        step = run.scenario.feature.step(step_id)
    except StopIteration:
        return path
    return next((s.key for s in step.slots if s.pattern().fullmatch(path)), path)


def session_lines(run: ScenarioRun) -> list[str]:
    """One line per session: what the test stand-in agent did, with redone work marked."""
    committed_in: dict[str, int] = {}
    written_in: dict[tuple[str, str], int] = {}
    lines = []
    for result in run.result.sessions:
        labels = [a.label for a in run.agent.actions if a.session == result.index]
        reads = sum(1 for label in labels if label.startswith("read "))
        shown = [f"{reads} reads"] if reads else []
        for label in labels:
            words = label.split()
            if words[0] == "read":
                continue
            if words[0] in ("write", "commit") and words[1] in committed_in:
                label += f" [REDO: {words[1]} was committed in session {committed_in[words[1]]}]"
            elif words[0] == "write":
                key = (words[1], _slot_key(run, words[1], words[2]))
                if written_in.get(key, result.index) < result.index:
                    label += f" [REDO: written in session {written_in[key]}]"
                written_in.setdefault(key, result.index)
            shown.append(label)
        for label in labels:
            words = label.split()
            if words[0] == "commit":
                committed_in.setdefault(words[1], result.index)
        lines.append(
            f"session {result.index} ({result.turns} turns, ended by {result.ended_by}): "
            + ", ".join(shown)
        )
    return lines


def print_scenario(
    result: ScenarioResult, out: Callable[[str], None] = print, details: bool = True
) -> None:
    scenario = result.scenario
    out(f"Scenario {scenario.name}: {scenario.description} (budgets {list(scenario.budgets)})")
    if details and result.run is not None:
        for line in session_lines(result.run):
            out(f"  {line}")
    titles = {c.key: c for c in CRITERIA}
    for outcome in result.outcomes:
        mark = {1.0: "PASS", 0.5: "HALF"}.get(outcome.fraction, "FAIL")
        out(f"  {mark} {outcome.key}: {outcome.detail}")
        if details and outcome.fraction < 1.0:
            out(f"       hint: {titles[outcome.key].hint}")
    if result.error:
        tail = result.error.strip().splitlines()[-12:]
        out("  ERROR in your layer (last lines of the traceback):")
        for line in tail:
            out(f"    {line}")
