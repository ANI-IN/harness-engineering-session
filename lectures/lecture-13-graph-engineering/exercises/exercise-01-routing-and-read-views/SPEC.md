# SPEC: exercise-01 routing-and-read-views

The lecture's `structure` surface counts a graph's parts and scores
`graph-misrouted` complete, then that graph commits broken work
([../../code/SPEC.md](../../code/SPEC.md)). This exercise is the check that
does catch it: a validator that reads a graph file and reports which node
each router actually acts on and whether every node's declared read view
matches what its ops read. Nothing runs the graph; every answer comes from
the declared structure.

## CLI surface

```text
main <graph-file>
```

The graph file is read once and nothing is written, so the committed
fixtures are unchanged by any number of runs.

## The graph file

The lecture's schema with two fields added: `writes`, the shared-state keys
a node declares it writes, and `ops`, the units of work inside the node and
the keys each one touches.

```json
{
  "id": "graph-two-writers",
  "entry": "plan",
  "nodes": [
    {
      "name": "verify",
      "kind": "code | agent | rollback",
      "reads": ["goal", "files"],
      "writes": ["review", "failures"],
      "ops": [
        { "op": "regrade-every-goal", "reads": ["goal", "files"], "writes": ["review"] }
      ],
      "router": { "key": "status", "values": ["planned", "applied"] },
      "edges": [{ "when": "applied", "to": "commit" }, { "when": "planned", "to": "undo" }]
    }
  ]
}
```

- `reads` is the node's declared read view: the keys the executor grants it.
- `writes` is what the node declares it writes into shared state.
- `ops` is what the node does, and each op names the keys it reads and
  writes. `reads` and `writes` are the declaration; `ops` is the work.
- `router`, `edges`, and `kind` mean what they mean in the demo's contract.

## Walk order

A graph with branches has no single execution order, so this validator uses
the order the walk can first reach each node: start at `entry`, follow each
node's edges in the order the file declares them, and record a node the
first time it is visited (breadth first). Nodes no edge reaches keep their
file order at the end, so every node has a position. **The walk order and
the file order are different lists**, and `graph-order-accidents` is the
fixture where they differ.

## Writer attribution

Every node on the way to a router may write the routed key, and each write
overwrites the one before it. The value a router reads therefore belongs to
the **last node that writes that key at or before the router in walk
order**, which is `last_writer`. First-in-the-file is a different node
whenever a key has more than one writer.

| `last_writer` | `grade` | Meaning |
| --- | --- | --- |
| the routing node itself | `independent` | the router acts on a value the node it sits on produced |
| any other node | `self-reported` | the router acts on a value another node reported about its own work |
| `none` | `unwritten` | nothing writes the key on the way here, so the router reads whatever the run started with |

## Findings

| `kind` | Raised when |
| --- | --- |
| `self-reported-routing` | a router's `grade` is `self-reported` |
| `unwritten-routing-key` | a router's `grade` is `unwritten` |
| `undeclared-read` | an op of a node reads a key the node's `reads` does not grant |
| `unused-read-view` | a node's `reads` grants a key no op of that node reads |

Findings are emitted node by node in walk order, and within a node in this
order: the routing finding (at most one), then `undeclared-read` by key,
then `unused-read-view` by key. `detail` is the sentence that names the
reason, and it names the node the routing key was attributed to.

## Output

```json
{
  "graph": "graph-two-writers",
  "order": ["plan", "apply", "verify", "commit", "undo"],
  "decisions": [
    { "at": "verify", "key": "status", "last_writer": "apply", "grade": "self-reported" }
  ],
  "views": [
    {
      "node": "verify",
      "declared": ["files", "goal"],
      "used": ["files", "goal"],
      "read_without_grant": [],
      "granted_unused": []
    }
  ],
  "findings": [{ "kind": "...", "node": "...", "key": "...", "detail": "..." }],
  "sound": false,
  "verdict": "sound" | "unsound"
}
```

`order` is the walk order. `decisions` carries one row per router, in walk
order. `views` carries one row per node, in walk order; `declared`, `used`,
`read_without_grant`, and `granted_unused` are sorted lists of key names.
`sound` is true when `findings` is empty.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `sound`: no routing or read-view finding |
| 1 | `unsound`: at least one finding |
| 2 | usage error, or a missing or malformed graph file; stdout empty |

## Fixtures and seeded symptoms

Four graphs over the same five nodes as the lecture demo.

| Graph | What it declares | Symptom |
| --- | --- | --- |
| `graph-declared` | the lecture's declared wiring, with `writes` and `ops` filled in | no finding; `verify` routes on `review`, which `verify` writes, so the decision is `independent` and the run exits 0 |
| `graph-two-writers` (the trap) | `plan` and `apply` both write `status`; `verify` routes on it | one `self-reported-routing` finding naming `apply`, the last writer on the way to `verify`, not `plan`, the first writer in the file |
| `graph-misrouted` | the lecture's misrouted wiring: `verify` routes on `applied_ok`, which `apply` writes | one `self-reported-routing` finding naming `apply`, the node whose work `verify` is there to judge |
| `graph-order-accidents` | `apply` routes on `review`, which only the downstream `verify` writes; `verify` has an op reading the ungranted `plan`; `commit` is granted `files` and reads only `review` | three findings, one per defect, and a walk order (`plan, apply, verify, undo, commit`) that is not the file order |

`graph-two-writers` is the trap because it is the one graph where the two
attribution rules disagree while everything else about the report stays the
same: both rules produce one finding of the same kind at the same node with
the same exit code, and only the writer they name differs. A validator that
looks right on the other three fixtures is caught here and nowhere else.

Both tracks reproduce the same finding for the same fixture; the seeded
symptom is the finding text, and the stage that catches it is the
conformance run against `expected/`.

## Starter state (the intended failure)

The starter is a complete validator except for `deciding_writer`, which
answers "who wrote this key" by scanning the graph file from the top and
taking the first node that declares writing it. That is the reading a graph
file invites, because a file lists its nodes in the order someone wrote
them down. It is a tie-break, and it breaks the tie the wrong way: when a
key has two writers, the router reads the value the LAST one wrote, not the
first one declared. Everything else is complete: the walk order, the grade
table, the four finding kinds, the finding order, the view rows, the
verdict, and the exit codes.

Verification fails first on the `two-writers-of-the-routed-key` case at
`$.decisions[0].last_writer: 'plan' != 'apply'`. Both `plan` and `apply`
write `status` in that graph, `apply` writes it later on the way to
`verify`, and the starter names `plan` because `plan` is written down
first. The case exits 1 under both drafts, so the runner reports the wrong
value rather than a wrong exit code, and the starter runs cleanly.

The same tie-break also misgrades `read-views-and-a-key-written-later`,
where `apply` routes on `review`: the correct rule finds no writer of
`review` on the way to `apply` and grades the decision `unwritten`, while
scanning the file from the top finds the downstream `verify` and grades it
`self-reported`.

## Expected output

- `two-writers-of-the-routed-key`: `graph-two-writers.json` to
  `expected/two-writers.json`, exit 1.
- `router-on-the-judged-nodes-own-field`: `graph-misrouted.json` to
  `expected/misrouted.json`, exit 1.
- `read-views-and-a-key-written-later`: `graph-order-accidents.json` to
  `expected/order-accidents.json`, exit 1.
- `declared-graph-is-sound`: `graph-declared.json` to
  `expected/declared.json`, exit 0.
- `missing-graph-file`: a path with no file at it, exit 2, stdout empty.
