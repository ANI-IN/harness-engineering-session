"""stopping-condition: where should this loop have stopped?

A recorded loop trace holds, round by round, what the maker reported about
its own step and what the checker independently reported about the whole
goal. The loop that produced it had no stopping condition, so it ran to the
end of the trace. This referee replays the trace and decides, at each
round, whether a properly built loop stops there.

Two rules end a loop, and they are read in this order: the clock cannot
afford another round, or the work is finished. This draft asks the maker
whether the work is finished, since the maker is the party doing it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def reached_the_goal(record: dict) -> bool:
    """The signal the stopping condition reads for one round.

    The maker takes the step and reports on it, so its report is the
    earliest signal available that the work is finished.
    """
    return record["maker"]["reports_done"]


def referee(transcript: dict) -> dict:
    budget = transcript["budget_ticks"]
    cost = transcript["cost_per_round"]
    clock = 0
    rows: list[dict] = []
    stop: dict | None = None
    last_ran: dict | None = None

    for record in transcript["rounds"]:
        number = record["round"]
        if stop is not None:
            rows.append({"round": number, "clock": clock, "decision": "not-run"})
            continue
        if clock + cost > budget:
            stop = {
                "round": number,
                "clock": clock,
                "decision": "stop-budget",
                "reason": (
                    f"round {number} costs {cost} ticks and the {budget} tick "
                    f"budget has {budget - clock} left"
                ),
            }
            rows.append({"round": number, "clock": clock, "decision": "stop-budget"})
            continue
        clock += cost
        last_ran = record
        decision = "stop-done" if reached_the_goal(record) else "continue"
        rows.append({"round": number, "clock": clock, "decision": decision})
        if decision == "stop-done":
            stop = {
                "round": number,
                "clock": clock,
                "decision": "stop-done",
                "reason": f"the stopping condition read a pass at round {number}",
            }

    if stop is None:
        number = transcript["rounds"][-1]["round"] if transcript["rounds"] else 0
        stop = {
            "round": number,
            "clock": clock,
            "decision": "trace-ended",
            "reason": f"the trace ends at round {number} with the loop still running",
        }

    unmet = list(last_ran["checker"]["unmet"]) if last_ran is not None else []
    if stop["decision"] == "stop-budget":
        verdict = "budget-exhausted"
    elif not unmet:
        verdict = "goal-reached"
    else:
        verdict = "stopped-early"

    return {
        "loop": transcript["loop"],
        "budget_ticks": budget,
        "rounds": rows,
        "stop": stop,
        "unmet_at_stop": unmet,
        "verdict": verdict,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <transcript-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"error: no such transcript file: {path}", file=sys.stderr)
        return 2
    report = referee(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "goal-reached" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
