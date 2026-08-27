# SPEC: assembled-run

One scripted session over one application, run twice under two definitions
of done. The demo is the difference between the two runs: the session, the
workspace, and the components are identical, and only the kinds of check
the definition admits change.

## CLI surface

```text
main session <workspace-dir> <definition-file>   # work the task under one definition of done
main coverage <workspace-dir>                    # supporting counts, not the demo
```

A workspace is a directory carrying `app.json` (below). A definition file
lives outside the workspace, because the definition of done belongs to the
harness rather than to the code being judged.

## The application contract (`app.json`)

```json
{
  "task": "...",
  "levels": ["unit", "e2e"],
  "components": [ { "id", "layer", "ops": [...], "unit_case": { "input", "expects" } } ],
  "pipelines": [ { "id", "stages": ["..."], "start": {}, "expects": { "field", "value" } } ]
}
```

A **record** is a flat map of string fields, rendered on one line as
`key=value` pairs in sorted key order (`(empty)` when it has no fields). A
**component** transforms a record by applying its `ops` in order; it is the
deterministic stand-in for a real module, and the ops are the seam where a
live harness would run the module itself. A **pipeline** is the assembled
system: stage 1 receives `start`, and every later stage receives the record
the previous stage produced.

| op | fields | effect | rejection message |
| --- | --- | --- | --- |
| `set` | `field`, `value` | writes the literal into the field | never rejects |
| `format` | `field`, `template` | writes the template with `{name}` placeholders filled from the record | `<name> is not in the record` |
| `copy` | `from`, `to` | writes the `from` field's value into the `to` field | `<from> is not in the record` |
| `require-prefix` | `field`, `prefix` | accepts only when the field starts with the prefix | `<field>=<value> does not start with <prefix>`, or `<field> is not in the record` |

A rejection stops that component; in a pipeline it stops the whole run.
Every op that writes a field also records itself as that field's last
writer, so a rejection can name the component on the other side of the
seam.

## The two kinds of check

- **`unit`**: one check per component, `unit:<component-id>`. The component
  runs alone on the input its own `unit_case` supplies, and the check
  passes when the resulting record equals the case's `expects`. No other
  component is involved.
  - pass detail: `<id> unit case output matches its declaration: <record>`
  - fail detail: `<id> unit case output <record> does not match its declaration <record>`,
    or `<id> rejected its own unit case input: <message>`
- **`e2e`**: one check per pipeline named in the definition's `e2e_runs`,
  `e2e:<pipeline-id>`. The pipeline runs assembled over its `start` record,
  and the check passes when the final record's `expects.field` holds
  `expects.value`. The check carries a `trace`: one entry per stage,
  `{"component", "outcome"}`, where the outcome is the rendered record after
  that stage, or `rejected: <message>`.
  - pass detail: `the assembled run completed: <field>=<value>`
  - fail details: `the assembled run stopped at <stage>: <message>; <field> was last written by <id>`
    (or `; no component in this flow wrote <field>` when nothing wrote it),
    and `the assembled run completed but <field>=<value>; the flow expects <field>=<value>`

## The definition of done (`<definition-file>`)

```json
{ "id": "...", "summary": "...", "levels": ["unit", "e2e"], "e2e_runs": ["..."] }
```

`levels` lists the kinds of check that count toward done, in the order they
run. `e2e_runs` names the pipelines the `e2e` level executes. A level whose
check list is empty passes with nothing executed: listing `e2e` while
naming no pipeline is a green level that ran no assembled code. Three
definitions ship: `unit-only`, `through-e2e`, and `e2e-listed-empty`, the
last of which admits the level and names no flow.

## The session

The session records one implementation event per component
(`{"step", "action", "outcome"}`, the outcome naming the ops that component
declares), then runs the admitted levels in order and stops at the first
failing level. Output:

```json
{
  "workspace": "...",
  "task": "...",
  "definition_of_done": { "id", "levels", "e2e_runs" },
  "events": [ { "step", "action", "outcome" } ],
  "levels": [ { "level", "checks": [ { "id", "subject", "result", "detail" } ], "result" } ],
  "verdict": { "declared", "failing_level", "levels_not_admitted" }
}
```

A level's `result` is `pass` when every one of its checks passed.
`declared` is `done` when no level failed and `blocked` otherwise;
`failing_level` names the first failing level or is `null`;
`levels_not_admitted` lists the kinds `app.json` declares that this
definition left out.

## The coverage surface

`coverage` prints, for the same workspace: the component ids, the unit
check ids, the pipeline **seams** (each adjacent stage pair, rendered
`<left> -> <right>`), the seams the unit checks exercise, the seams the
assembled run exercises, and a `totals` object of the four counts. A unit
check runs one component, so its stage sequence has no adjacent pair and
its seam list is empty by construction. This surface is supporting
evidence about the demo, never the demo: the behavior is in `session`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `session`: the session declared done under this definition. `coverage`: counts printed |
| 1 | `session`: a level failed, so the session is blocked |
| 2 | usage error, `<workspace-dir>` not a directory or lacking `app.json`, or `<definition-file>` missing; stdout empty |

## Fixtures and the seeded defect

Both workspaces describe the same three-component export feature:
`selection-ui` (ui layer) picks the report, `path-builder` (service layer)
builds the export path from the report name, `file-writer` (io layer)
refuses any path that is not absolute and then writes it. Both declare the
same pipeline `assembled-export-flow` wiring the three in that order.

`workspaces/workspace-seam-gap` carries the seeded defect, and it is a
contract mismatch rather than a missing artifact:

| Seeded defect | Symptom | Caught by |
| --- | --- | --- |
| `path-builder` emits `exports/{report}.csv`, a relative path, while `file-writer` accepts only paths starting with `/` | `the assembled run stopped at file-writer: path=exports/quarterly.csv does not start with /; path was last written by path-builder`, exit 1 | the `e2e` level only |

Neither component is wrong on its own terms. `path-builder`'s unit case
declares the relative path it produces and the check passes;
`file-writer`'s unit case supplies an absolute path and the check passes.
The disagreement lives between them, so no `unit` check can reach it: under
`definitions/unit-only.json` all three components pass and the session
declares done with exit 0.

`workspaces/workspace-seam-closed` closes the mismatch by giving
`path-builder` the template `/srv/reports/exports/{report}.csv` and the
matching unit case. Its `e2e` check then completes with
`written=/srv/reports/exports/quarterly.csv` and the session declares done.

The `unit-only-declares-done` case (exit 0) and the
`through-e2e-blocks-the-same-work` case (exit 1) pin the pair over the same
workspace; `through-e2e-clears-the-closed-seam` (exit 0) pins the
end-to-end level over finished work;
`e2e-listed-but-empty-declares-done` (exit 0) pins the vacuous level, which
ships the same defect as `unit-only` while naming the right kind of check.
