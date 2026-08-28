"""seam-remediation exercise, Python solution.

A failing end-to-end run is only half a signal. The other half is the
instruction that follows from it, and the instruction has to name the
component that has to change. The objection is raised by whichever
component refused the record, or by the flow's own expectation, but the
value that broke the contract came from somewhere else, so the fix belongs
with the producer.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")
START_RECORD = "the flow's start record"


def render(record: dict[str, str]) -> str:
    if not record:
        return "(empty)"
    return " ".join(f"{key}={record[key]}" for key in sorted(record))


def run_component(
    component: dict, record: dict[str, str], writers: dict[str, str]
) -> tuple[bool, dict[str, str], dict | None]:
    """Run one component's ops over a record; see SPEC.md for the op table.

    A rejection returns a failure dict carrying the kind, the field, and
    the message, which is what the remediation is built from.
    """
    current = dict(record)
    for op in component["ops"]:
        kind = op["op"]
        if kind == "set":
            current[op["field"]] = op["value"]
            writers[op["field"]] = component["id"]
        elif kind == "format":
            names = [match.group(1) for match in PLACEHOLDER.finditer(op["template"])]
            missing = [name for name in names if name not in current]
            if missing:
                return False, current, missing_failure(missing[0])
            current[op["field"]] = PLACEHOLDER.sub(
                lambda match: current[match.group(1)], op["template"]
            )
            writers[op["field"]] = component["id"]
        elif kind == "copy":
            source = op["from"]
            if source not in current:
                return False, current, missing_failure(source)
            current[op["to"]] = current[source]
            writers[op["to"]] = component["id"]
        elif kind == "require-prefix":
            field = op["field"]
            if field not in current:
                return False, current, missing_failure(field)
            if not current[field].startswith(op["prefix"]):
                return False, current, {
                    "kind": "prefix",
                    "field": field,
                    "value": current[field],
                    "prefix": op["prefix"],
                    "message": (
                        f"{field}={current[field]} does not start with {op['prefix']}"
                    ),
                }
        else:
            raise ValueError(f"unknown op: {kind}")
    return True, current, None


def missing_failure(field: str) -> dict:
    return {"kind": "missing", "field": field, "message": f"{field} is not in the record"}


def producer(writers: dict[str, str], field: str, stages: list[str], stage: str) -> str:
    """Who has to change: the component that last wrote the field, or, when
    nothing wrote it, whatever ran immediately before the objecting stage."""
    if field in writers:
        return writers[field]
    index = stages.index(stage)
    return stages[index - 1] if index > 0 else START_RECORD


def run_pipeline(app: dict, pipeline: dict) -> tuple[bool, str, dict | None]:
    """The assembled run. Returns (passed, detail, failure)."""
    by_id = {component["id"]: component for component in app["components"]}
    stages = pipeline["stages"]
    record = dict(pipeline["start"])
    writers: dict[str, str] = {}
    for stage in stages:
        accepted, record, failure = run_component(by_id[stage], record, writers)
        if failure is not None and not accepted:
            field = failure["field"]
            written_by = writers.get(field)
            source = (
                f"{field} was last written by {written_by}"
                if written_by
                else f"no component in this flow wrote {field}"
            )
            detail = f"the assembled run stopped at {stage}: {failure['message']}; {source}"
            origin = producer(writers, field, stages, stage)
            return False, detail, {**failure, "stage": stage, "producer": origin}
    field = pipeline["expects"]["field"]
    want = pipeline["expects"]["value"]
    got = record.get(field, "(absent)")
    if got == want:
        return True, f"the assembled run completed: {field}={got}", None
    origin = writers.get(field, stages[-1])
    detail = (
        f"the assembled run completed but {field}={got}; "
        f"the flow expects {field}={want}"
    )
    return False, detail, {
        "kind": "expectation",
        "field": field,
        "value": got,
        "want": want,
        "stage": pipeline["id"],
        "producer": origin,
    }


def what_line(failure: dict) -> str:
    if failure["kind"] == "expectation":
        return f"{failure['stage']} finished with {failure['field']}={failure['value']}"
    return f"{failure['stage']} rejected the record: {failure['message']}"


def why_line(failure: dict) -> str:
    if failure["kind"] == "missing":
        return (
            f"{failure['stage']} reads {failure['field']}, "
            f"and the record it was handed has none"
        )
    if failure["kind"] == "prefix":
        return (
            f"{failure['stage']} accepts {failure['field']} only when it "
            f"starts with {failure['prefix']}"
        )
    return f"{failure['stage']} is declared to finish with {failure['field']}={failure['want']}"


def fix_line(failure: dict) -> str:
    """The producing side of the seam is the side that changes."""
    if failure["kind"] == "missing":
        return (
            f"change {failure['producer']} to emit {failure['field']} "
            f"before {failure['stage']} runs"
        )
    if failure["kind"] == "prefix":
        return (
            f"change {failure['producer']} to emit {failure['field']} "
            f"starting with {failure['prefix']}"
        )
    return (
        f"change {failure['producer']} to emit {failure['field']}={failure['want']}"
    )


def report(app: dict, name: str) -> dict:
    runs = []
    remediations = []
    for pipeline in app["pipelines"]:
        passed, detail, failure = run_pipeline(app, pipeline)
        check = f"e2e:{pipeline['id']}"
        runs.append({"id": check, "result": "pass" if passed else "fail", "detail": detail})
        if failure is not None:
            remediations.append(
                {
                    "check": check,
                    "fix": fix_line(failure),
                    "what": what_line(failure),
                    "why": why_line(failure),
                }
            )
    return {
        "workspace": name,
        "runs": runs,
        "remediations": remediations,
        "verdict": {
            "remediations": len(remediations),
            "result": "clean" if not remediations else "fixes-required",
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <workspace-dir>", file=sys.stderr)
        return 2
    workspace = Path(argv[1])
    if not workspace.is_dir() or not (workspace / "app.json").is_file():
        print(f"error: not a workspace (needs app.json): {workspace}", file=sys.stderr)
        return 2
    app = json.loads((workspace / "app.json").read_text(encoding="utf-8"))
    result = report(app, workspace.name)
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"]["result"] == "clean" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
