# SPEC: graph-run

A graph executor with no dependencies: nodes, edges, shared state, a router
that picks the next edge from that state, and one rollback edge. `run`
walks a committed graph over a committed workspace and reports what the
walk did and what it left behind. The demo is the difference between three
wirings of the same five nodes over the same workspace.

## CLI surface

```text
main run <graph-file> <workspace-dir>    # walk the graph; the behavioural run
main structure <graph-file>              # count the graph's parts; supporting evidence
```

The workspace is read from disk once and edited in memory. Nothing under
`<workspace-dir>` is written, so the committed fixtures are unchanged by
any number of runs and every command in the lecture README is idempotent.
The in-memory file map is the seam where a live harness would edit real
files ([deterministic fake agent](../../../docs/glossary.md#core-model)).

## The graph file

```json
{
  "id": "graph-declared",
  "entry": "plan",
  "nodes": [
    {
      "name": "verify",
      "kind": "code | agent | rollback",
      "reads": ["goal", "files"],
      "router": { "key": "review", "values": ["pass", "fail"] },
      "edges": [{ "when": "pass", "to": "commit" }, { "when": "fail", "to": "undo" }]
    }
  ]
}
```

- `reads` is the node's view of shared state: the executor hands the node a
  copy containing those keys and no others. A node cannot reach a key it
  did not declare, which is how the verify node's independence is enforced
  by the executor rather than promised in prose.
- `router` names the one shared-state key that decides this node's exit,
  and the values that key can take. A node without a `router` takes its
  first edge.
- An edge with `when` matches only that value; an edge without `when`
  matches anything.
- `kind` is descriptive except for `rollback`, which is load-bearing: an
  edge is a **rollback edge** when its target node's kind is `rollback`.
  The count is derived from the wiring, never asserted by a label on the
  edge.

## Shared state

One structure, written only through node return values. Every key is
present before the walk starts, so a router reading a key no node has
written yet reads its declared initial value rather than failing.

| Key | Initial | Written by |
| --- | --- | --- |
| `task`, `goal` | from `task.json` | nobody |
| `files` | the workspace, path to text | `apply`, `undo` |
| `plan` | `[]` | `plan` |
| `applied` | `[]` | `apply` |
| `applied_ok` | `false` | `apply` |
| `review` | `null` | `verify` |
| `failures` | `[]` | `verify` |
| `undone` | `[]` | `undo` |
| `rolled_back` | `false` | `undo` |
| `committed` | `false` | `commit` |

The router compares state values as text: `true`, `false`, `none`, or the
value itself, so both tracks spell every comparison the same way.

## The nodes

A goal is **declared** when its file holds exactly one line starting
`<key>=` and that line is exactly `<key>=<value>`. Detail strings:
`<path> missing`, `<path> has no <key>= line`,
`<path> declares <key> N times`, `<path> declares <key>=<found>, not
<key>=<value>`, `<path> declares <key>=<value> once`. Both tracks treat LF
and CRLF alike as line separators (docs/conventions.md, semantic rules).

| Node | Kind | Reads | Does | Writes |
| --- | --- | --- | --- | --- |
| `plan` | code | `task`, `goal`, `files` | lists the goals that are not declared | `plan` |
| `apply` | agent | `plan`, `files` | appends `<key>=<value>` to each planned file, writes `scratch/apply-notes.txt`, journals every write in order | `files`, `applied`, `applied_ok` |
| `verify` | agent | `goal`, `files` | re-reads the workspace and grades every goal | `review`, `failures` |
| `commit` | code | `review`, `files` | records the run as committed, whatever the review says | `committed` |
| `undo` | rollback | `applied`, `files` | replays the journal backwards | `files`, `undone`, `rolled_back` |

`apply` appends. It does not replace, because appending is what an editor
that believes a key is absent does, and the conflicted workspace is where
that assumption breaks.

`undo` walks `applied` in reverse. Reverse order is what makes each
appended line the last line of its file again; an append is removed only
from that position, and a created file is removed only by path. An
operation whose line is no longer last is reported as `kept <line> in
<path>; it is no longer the last line` and the workspace does not return
to its opening bytes.

## The walk

Start at `entry`. Run the node, merge its writes into shared state, then
ask the router for the next node. Stop when a node has no edge out, when
no edge matches the router's value, or after `MAX_STEPS` (12) nodes. Each
router decision is recorded whether or not an edge matched.

## Verdict and exit codes

The exit code reports whether the graph left the workspace in a state
someone can act on, not whether the task succeeded. A rollback is a
success of the graph.

| Final state | Verdict | Code |
| --- | --- | --- |
| `committed` and `review == pass` | `committed` | 0 |
| `rolled_back` | `rolled-back` | 0 |
| `committed` and `review != pass` | `committed-broken` | 1 |
| nothing committed or rolled back, `applied` non-empty | `half-applied` | 1 |
| nothing committed or rolled back, nothing applied | `stalled` | 1 |

| Code | Meaning |
| --- | --- |
| 0 | `run`: `committed` or `rolled-back`. `structure`: every routing value has an edge and every node is reachable |
| 1 | `run`: `committed-broken`, `half-applied`, or `stalled`. `structure`: an uncovered routing value or an unreachable node |
| 2 | usage error, a missing or malformed graph file, or a `<workspace-dir>` missing or lacking `task.json`; stdout empty |

Output of `run`: `{"graph", "workspace", "task", "path", "steps",
"routing", "final_state", "workspace_after", "matches_opening_state",
"verdict"}`, where a step is `{"step", "node", "kind", "reads", "writes",
"outcome"}`, a routing decision is `{"at", "key", "value", "edge",
"rollback", "note"}`, and `workspace_after` maps every surviving path to
its non-empty lines.

## Structure (supporting evidence)

`structure` counts what the graph declares: `{"graph", "entry", "nodes",
"node_kinds", "edges", "conditional_edges", "rollback_edges", "routers",
"unreachable", "complete"}`. A router's `uncovered` lists the declared
values with no edge. `complete` is true when no router has an uncovered
value and every node is reachable from `entry`.

This is a count, so it is evidence and not the demonstration.
`graph-misrouted` is the reason the distinction is kept: it scores
`complete: true` with one rollback edge, and its run commits broken work.

## Fixtures and seeded symptoms

Two workspaces, differing by one line, and three graphs over the same five
nodes.

| Workspace | `config/app.conf` | Consequence |
| --- | --- | --- |
| `workspace-clean` | `service=reports` | `apply` appends `export_dir=out/reports`, so the key is declared once and `verify` passes |
| `workspace-conflicted` | `service=reports`, `export_dir=out/old` | `apply` appends a second `export_dir` line, so the key is declared twice and `verify` fails |

| Graph | Wiring | Run over `workspace-conflicted` |
| --- | --- | --- |
| `graph-declared` | verify routes on `review`; `fail` goes to the rollback node | `undo` reverses all three journalled operations; `matches_opening_state` is true; exit 0 |
| `graph-no-rollback` | verify routes on `review`; only `pass` has an edge | the walk stops at `verify`; `config/app.conf` keeps both `export_dir` lines and the scratch file survives; exit 1 |
| `graph-misrouted` | verify routes on `applied_ok`, which `apply` sets when its own writes land | `applied_ok=true` takes the commit edge; `review=fail` is never consulted; exit 1 |

The seeded symptom is the duplicated key: `verify` reports
`config/app.conf declares export_dir 2 times` in all three conflicted
runs, and both tracks reproduce that same failure. What differs is only
what the graph does next.

## Expected output

- `declared-graph-commits`: `graph-declared` + `workspace-clean` to
  `expected/run-committed.json`, exit 0.
- `declared-graph-rolls-back`: `graph-declared` + `workspace-conflicted`
  to `expected/run-rolled-back.json`, exit 0.
- `no-rollback-edge-leaves-half-applied`: `graph-no-rollback` +
  `workspace-conflicted` to `expected/run-half-applied.json`, exit 1.
- `misrouted-graph-commits-broken`: `graph-misrouted` +
  `workspace-conflicted` to `expected/run-committed-broken.json`, exit 1.
- `structure-of-the-declared-graph` to
  `expected/structure-declared.json`, exit 0.
- `structure-finds-the-uncovered-routing-value` to
  `expected/structure-no-rollback.json`, exit 1.
