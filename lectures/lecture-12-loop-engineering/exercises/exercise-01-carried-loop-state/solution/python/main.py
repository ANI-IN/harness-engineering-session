"""carried-loop-state: the memory that turns retries into a loop.

A loop directory holds a goal, a workspace, and a loop state written by
whatever ran the earlier rounds. This runner takes the next rounds. Each
round reads the carried state to learn which criteria have already been
attempted, attempts the first criterion the state does not name, and writes
that attempt back into the state before the next round begins. Drop any one
of those three moves and the runner is N independent retries: it re-attempts
work the loop already did and spends its round budget on it.

The workspace is loaded once and edited in memory and the loop state is
carried in memory, so nothing under the loop directory is written and every
run over a committed fixture is idempotent. Nothing here reads real time:
the budget is a round count carried in the state, not a clock. SPEC.md pins
the check engine, the step rule, the state schema, and the stop reasons.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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


def unmet_criteria(files: dict[str, str], criteria: list[dict]) -> list[str]:
    """Every criterion of the goal that the workspace does not satisfy."""
    return [c["id"] for c in criteria if not run_check(files, c["check"])[0]]


def apply_step(files: dict[str, str], step: dict) -> str:
    path, line = step["path"], step["line"]
    if path not in files:
        files[path] = line + "\n"
        return f"created {path} with {line}"
    files[path] = files[path] + line + "\n"
    return f"appended {line} to {path}"


# --------------------------------------------------------------------------
# The carried state: read at the top of a round, written at the bottom.
# --------------------------------------------------------------------------


def attempted_criteria(state: dict) -> list[str]:
    """The criteria this loop has already attempted, in the order it tried them.

    Every entry in `attempted` records a round that ran to completion, so
    all `rounds_done` of them count: an attempt that ended `unmet` was still
    an attempt, and re-taking its step is the repetition this memory exists
    to prevent.
    """
    return [entry["criterion"] for entry in state["attempted"]]


def next_criterion(criteria: list[dict], attempted: list[str]) -> dict | None:
    """The first criterion in goal order that the carried state does not name."""
    return next((c for c in criteria if c["id"] not in attempted), None)


def record_attempt(state: dict, number: int, criterion: str, outcome: str) -> None:
    """Write the round into the carried state, before the next round reads it."""
    state["attempted"].append(
        {"round": number, "criterion": criterion, "outcome": outcome}
    )
    state["rounds_done"] = number


# --------------------------------------------------------------------------
# The loop.
# --------------------------------------------------------------------------


def run_loop(goal: dict, state: dict, files: dict[str, str]) -> dict:
    criteria = goal["criteria"]
    max_rounds = goal["max_rounds"]
    carried = {
        "loop": state["loop"],
        "rounds_done": state["rounds_done"],
        "attempted": [dict(entry) for entry in state["attempted"]],
    }
    rounds: list[dict] = []
    ended_on = ""
    stop: dict = {}

    while True:
        if carried["rounds_done"] >= max_rounds:
            ended_on = "budget"
            stop = {
                "after_round": carried["rounds_done"],
                "reason": (
                    f"the loop has run {carried['rounds_done']} of its "
                    f"{max_rounds} rounds, so it cannot start another"
                ),
            }
            break

        memory = attempted_criteria(carried)
        target = next_criterion(criteria, memory)
        if target is None:
            ended_on = "steps"
            stop = {
                "after_round": carried["rounds_done"],
                "reason": (
                    "the carried state names every criterion of the goal, "
                    "so there is no step left to take"
                ),
            }
            break

        number = carried["rounds_done"] + 1
        action = apply_step(files, target["step"])
        passed, detail = run_check(files, target["check"])
        record_attempt(carried, number, target["id"], "met" if passed else "unmet")
        unmet = unmet_criteria(files, criteria)
        rounds.append(
            {
                "round": number,
                "memory_read": memory,
                "chosen_criterion": target["id"],
                "step_taken": action,
                "criterion_met_after": "met" if passed else "unmet",
                "detail": detail,
                "unmet_after": unmet,
            }
        )
        if not unmet:
            ended_on = "goal"
            stop = {
                "after_round": number,
                "reason": f"every criterion of the goal is met after round {number}",
            }
            break

    unmet = unmet_criteria(files, criteria)
    if not unmet:
        verdict = "goal-reached"
    elif ended_on == "budget":
        verdict = "budget-exhausted"
    else:
        verdict = "steps-exhausted"

    return {
        "loop": goal["loop"],
        "goal": goal["goal"],
        "max_rounds": max_rounds,
        "rounds": rounds,
        "state_written": carried,
        "stop": stop,
        "unmet": unmet,
        "verdict": verdict,
    }


USAGE = "usage: main.py <loop-dir>"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    root = Path(argv[1])
    goal_path, state_path = root / "goal.json", root / "loop-state.json"
    if not goal_path.is_file() or not state_path.is_file():
        print(
            f"error: not a loop (needs goal.json and loop-state.json): {root}",
            file=sys.stderr,
        )
        return 2
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    files = load_workspace(root / "workspace")
    report = run_loop(goal, state, files)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "goal-reached" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
