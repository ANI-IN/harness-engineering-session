"""graph-run: a standard library graph executor, and the run it produces.

A graph is a committed JSON file: named nodes, the shared-state keys each
node is allowed to read, the edges out of each node, and, on one node, a
router naming the state key that decides which edge is taken. `run` walks
that graph over a workspace and reports every step, every routing
decision, the workspace the walk left behind, and a verdict.

The demonstration is behavioural. The same five nodes and the same two
workspaces are run under three wirings: one that declares a rollback edge,
one that omits it, and one whose router is keyed on the wrong state field.
The wiring alone decides whether the workspace ends consistent (committed
or restored, exit 0) or wrecked (half applied or committed broken,
exit 1).

`structure` is the supporting metric: node and edge counts, and which
routing values have no edge. It is evidence about a graph's shape, never
the demonstration, and graph-misrouted is the reason why: it scores as
complete and still commits broken work.

The workspace is read once and edited in memory, so the committed fixtures
never change and every run is idempotent. SPEC.md pins the graph schema,
the node contracts, the router, and the exit codes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_STEPS = 12
NOTES_PATH = "scratch/apply-notes.txt"
NOTES_TEXT = "note=working notes written by the apply node\n"


# --------------------------------------------------------------------------
# Shared state helpers. Every node reads and writes this one structure; no
# node calls another, and no node sees a key its graph entry does not list.
# --------------------------------------------------------------------------


def as_text(value: object) -> str:
    """The router compares state values as text, so both tracks spell
    booleans and absent values the same way."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "none"
    return str(value)


def nonempty_lines(text: str) -> list[str]:
    """Non-empty lines, LF or CRLF alike (docs/conventions.md, semantic rules)."""
    return [line for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line]


def declaration(files: dict[str, str], goal: dict) -> tuple[str, str]:
    """Whether one goal is declared, and the sentence that says so."""
    path, key, value = goal["path"], goal["key"], goal["value"]
    if path not in files:
        return "missing", f"{path} missing"
    found = [line for line in nonempty_lines(files[path]) if line.startswith(f"{key}=")]
    if not found:
        return "absent", f"{path} has no {key}= line"
    if len(found) > 1:
        return "duplicated", f"{path} declares {key} {len(found)} times"
    if found[0] != f"{key}={value}":
        return "wrong-value", f"{path} declares {found[0]}, not {key}={value}"
    return "ok", f"{path} declares {key}={value} once"


# --------------------------------------------------------------------------
# The nodes. Each takes the view of shared state its graph entry declares,
# and returns the keys it writes plus the sentence the transcript records.
# --------------------------------------------------------------------------


def node_plan(view: dict) -> tuple[dict, str]:
    """Deterministic node: compare the goal against the workspace."""
    plan, unmet = [], []
    for goal in view["goal"]:
        status, detail = declaration(view["files"], goal)
        if status != "ok":
            plan.append(dict(goal))
            unmet.append(detail)
    total = len(view["goal"])
    if not plan:
        return {"plan": plan}, f"{total} goals read; every one is already declared"
    return {"plan": plan}, f"{total} goals read; {len(plan)} need an edit: " + "; ".join(unmet)


def node_apply(view: dict) -> tuple[dict, str]:
    """Agent node stand-in: append each planned declaration, and leave the
    working notes an agent writes beside its edits. Every write is
    journalled, in the order it happened, so a rollback edge has something
    to reverse."""
    files = dict(view["files"])
    applied: list[dict] = []
    for item in view["plan"]:
        line = f"{item['key']}={item['value']}"
        path = item["path"]
        if path in files:
            files[path] = files[path] + line + "\n"
            applied.append({"op": "append", "path": path, "line": line})
        else:
            files[path] = f"module={Path(path).stem}\n{line}\n"
            applied.append({"op": "create", "path": path})
    files[NOTES_PATH] = NOTES_TEXT
    applied.append({"op": "create", "path": NOTES_PATH})
    outcome = (
        f"{len(view['plan'])} edits applied and {NOTES_PATH} written; "
        f"{len(applied)} operations journalled"
    )
    return {"files": files, "applied": applied, "applied_ok": True}, outcome


