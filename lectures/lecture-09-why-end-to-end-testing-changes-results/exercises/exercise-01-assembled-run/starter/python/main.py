"""assembled-run exercise, Python starter.

The report runs end to end and has the full shape: the unit layer is
complete and correct, the end-to-end layer walks the pipeline's stages in
order, and the verdict is derived from both. One naive decision remains
(see SPEC.md "Starter state"): the end-to-end runner starts each stage
from that component's own unit case input instead of threading the record
the previous stage produced. Fix `run_pipeline`, then run
../../verify.sh --stack=python until it exits 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")


def render(record: dict[str, str]) -> str:
    if not record:
        return "(empty)"
    return " ".join(f"{key}={record[key]}" for key in sorted(record))


def run_component(
    component: dict, record: dict[str, str], writers: dict[str, str]
) -> tuple[bool, dict[str, str], str, str]:
    """Run one component's ops over a record; see SPEC.md for the op table."""
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
                return False, current, f"{missing[0]} is not in the record", missing[0]
            current[op["field"]] = PLACEHOLDER.sub(
                lambda match: current[match.group(1)], op["template"]
            )
            writers[op["field"]] = component["id"]
        elif kind == "copy":
            source = op["from"]
            if source not in current:
                return False, current, f"{source} is not in the record", source
            current[op["to"]] = current[source]
            writers[op["to"]] = component["id"]
        elif kind == "require-prefix":
            field = op["field"]
            if field not in current:
                return False, current, f"{field} is not in the record", field
            if not current[field].startswith(op["prefix"]):
                return (
                    False,
                    current,
                    f"{field}={current[field]} does not start with {op['prefix']}",
                    field,
                )
        else:
            raise ValueError(f"unknown op: {kind}")
    return True, current, "", ""


def unit_check(component: dict) -> tuple[bool, str]:
    identifier = component["id"]
    accepted, record, message, _ = run_component(component, component["unit_case"]["input"], {})
    if not accepted:
        return False, f"{identifier} rejected its own unit case input: {message}"
    expects = component["unit_case"]["expects"]
    if record == expects:
        return True, f"{identifier} unit case output matches its declaration: {render(record)}"
    return False, (
        f"{identifier} unit case output {render(record)} does not match "
        f"its declaration {render(expects)}"
    )


def run_pipeline(app: dict, pipeline: dict) -> tuple[bool, str, list[dict]]:
    """The end-to-end run over the pipeline's stages, in declared order."""
    by_id = {component["id"]: component for component in app["components"]}
    record: dict[str, str] = dict(pipeline["start"])
    writers: dict[str, str] = {}
    trace: list[dict] = []
    for stage in pipeline["stages"]:
        component = by_id[stage]
        # Naive draft: every component ships a unit case with an input
        # already prepared for it, so hand each stage that input and move
        # on. Exercise: an assembled run threads ONE record through the
        # stages, so a stage must receive what the previous stage produced.
        accepted, record, message, field = run_component(
            component, component["unit_case"]["input"], writers
        )
        if not accepted:
            trace.append({"component": stage, "outcome": f"rejected: {message}"})
            origin = writers.get(field)
            source = (
                f"{field} was last written by {origin}"
                if origin
                else f"no component in this flow wrote {field}"
            )
            return False, f"the assembled run stopped at {stage}: {message}; {source}", trace
        trace.append({"component": stage, "outcome": render(record)})
    field = pipeline["expects"]["field"]
    want = pipeline["expects"]["value"]
    got = record.get(field, "(absent)")
    if got == want:
        return True, f"the assembled run completed: {field}={got}", trace
    return False, (
        f"the assembled run completed but {field}={got}; the flow expects {field}={want}"
    ), trace


def report(app: dict, name: str) -> dict:
    unit_rows = []
    for component in app["components"]:
        passed, detail = unit_check(component)
        unit_rows.append(
            {
                "id": f"unit:{component['id']}",
                "subject": component["id"],
                "result": "pass" if passed else "fail",
                "detail": detail,
            }
        )
    e2e_rows = []
    for pipeline in app["pipelines"]:
        passed, detail, trace = run_pipeline(app, pipeline)
        e2e_rows.append(
            {
                "id": f"e2e:{pipeline['id']}",
                "subject": pipeline["id"],
                "result": "pass" if passed else "fail",
                "detail": detail,
                "trace": trace,
            }
        )
    layers = [("unit", unit_rows), ("e2e", e2e_rows)]
    results = {
        layer: ("pass" if all(row["result"] == "pass" for row in rows) else "fail")
        for layer, rows in layers
    }
    failing = next((layer for layer, _ in layers if results[layer] == "fail"), None)
    return {
        "workspace": name,
        "unit": {"checks": unit_rows, "result": results["unit"]},
        "e2e": {"checks": e2e_rows, "result": results["e2e"]},
        "verdict": {
            "failing_layer": failing,
            "result": "done" if failing is None else "blocked",
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
    return 0 if result["verdict"]["result"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
