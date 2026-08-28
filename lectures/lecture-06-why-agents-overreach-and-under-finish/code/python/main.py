"""scope-run: a scripted worker meets a task boundary, or does not.

The demo is behavioral. A deterministic worker replays the same session
script (a fake agent's recorded stream of "the next thing I want to do":
steps on the assigned feature interleaved with tangents it noticed along
the way) against two workspaces that differ by one line, the WIP limit in
AGENTS.md. Without the boundary the worker acts on every impulse: five
features end the session in flight and the step budget runs out before
the assigned feature's verification ever runs (exit 1). With the boundary
the same tangent impulses are parked into a queue for zero steps, the
assigned feature finishes verified with budget to spare (exit 0), and the
parked queue records the scope the session refused to spend. Every rule
and every step cost is pinned in SPEC.md; nothing here is narrated.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_BUDGET = 12
WIP_RULE = re.compile(r"^- WIP limit: (\d+)$", re.MULTILINE)


def load_workspace(workspace: Path) -> tuple[list[dict], int | None]:
    """The feature list (scope surface) and the boundary, if AGENTS.md draws one."""
    feature_list = json.loads((workspace / "feature_list.json").read_text(encoding="utf-8"))
    rules = (workspace / "AGENTS.md").read_text(encoding="utf-8")
    match = WIP_RULE.search(rules)
    return feature_list["features"], int(match.group(1)) if match else None


def run(workspace: Path, script: dict, budget: int) -> dict:
    """The scripted session (SPEC.md, "The run"). Behavior derives from the
    workspace files and the script; nothing else is consulted."""
    features, wip_limit = load_workspace(workspace)
    status = {feature["id"]: feature["status"] for feature in features}
    verification = {feature["id"]: feature["verification"] for feature in features}
    assigned = next(feature["id"] for feature in features if feature["status"] == "in-progress")
    steps_on = {feature["id"]: 0 for feature in features}
    events: list[dict] = []
    parked: list[dict] = []
    parked_by_feature: dict[str, dict] = {}
    steps_spent = 0

    def in_flight() -> int:
        return sum(1 for state in status.values() if state == "in-progress")

    for impulse in script["impulses"]:
        if steps_spent >= budget:
            break
        target = impulse["feature"]
        newly_activated = False
        if status[target] != "in-progress":
            if wip_limit is not None and in_flight() >= wip_limit:
                entry = parked_by_feature.get(target)
                if entry is None:
                    entry = {
                        "feature": target,
                        "action": impulse["action"],
                        "noticed": impulse["noticed"],
                        "noticed_at_step": steps_spent,
                        "times_provoked": 1,
                    }
                    parked_by_feature[target] = entry
                    parked.append(entry)
                else:
                    entry["times_provoked"] += 1
                continue
            status[target] = "in-progress"
            newly_activated = True

        steps_spent += 1
        steps_on[target] += 1
        if impulse["kind"] == "verify":
            status[target] = "passing"
            action = f"run the verification command ({verification[target]})"
            outcome = f"pass: {target} moves to passing with evidence"
        elif target == assigned:
            action = impulse["action"]
            outcome = f"progress on the assigned feature (step {steps_on[target]})"
        else:
            action = impulse["action"]
            outcome = (
                f"scope crossed: {in_flight()} features in flight"
                if newly_activated
                else "the tangent deepens; the assigned feature waits"
            )
        events.append(
            {"step": steps_spent, "feature": target, "action": action, "outcome": outcome}
        )

    return {
        "workspace": workspace.name,
        "wip_limit": wip_limit,
        "assigned": assigned,
        "budget": budget,
        "events": events,
        "parked": parked,
        "steps_spent": steps_spent,
        "steps_on_assigned": steps_on[assigned],
        "steps_on_tangents": steps_spent - steps_on[assigned],
        "features_started": sum(1 for feature in features if steps_on[feature["id"]] > 0),
        "features_passing": sum(1 for feature in features if status[feature["id"]] == "passing"),
        "in_progress_at_end": [
            feature["id"] for feature in features if status[feature["id"]] == "in-progress"
        ],
        "assigned_verified": status[assigned] == "passing",
    }


USAGE = "usage: main.py <workspace-dir> <session-script.json> [--budget N]"


def parse_args(argv: list[str]) -> tuple[Path, Path, int] | None:
    positional: list[str] = []
    budget = DEFAULT_BUDGET
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--budget":
            if index + 1 >= len(argv) or not argv[index + 1].isdigit():
                return None
            budget = int(argv[index + 1])
            index += 2
            continue
        if arg.startswith("-"):
            return None
        positional.append(arg)
        index += 1
    if len(positional) != 2 or budget < 1:
        return None
    return Path(positional[0]), Path(positional[1]), budget


def main(argv: list[str]) -> int:
    parsed = parse_args(argv)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    workspace, script_path, budget = parsed
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return 2
    for required in ("feature_list.json", "AGENTS.md"):
        if not (workspace / required).is_file():
            print(f"error: workspace lacks {required}: {workspace}", file=sys.stderr)
            return 2
    if not script_path.is_file():
        print(f"error: not a file: {script_path}", file=sys.stderr)
        return 2
    script = json.loads(script_path.read_text(encoding="utf-8"))
    features, _ = load_workspace(workspace)
    active = [feature["id"] for feature in features if feature["status"] == "in-progress"]
    if len(active) != 1:
        print(
            f"error: expected exactly one in-progress feature, found {len(active)}",
            file=sys.stderr,
        )
        return 2
    report = run(workspace, script, budget)
    print(json.dumps(report, indent=2))
    return 0 if report["assigned_verified"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