def node_verify(view: dict) -> tuple[dict, str]:
    """Agent node with a fresh view: its graph entry lists `goal` and
    `files` and nothing else, so it cannot see the plan that was drawn or
    the journal of what was written. It re-reads the workspace."""
    failures = []
    for goal in view["goal"]:
        status, detail = declaration(view["files"], goal)
        if status != "ok":
            failures.append(detail)
    review = "fail" if failures else "pass"
    outcome = (
        f"review=fail; {'; '.join(failures)}"
        if failures
        else f"review=pass; all {len(view['goal'])} goals are declared exactly once"
    )
    return {"review": review, "failures": failures}, outcome


def node_commit(view: dict) -> tuple[dict, str]:
    """Deterministic node: mark the run committed. It reports the review it
    was handed, whatever that review says."""
    review = as_text(view["review"])
    return {"committed": True}, f"recorded the run as committed with review={review}"


def node_undo(view: dict) -> tuple[dict, str]:
    """The rollback node: replay the journal backwards. Reverse order is
    what makes each append the last line of its file again, which is the
    only position from which removing it is safe."""
    files = dict(view["files"])
    undone: list[str] = []
    for operation in reversed(view["applied"]):
        path = operation["path"]
        if operation["op"] == "create":
            files.pop(path, None)
            undone.append(f"removed {path}")
            continue
        line = operation["line"]
        body = nonempty_lines(files.get(path, ""))
        if body and body[-1] == line:
            files[path] = "".join(f"{text}\n" for text in body[:-1])
            undone.append(f"removed {line} from {path}")
        else:
            undone.append(f"kept {line} in {path}; it is no longer the last line")
    outcome = f"{len(undone)} journalled operations replayed backwards: " + "; ".join(undone)
    return {"files": files, "undone": undone, "rolled_back": True}, outcome


NODE_IMPLEMENTATIONS = {
    "plan": node_plan,
    "apply": node_apply,
    "verify": node_verify,
    "commit": node_commit,
    "undo": node_undo,
}


# --------------------------------------------------------------------------
# The graph: validation, the router, and the walk.
# --------------------------------------------------------------------------


def validate(graph: dict) -> str | None:
    """The one message a malformed graph produces, identical in both tracks."""
    names = [node["name"] for node in graph["nodes"]]
    if len(set(names)) != len(names):
        return "graph declares the same node name twice"
    if graph["entry"] not in names:
        return f"graph entry {graph['entry']} is not a declared node"
    for node in graph["nodes"]:
        if node["name"] not in NODE_IMPLEMENTATIONS:
            return f"graph names node {node['name']}, which has no implementation"
        for edge in node["edges"]:
            if edge["to"] not in names:
                return f"edge {node['name']} -> {edge['to']} names an undeclared node"
    return None


def choose_edge(node: dict, state: dict, by_name: dict, routing: list[dict]) -> str | None:
    """The router: read one shared-state key, take the first edge declared
    for that value. An unconditional edge matches anything. When no edge
    matches, the walk has nowhere to go and stops where it stands."""
    edges = node["edges"]
    router = node.get("router")
    if router is None:
        return edges[0]["to"] if edges else None
    key = router["key"]
    value = as_text(state.get(key))
    chosen = next((edge for edge in edges if edge.get("when", value) == value), None)
    routing.append(
        {
            "at": node["name"],
            "key": key,
            "value": value,
            "edge": f"{node['name']} -> {chosen['to']}" if chosen else None,
            "rollback": chosen is not None and by_name[chosen["to"]]["kind"] == "rollback",
            "note": (
                f"the router read {key}={value} and took the edge declared for it"
                if chosen
                else f"no edge is declared for {key} == {value}, so the walk stops here"
            ),
        }
    )
    return chosen["to"] if chosen else None


def walk(graph: dict, state: dict) -> tuple[list[dict], list[dict]]:
    """Follow the graph from its entry node until a node has no edge out."""
    by_name = {node["name"]: node for node in graph["nodes"]}
    steps: list[dict] = []
    routing: list[dict] = []
    current: str | None = graph["entry"]
    while current is not None and len(steps) < MAX_STEPS:
        node = by_name[current]
        view = {key: state[key] for key in node["reads"]}
        writes, outcome = NODE_IMPLEMENTATIONS[current](view)
        state.update(writes)
        steps.append(
            {
                "step": len(steps) + 1,
                "node": current,
                "kind": node["kind"],
                "reads": list(node["reads"]),
                "writes": sorted(writes),
                "outcome": outcome,
            }
        )
        current = choose_edge(node, state, by_name, routing)
    return steps, routing


