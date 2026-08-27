"""failure-triage exercise, Python solution.

All five attribution rules implemented. Each rule inspects one event (plus
the events before it in the same run) and returns (subsystem, rule-id) or
None; the first event matching any rule attributes the run. Rule semantics
and precedence are pinned by ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys

SUBSYSTEMS = ("instructions", "tools", "environment", "state", "feedback")

TOOL_SIGNALS = ("command not found", "permission denied")
ENVIRONMENT_SIGNALS = ("ModuleNotFoundError", "Cannot find module", "version")


def attribute_event(event: dict, prior: list[dict]) -> tuple[str, str] | None:
    kind = event["type"]
    detail = event["detail"]
    if kind == "agent_question":
        return "instructions", "asked-for-repo-fact"
    if kind == "shell_error" and any(signal in detail for signal in TOOL_SIGNALS):
        return "tools", "command-unavailable"
    if kind == "shell_error" and any(signal in detail for signal in ENVIRONMENT_SIGNALS):
        return "environment", "dependency-or-runtime-missing"
    if kind == "rework":
        return "state", "repeated-prior-work"
    if kind == "claim" and not any(
        p["type"] == "verification" and p.get("result") == "pass" for p in prior
    ):
        return "feedback", "claim-without-passing-verification"
    return None


def triage(events: list[dict]) -> dict:
    order: list[str] = []
    runs: dict[str, dict] = {}
    for event in events:
        run_id = event["run"]
        if run_id not in runs:
            order.append(run_id)
            runs[run_id] = {"task": None, "events": []}
        if event["type"] == "task" and runs[run_id]["task"] is None:
            runs[run_id]["task"] = event["detail"]
        runs[run_id]["events"].append(event)

    report_runs = []
    summary = dict.fromkeys((*SUBSYSTEMS, "unattributed"), 0)
    for run_id in order:
        entry = runs[run_id]
        attributed: tuple[str, str, dict] | None = None
        for index, event in enumerate(entry["events"]):
            match = attribute_event(event, entry["events"][:index])
            if match:
                attributed = (*match, event)
                break
        if attributed:
            subsystem, rule, event = attributed
            evidence = f'{event["type"]}: "{event["detail"]}"'
        else:
            subsystem, rule, evidence = "unattributed", None, None
        summary[subsystem] += 1
        report_runs.append(
            {"id": run_id, "task": entry["task"], "subsystem": subsystem,
             "rule": rule, "evidence": evidence}
        )

    total = len(order)
    failures = total - summary["unattributed"]
    return {
        "runs": report_runs,
        "summary": summary,
        "total_runs": total,
        "harness_failure_rate": failures / total if total else 0.0,
    }


def parse_transcript(text: str) -> list[dict]:
    events = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"malformed transcript at line {number}: {error}") from error
        for field in ("run", "type", "detail"):
            if field not in event:
                raise ValueError(f"malformed transcript at line {number}: missing {field!r}")
        events.append(event)
    return events


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <transcript.jsonl>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        print(f"error: cannot read transcript: {error}", file=sys.stderr)
        return 2
    try:
        events = parse_transcript(text)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(triage(events), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
