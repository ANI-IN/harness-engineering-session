"""graph-lint: the routing and read-view checks a part count cannot make.

The lecture's `structure` surface counts a graph's parts and calls
`graph-misrouted` complete, because by every count it is. This surface asks
the two questions a count cannot: whose report does each router act on, and
does every node's declared read view match what its ops actually read.

Two rules carry the whole file:

* A router is independent when the node it sits on is the node that wrote
  the routed key. Attributing the key to a writer is what `deciding_writer`
  below does.
* A read view is honest when the keys a node's ops read are exactly the
  keys the graph file grants it. A key read without a grant works only
  while the shared state happens to carry it; a key granted and never read
  widens the node's context for nothing.

The graph file is read once and nothing is written. SPEC.md pins the graph
schema, the walk order, the four finding kinds, the report, and the exit
codes.

Your task is `deciding_writer` and its one caller; everything else here is
complete. See README.md, "Your task".
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

NONE = "none"


def reach_order(graph: dict, by_name: dict[str, dict]) -> list[str]:
    """First-visit order of a walk from `entry`, following each node's edges
    in the order the file declares them. Nodes the walk cannot reach keep
    their file order at the end, so every node has a position."""
    order: list[str] = []
    seen: set[str] = set()
    queue = deque([graph["entry"]])
    while queue:
        name = queue.popleft()
        if name in seen or name not in by_name:
            continue
        seen.add(name)
        order.append(name)
        for edge in by_name[name].get("edges", []):
            if edge["to"] not in seen:
                queue.append(edge["to"])
    order.extend(node["name"] for node in graph["nodes"] if node["name"] not in seen)
    return order


def deciding_writer(nodes: list[dict], key: str) -> str:
    """The node whose write of `key` a router reads.

    A graph file lists its nodes in the order someone wrote them down, so
    scan the file from the top and take the first node that declares
    writing the key.
    """
    for node in nodes:
        if key in node["writes"]:
            return node["name"]
    return NONE


def grade_of(writer: str, at: str) -> str:
    if writer == NONE:
        return "unwritten"
    return "independent" if writer == at else "self-reported"


def decisions_of(graph: dict, order: list[str], by_name: dict[str, dict]) -> list[dict]:
    """One row per router, in walk order."""
    rows = []
    for name in order:
        router = by_name[name].get("router")
        if router is None:
            continue
        key = router["key"]
        writer = deciding_writer(graph["nodes"], key)
        rows.append(
            {"at": name, "key": key, "last_writer": writer, "grade": grade_of(writer, name)}
        )
    return rows


def views_of(order: list[str], by_name: dict[str, dict]) -> list[dict]:
    """One row per node, in walk order: what the graph grants against what
    the node's ops read."""
    rows = []
    for name in order:
        node = by_name[name]
        declared = set(node["reads"])
        used = {key for op in node["ops"] for key in op["reads"]}
        rows.append(
            {
                "node": name,
                "declared": sorted(declared),
                "used": sorted(used),
                "read_without_grant": sorted(used - declared),
                "granted_unused": sorted(declared - used),
            }
        )
    return rows


def first_op_reading(node: dict, key: str) -> str:
    for op in node["ops"]:
        if key in op["reads"]:
            return op["op"]
    return NONE


def findings_of(
    order: list[str], by_name: dict[str, dict], decisions: list[dict], views: list[dict]
) -> list[dict]:
    """Every defect, node by node in walk order: the routing finding first,
    then reads without a grant, then grants nothing reads."""
    decision_at = {row["at"]: row for row in decisions}
    view_of = {row["node"]: row for row in views}
    found: list[dict] = []
    for name in order:
        node = by_name[name]
        decision = decision_at.get(name)
        if decision is not None and decision["grade"] == "unwritten":
            found.append(
                {
                    "kind": "unwritten-routing-key",
                    "node": name,
                    "key": decision["key"],
                    "detail": (
                        f"the router at {name} reads {decision['key']}, which no node "
                        f"writes on the way to {name}, so the edge it takes is whatever "
                        "the state carried in"
                    ),
                }
            )
        elif decision is not None and decision["grade"] == "self-reported":
            writer = decision["last_writer"]
            found.append(
                {
                    "kind": "self-reported-routing",
                    "node": name,
                    "key": decision["key"],
                    "detail": (
                        f"the router at {name} reads {decision['key']}, and the last node "
                        f"to write {decision['key']} on the way to {name} is {writer}, so "
                        f"{writer} decides the edge out of the node that judges its work"
                    ),
                }
            )
        view = view_of[name]
        for key in view["read_without_grant"]:
            found.append(
                {
                    "kind": "undeclared-read",
                    "node": name,
                    "key": key,
                    "detail": (
                        f"op {first_op_reading(node, key)} of {name} reads {key}, which "
                        f"the graph does not grant {name}, so it works only while the "
                        "shared state happens to carry that key"
                    ),
                }
            )
        for key in view["granted_unused"]:
            found.append(
                {
                    "kind": "unused-read-view",
                    "node": name,
                    "key": key,
                    "detail": (
                        f"the graph grants {name} the key {key} and no op of {name} reads "
                        f"it, so {name} sees more shared state than it uses"
                    ),
                }
            )
    return found


def report(graph: dict) -> dict:
    by_name = {node["name"]: node for node in graph["nodes"]}
    order = reach_order(graph, by_name)
    decisions = decisions_of(graph, order, by_name)
    views = views_of(order, by_name)
    findings = findings_of(order, by_name, decisions, views)
    return {
        "graph": graph["id"],
        "order": order,
        "decisions": decisions,
        "views": views,
        "findings": findings,
        "sound": not findings,
        "verdict": "sound" if not findings else "unsound",
    }


USAGE = "usage: main.py <graph-file>"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    graph_path = Path(argv[1])
    if not graph_path.is_file():
        print(f"error: no graph file at {argv[1]}", file=sys.stderr)
        return 2
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"error: malformed graph file {argv[1]}: {error}", file=sys.stderr)
        return 2
    result = report(graph)
    print(json.dumps(result, indent=2))
    return 0 if result["sound"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
