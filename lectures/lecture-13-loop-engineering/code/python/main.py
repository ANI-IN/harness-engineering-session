"""loop-runner: one goal, one maker, one independent checker, one clock.

The runner repeats a round (the maker takes one step, the checker grades
the whole goal) until its stopping condition fires or the loop's simulated
clock cannot afford another round. `--stop-on` selects the one signal the
stopping condition reads: `checker` reads the independent verdict over
every criterion, `maker` reads the maker's own report about the step it
just took. Nothing else differs between the two runs.

The exit code is the goal's state when the loop stopped, re-evaluated from
the workspace rather than taken from whatever signal ended the run: 0 when
every criterion is met, 1 when the loop stopped with work remaining. So a
run that stops on the maker's report exits 1 while reporting that the
maker said it was finished.

The clock is a step counter, not a wall clock: the maker's turn costs
MAKER_TICKS and the checker's turn costs CHECKER_TICKS, and a round is
only started when the remaining budget covers both. Nothing here reads
real time, and the workspace is loaded once and edited in memory, so the
committed fixture never changes and every run is idempotent. SPEC.md pins
the check engine, the maker's step rule, the checker's verdict, the
stopping condition, and the clock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAKER_TICKS = 2
CHECKER_TICKS = 1
ROUND_TICKS = MAKER_TICKS + CHECKER_TICKS


# --------------------------------------------------------------------------
# The workspace: a path-to-text map loaded once and edited in memory.
# --------------------------------------------------------------------------


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


# --------------------------------------------------------------------------
# The check engine: the deterministic stand-in for running the real command.
# --------------------------------------------------------------------------


def run_check(files: dict[str, str], check: dict) -> tuple[bool, str]:
    path = check["path"]
    if path not in files:
        return False, f"{path} missing"
    lines = files[path].split("\n")
    if check["kind"] == "key-declared-once":
        key = check["key"]
        count = sum(1 for line in lines if line.startswith(f"{key}="))
        if count == 1:
            return True, f"{path} declares {key} once"
        if count == 0:
            return False, f"{path} has no {key}= line"
        return False, f"{path} declares {key} {count} times"
    if check["kind"] == "file-has-line":
        prefix = check["prefix"]
        if any(line.startswith(prefix) for line in lines):
            return True, f"{path} has a line starting with {prefix}"
        return False, f"{path} has no line starting with {prefix}"
    raise ValueError(f"unknown check kind: {check['kind']}")


def grade_goal(files: dict[str, str], criteria: list[dict]) -> list[dict]:
    """Every criterion of the goal, checked against the workspace as it is."""
    graded = []
    for criterion in criteria:
        passed, detail = run_check(files, criterion["check"])
        graded.append(
            {
                "criterion": criterion["id"],
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )
    return graded


def with_status(graded: list[dict], status: str) -> list[dict]:
    return [row["criterion"] for row in graded if row["status"] == status]


# --------------------------------------------------------------------------
# The maker: one step per round, chosen from the loop state's memory.
# --------------------------------------------------------------------------


def apply_step(files: dict[str, str], step: dict) -> str:
    path, line = step["path"], step["line"]
    if path not in files:
        files[path] = line + "\n"
        return f"created {path} with {line}"
    files[path] = files[path] + line + "\n"
    return f"appended {line} to {path}"


def maker_turn(files: dict[str, str], criteria: list[dict], attempted: list[str]) -> dict:
    """Take one step towards the goal, then report on that step alone.

    The step is the first unmet criterion this loop has not attempted
    before, which is why the loop state exists: without the record of what
    earlier rounds tried, the maker would take the same step forever.
    """
    unmet = with_status(grade_goal(files, criteria), "fail")
    target = next(
        (c for c in criteria if c["id"] in unmet and c["id"] not in attempted), None
    )
    if target is None:
        return {
            "criterion": None,
            "action": "no step taken: every unmet criterion has already been attempted once",
            "reports_done": False,
            "why": "the maker changed nothing this round, so it claims nothing",
        }
    action = apply_step(files, target["step"])
    passed, detail = run_check(files, target["check"])
    return {
        "criterion": target["id"],
        "action": action,
        "reports_done": passed,
        "why": (
            f"{target['id']} passes after the edit, and the maker reads the step "
            "it just finished as the job being finished"
            if passed
            else f"{target['id']} still fails after the edit: {detail}"
        ),
    }


# --------------------------------------------------------------------------
# The checker: independent, and it grades the goal rather than the step.
# --------------------------------------------------------------------------


def checker_turn(files: dict[str, str], criteria: list[dict]) -> dict:
    graded = grade_goal(files, criteria)
    unmet = with_status(graded, "fail")
    return {
        "verdict": "fail" if unmet else "pass",
        "met": with_status(graded, "pass"),
        "unmet": unmet,
        "checked": graded,
    }


# --------------------------------------------------------------------------
# The loop.
# --------------------------------------------------------------------------


def run_loop(goal: dict, state: dict, files: dict[str, str], stop_on: str) -> dict:
    criteria = goal["criteria"]
    budget = goal["budget_ticks"]
    clock = state["clock"]
    carried = [dict(entry) for entry in state["rounds"]]
    rounds: list[dict] = []
    number = len(carried)
    stop: dict = {}

    while True:
        number += 1
        if clock + ROUND_TICKS > budget:
            stop = {
                "round": number,
                "clock": clock,
                "fired_on": "clock",
                "reason": (
                    f"round {number} costs {ROUND_TICKS} ticks and the {budget} tick "
                    f"budget has {budget - clock} left, so the loop cannot start it"
                ),
            }
            break

        maker = maker_turn(files, criteria, [e["criterion"] for e in carried])
        checker = checker_turn(files, criteria)
        clock += ROUND_TICKS

        signal = "pass" if (
            maker["reports_done"] if stop_on == "maker" else checker["verdict"] == "pass"
        ) else "fail"
        decision = "stop" if signal == "pass" else "continue"
        rounds.append(
            {
                "round": number,
                "clock": clock,
                "maker": maker,
                "checker": checker,
                "stopping_condition": {
                    "reads": stop_on,
                    "signal": signal,
                    "decision": decision,
                },
            }
        )
        carried.append(
            {
                "round": number,
                "criterion": maker["criterion"],
                "maker_reported": "done" if maker["reports_done"] else "not-done",
                "checker_verdict": checker["verdict"],
            }
        )
        if decision == "stop":
            stop = {
                "round": number,
                "clock": clock,
                "fired_on": stop_on,
                "reason": f"the stopping condition read the {stop_on}'s signal as pass",
            }
            break

    # The verdict is re-graded from the workspace, not taken from the signal
    # that ended the run: the loop's own stopping condition is exactly what
    # is on trial here.
    final = grade_goal(files, criteria)
    unmet = with_status(final, "fail")
    if not unmet:
        result = "goal-reached"
    elif stop["fired_on"] == "clock":
        result = "budget-exhausted"
    else:
        result = "stopped-early"

    return {
        "loop": goal["loop"],
        "goal": goal["goal"],
        "stop_on": stop_on,
        "budget_ticks": budget,
        "rounds": rounds,
        "stop": stop,
        "loop_state": {
            "loop": state["loop"],
            "clock": clock,
            "status": result,
            "rounds": carried,
        },
        "unmet": unmet,
        "result": result,
    }


USAGE = "usage: main.py <loop-dir> --stop-on=maker|checker"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[2] not in ("--stop-on=maker", "--stop-on=checker"):
        print(USAGE, file=sys.stderr)
        return 2
    root = Path(argv[1])
    goal_path, state_path = root / "goal.json", root / "loop-state.json"
    if not goal_path.is_file() or not state_path.is_file():
        print(f"error: not a loop (needs goal.json and loop-state.json): {root}", file=sys.stderr)
        return 2
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    files = load_workspace(root / "workspace")
    report = run_loop(goal, state, files, argv[2].removeprefix("--stop-on="))
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "goal-reached" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
