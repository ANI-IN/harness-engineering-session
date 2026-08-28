"""failure-triage: attribute agent-run failures to harness subsystems.

Reads a JSONL transcript of agent-run events and applies the mechanical
attribution rules from SPEC.md. The point of the demo: failure diagnosis is
a rules job over observable events, not a judgment call about the model.
"""

from __future__ import annotations

import json
import re
import sys

SUBSYSTEMS = ("instructions", "tools", "environment", "state", "feedback")

# Signals match whole words. A bare substring test reads `version` inside
# `conversion` and `subversion`, so a TypeError and a stale VCS mirror both
# attributed to the environment. That is the mistake lectures 02 to 04 spend
# four exercises teaching against, and the fixture
# `fixtures/lookalike-signals.jsonl` pins the distinction.
TOOL_SIGNALS = (r"\bcommand not found\b", r"\bpermission denied\b")
ENVIRONMENT_SIGNALS = (
    r"\bModuleNotFoundError\b",
    r"\bCannot find module\b",
    r"\bversion\b",
)


def attribute_event(event: dict, prior: list[dict]) -> tuple[str, str] | None:
    """Return (subsystem, rule) for the first rule this event matches, else None.

    Rule order per SPEC.md: instructions, tools, environment, state, feedback.
    """
    kind = event["type"]
    detail = event["detail"]
    if kind == "agent_question":
        return "instructions", "asked-for-repo-fact"
    if kind == "shell_error":
        if any(re.search(signal, detail) for signal in TOOL_SIGNALS):
            return "tools", "command-unavailable"
        if any(re.search(signal, detail) for signal in ENVIRONMENT_SIGNALS):
            return "environment", "dependency-or-runtime-missing"
    if kind == "rework":
        return "state", "repeated-prior-work"
    if kind == "claim":
        has_passing = any(
            p["type"] == "verification" and p.get("result") == "pass" for p in prior
        )
        if not has_passing:
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
        found: tuple[str, str, dict] | None = None
        for index, event in enumerate(entry["events"]):
            match = attribute_event(event, entry["events"][:index])
            if match:
                found = (*match, event)
                break
        if found:
            subsystem, rule, event = found
            evidence = f'{event["type"]}: "{event["detail"]}"'
        else:
            subsystem, rule, evidence = "unattributed", None, None
        summary[subsystem] += 1
        report_runs.append(
            {
                "id": run_id,
                "task": entry["task"],
                "subsystem": subsystem,
                "rule": rule,
                "evidence": evidence,
            }
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
