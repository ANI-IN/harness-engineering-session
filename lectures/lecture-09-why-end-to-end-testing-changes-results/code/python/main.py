"""assembled-run: one scripted session, two definitions of done.

`session` replays a deterministic scripted session over an application
described by `app.json` (components with declared ops and a declared unit
case, plus the pipelines that wire them together). The session runs every
check layer its definition-of-done file admits, stops at the first failing
layer, and declares done or blocked. Nothing else varies: the workspace,
the components, and the session are fixed, so the only input that changes
between two runs is which KINDS of check the definition admits.

Under `unit-only` every component passes its own unit case and the session
declares done, exit 0. Under `through-e2e` the same session additionally
runs the assembled pipeline, the record built by one component reaches the
next component that will not accept it, and the session is blocked, exit
1. `coverage` prints the supporting counts: which seams the two kinds of
check exercise. SPEC.md pins the op vocabulary, the layer semantics, and
the seeded contract mismatch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")


def render(record: dict[str, str]) -> str:
    """The canonical one-line rendering of a record, fields in sorted order."""
    if not record:
        return "(empty)"
    return " ".join(f"{key}={record[key]}" for key in sorted(record))


def run_component(
    component: dict, record: dict[str, str], writers: dict[str, str]
) -> tuple[bool, dict[str, str], str, str]:
    """Run one component's ops over a record.

    Returns (accepted, record, message, field). `writers` accumulates, per
    field, the id of the component that last wrote it, which is what lets a
    rejection name both sides of the seam instead of only the rejecting
    side. A component that rejects its input returns the untouched record,
    the reason, and the field the reason is about.
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
    """One unit-layer check: the component against its own declared case.

    The component is run in isolation, on the input its own unit case
    supplies. No other component is involved, which is exactly why a
    passing unit check says nothing about the assembled path.
    """
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
    """One end-to-end check: the assembled pipeline over a real request.

    Each stage receives the record the previous stage produced, so a
    disagreement between what one component emits and what the next accepts
    surfaces here and only here.
    """
    by_id = {component["id"]: component for component in app["components"]}
    record = dict(pipeline["start"])
    writers: dict[str, str] = {}
    trace: list[dict] = []
    for stage in pipeline["stages"]:
        accepted, record, message, field = run_component(by_id[stage], record, writers)
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


def layer_checks(app: dict, definition: dict, layer: str) -> list[dict]:
    """The checks one layer admits. `unit` runs every component alone;
    `e2e` runs every pipeline the definition names, which is why a
    definition may list the layer and still run nothing."""
    if layer == "unit":
        rows = []
        for component in app["components"]:
            passed, detail = unit_check(component)
            rows.append(
                {
                    "id": f"unit:{component['id']}",
                    "subject": component["id"],
                    "result": "pass" if passed else "fail",
                    "detail": detail,
                }
            )
        return rows
    if layer == "e2e":
        by_id = {pipeline["id"]: pipeline for pipeline in app["pipelines"]}
        rows = []
        for run_id in definition["e2e_runs"]:
            passed, detail, trace = run_pipeline(app, by_id[run_id])
            rows.append(
                {
                    "id": f"e2e:{run_id}",
                    "subject": run_id,
                    "result": "pass" if passed else "fail",
                    "detail": detail,
                    "trace": trace,
                }
            )
        return rows
    raise ValueError(f"unknown layer: {layer}")


def session(app: dict, definition: dict, name: str) -> dict:
    """The scripted session (SPEC.md, "The session"). The implementation
    events are fixed; the definition of done decides which layers run."""
    events = [
        {
            "step": index,
            "action": f"write the {component["tier"]} component {component['id']}",
            "outcome": "ops declared in app.json: "
            + ", ".join(op["op"] for op in component["ops"]),
        }
        for index, component in enumerate(app["components"], start=1)
    ]

    layers = []
    failing_layer = None
    for layer in definition["layers"]:
        checks = layer_checks(app, definition, layer)
        result = "pass" if all(check["result"] == "pass" for check in checks) else "fail"
        layers.append({"layer": layer, "checks": checks, "result": result})
        if result == "fail":
            failing_layer = layer
            break

    admitted = definition["layers"]
    return {
        "workspace": name,
        "task": app["task"],
        "definition_of_done": {
            "id": definition["id"],
            "layers": admitted,
            "e2e_runs": definition["e2e_runs"],
        },
        "events": events,
        "layers": layers,
        "verdict": {
            "declared": "done" if failing_layer is None else "blocked",
            "failing_layer": failing_layer,
            "layers_not_admitted": [kind for kind in app["layers"] if kind not in admitted],
        },
    }