def verdict_of(state: dict) -> str:
    if state["committed"] and state["review"] == "pass":
        return "committed"
    if state["rolled_back"]:
        return "rolled-back"
    if state["committed"]:
        return "committed-broken"
    if state["applied"]:
        return "half-applied"
    return "stalled"


# --------------------------------------------------------------------------
# Surfaces.
# --------------------------------------------------------------------------


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "task.json":
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def run(graph: dict, root: Path) -> dict:
    task = json.loads((root / "task.json").read_text(encoding="utf-8"))
    opening = load_workspace(root)
    state = {
        "task": task["task"],
        "goal": task["goal"],
        "files": dict(opening),
        "plan": [],
        "applied": [],
        "applied_ok": False,
        "review": None,
        "failures": [],
        "undone": [],
        "rolled_back": False,
        "committed": False,
    }
    steps, routing = walk(graph, state)
    return {
        "graph": graph["id"],
        "workspace": root.name,
        "task": state["task"],
        "path": [step["node"] for step in steps],
        "steps": steps,
        "routing": routing,
        "final_state": {
            "review": state["review"],
            "applied_ok": state["applied_ok"],
            "committed": state["committed"],
            "rolled_back": state["rolled_back"],
            "failures": state["failures"],
            "undone": state["undone"],
        },
        "workspace_after": {
            path: nonempty_lines(text) for path, text in sorted(state["files"].items())
        },
        "matches_opening_state": state["files"] == opening,
        "verdict": verdict_of(state),
    }


def structure(graph: dict) -> dict:
    """Supporting evidence: what the graph's shape says about itself."""
    by_name = {node["name"]: node for node in graph["nodes"]}
    kinds: dict[str, int] = {}
    edges = 0
    conditional = 0
    rollback = 0
    routers = []
    for node in graph["nodes"]:
        kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
        for edge in node["edges"]:
            edges += 1
            conditional += 1 if "when" in edge else 0
            rollback += 1 if by_name[edge["to"]]["kind"] == "rollback" else 0
        router = node.get("router")
        if router is not None:
            declared = {edge["when"] for edge in node["edges"] if "when" in edge}
            routers.append(
                {
                    "at": node["name"],
                    "key": router["key"],
                    "values": list(router["values"]),
                    "uncovered": [value for value in router["values"] if value not in declared],
                }
            )

    seen: list[str] = []
    frontier = [graph["entry"]]
    while frontier:
        name = frontier.pop(0)
        if name in seen:
            continue
        seen.append(name)
        frontier.extend(edge["to"] for edge in by_name[name]["edges"])
    unreachable = sorted(name for name in by_name if name not in seen)

    return {
        "graph": graph["id"],
        "entry": graph["entry"],
        "nodes": len(graph["nodes"]),
        "node_kinds": kinds,
        "edges": edges,
        "conditional_edges": conditional,
        "rollback_edges": rollback,
        "routers": routers,
        "unreachable": unreachable,
        "complete": not unreachable and all(not r["uncovered"] for r in routers),
    }


USAGE = "usage: main.py run <graph-file> <workspace-dir> | structure <graph-file>"


def read_graph(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("run", "structure"):
        print(USAGE, file=sys.stderr)
        return 2
    if len(argv) != (4 if argv[1] == "run" else 3):
        print(USAGE, file=sys.stderr)
        return 2
    graph = read_graph(Path(argv[2]))
    if graph is None:
        print(f"error: no graph file at {argv[2]}", file=sys.stderr)
        return 2
    problem = validate(graph)
    if problem is not None:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    if argv[1] == "structure":
        report = structure(graph)
        print(json.dumps(report, indent=2))
        return 0 if report["complete"] else 1
    root = Path(argv[3])
    if not root.is_dir() or not (root / "task.json").is_file():
        print(f"error: not a workspace (needs task.json): {argv[3]}", file=sys.stderr)
        return 2
    report = run(graph, root)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] in ("committed", "rolled-back") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