def seams(stages: list[str]) -> list[str]:
    """The component boundaries a stage sequence crosses. A single stage
    crosses none, which is the whole of the unit layer's blind spot."""
    return [f"{left} -> {right}" for left, right in zip(stages, stages[1:], strict=False)]


def crossed_seams(app: dict) -> list[str]:
    """The seams the assembled run actually crossed, taken from the run.

    Derived, never declared. A seam counts as crossed when the record a
    stage produced reached the next stage, which includes the stage that
    rejected it: that rejection is how the defect surfaces. A run that halts
    at its first stage crosses nothing, and this must say so, because a
    lecture whose whole point is that a named layer running zero checks
    still passes cannot itself report coverage it did not measure.
    """
    crossed: list[str] = []
    for pipeline in app["pipelines"]:
        _accepted, _message, trace = run_pipeline(app, pipeline)
        reached = [entry["component"] for entry in trace]
        for left, right in zip(reached, reached[1:], strict=False):
            seam = f"{left} -> {right}"
            if seam not in crossed:
                crossed.append(seam)
    return crossed


def coverage(app: dict, name: str) -> dict:
    """Supporting counts only: what each kind of check touches. This is
    evidence about the demo, not the demo."""
    pipeline_seams: list[str] = []
    for pipeline in app["pipelines"]:
        for seam in seams(pipeline["stages"]):
            if seam not in pipeline_seams:
                pipeline_seams.append(seam)
    exercised = crossed_seams(app)
    unit_seams = sorted(
        {seam for component in app["components"] for seam in seams([component["id"]])}
    )
    return {
        "workspace": name,
        "components": [component["id"] for component in app["components"]],
        "unit_checks": [f"unit:{component['id']}" for component in app["components"]],
        "seams": pipeline_seams,
        "seams_exercised_by_unit_checks": unit_seams,
        "seams_exercised_by_the_assembled_run": exercised,
        "totals": {
            "components": len(app["components"]),
            "unit_checks": len(app["components"]),
            "seams": len(pipeline_seams),
            "seams_exercised_by_unit_checks": len(unit_seams),
            "seams_exercised_by_the_assembled_run": len(exercised),
        },
    }


def load_app(workspace: Path) -> dict:
    return json.loads((workspace / "app.json").read_text(encoding="utf-8"))


def resolve_workspace(arg: str) -> Path | None:
    workspace = Path(arg)
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return None
    if not (workspace / "app.json").is_file():
        print(f"error: not a workspace (no app.json): {workspace}", file=sys.stderr)
        return None
    return workspace


USAGE = (
    "usage: main.py session <workspace-dir> <definition-file> | "
    "main.py coverage <workspace-dir>"
)


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("session", "coverage"):
        print(USAGE, file=sys.stderr)
        return 2
    command = argv[1]
    if (command == "session" and len(argv) != 4) or (command == "coverage" and len(argv) != 3):
        print(USAGE, file=sys.stderr)
        return 2
    workspace = resolve_workspace(argv[2])
    if workspace is None:
        return 2
    app = load_app(workspace)
    if command == "coverage":
        print(json.dumps(coverage(app, workspace.name), indent=2))
        return 0
    definition_path = Path(argv[3])
    if not definition_path.is_file():
        print(f"error: no such definition of done: {definition_path}", file=sys.stderr)
        return 2
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    report = session(app, definition, workspace.name)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"]["declared"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
