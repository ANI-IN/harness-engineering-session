# SPEC: exercise-02 seam-remediation

Exercise 01 makes the assembled run real. This one makes its failure
actionable. Every failing end-to-end run produces a remediation record
with three parts, and the third part names the component that has to
change. The objection always comes from the component that refused the
record, or from the flow's own expectation; the value that broke the
contract came from somewhere upstream, and that is where the change goes.

## CLI surface

```text
main <workspace-dir>
```

`<workspace-dir>` carries `app.json` with the demo's shape
([../../code/SPEC.md](../../code/SPEC.md)): `components` (each with `ops`
and a `unit_case`) and `pipelines` (each with `stages`, `start`, and
`expects`). The op vocabulary, the record rendering, and the assembled run
are the demo's, unchanged.

## The report

```json
{
  "workspace": "...",
  "runs": [ { "id", "result": "pass" | "fail", "detail" } ],
  "remediations": [ { "check", "fix", "what", "why" } ],
  "verdict": { "remediations": 0, "result": "clean" | "fixes-required" }
}
```

One `runs` row per declared pipeline, in declared order, with the demo's
detail strings. One `remediations` row per failing run, in the same order.
`result` is `clean` when there is nothing to remediate.

## Failure kinds and their remediation text

Three kinds, all derived from the run itself, none authored by hand:

| kind | raised when | `what` | `why` |
| --- | --- | --- | --- |
| `missing` | a stage reads a field the record does not carry | `<stage> rejected the record: <field> is not in the record` | `<stage> reads <field>, and the record it was handed has none` |
| `prefix` | a stage requires a field to start with a prefix and it does not | `<stage> rejected the record: <field>=<value> does not start with <prefix>` | `<stage> accepts <field> only when it starts with <prefix>` |
| `expectation` | the run reaches the end with the wrong final value | `<flow> finished with <field>=<value>` | `<flow> is declared to finish with <field>=<want>` |

`fix` names the **producer**: the component that last wrote the field
before the objection, or, when nothing in the flow wrote it, whatever ran
immediately before the objecting stage (`the flow's start record` when the
objecting stage is the first one). For an `expectation` failure the
producer is the component that last wrote the field, or the last stage.

| kind | `fix` |
| --- | --- |
| `missing` | `change <producer> to emit <field> before <stage> runs` |
| `prefix` | `change <producer> to emit <field> starting with <prefix>` |
| `expectation` | `change <producer> to emit <field>=<want>` |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `clean`: every declared run completed as declared |
| 1 | `fixes-required`: at least one run failed and carries a remediation |
| 2 | usage error, or `<workspace-dir>` is not a directory or lacks `app.json`; stdout empty |

## Fixtures

Four workspaces over the same three-component export feature, each with a
unit layer that passes completely:

- `workspaces/workspace-seam-gap`: `path-builder` emits a relative path and
  `file-writer` accepts only absolute ones (a `prefix` failure).
- `workspaces/workspace-name-gap`: `selection-ui` writes `report_name`
  while `path-builder` reads `{report}` (a `missing` failure, and nothing
  in the flow ever wrote `report`).
- `workspaces/workspace-artifact-gap` (the trap): every stage accepts the
  record, and `file-writer` writes `<path>.tmp` exactly as its own unit
  case declares. The run completes and the artifact is wrong (an
  `expectation` failure), so the objection comes from the flow rather than
  from a component, and the naive instruction is to change the flow.
- `workspaces/workspace-seam-closed`: the seam agrees, the run completes,
  and there is nothing to remediate.

## Starter state (the intended failure)

The starter addresses every instruction to the component that raised the
objection: `change <stage> to accept ...` for a rejection and
`change <flow> to expect ...` for a wrong artifact. Each instruction is
locally plausible and each one deletes a contract instead of honoring it:
teaching `file-writer` to accept relative paths removes the check that
caught the defect, and teaching the flow to expect the temporary file
renames the bug into the specification. The producer lookup the starter
needs is already computed and carried on the failure record.

Verification fails first on the `prefix-seam-remediated` case, at:

```text
diverges at $.remediations[0].fix: 'change file-writer to accept path=exports/quarterly.csv' != 'change path-builder to emit path starting with /'
```

`missing-field-remediated` and `wrong-artifact-remediated` fail the same
way in their own kinds; `clean-flow-has-nothing-to-fix` passes, because a
run with no failure has no instruction to get wrong. Every `what` and
`why` string is already correct in the starter, and the verdict, the
counts, and the exit codes match: the whole divergence is which component
the report tells the next session to change. The starter must run cleanly
and fail only by producing those wrong values.

## Expected output

- `prefix-seam-remediated`: `workspace-seam-gap` -> `expected/seam-gap.json`, exit 1.
- `missing-field-remediated`: `workspace-name-gap` -> `expected/name-gap.json`, exit 1.
- `wrong-artifact-remediated`: `workspace-artifact-gap` -> `expected/artifact-gap.json`, exit 1.
- `clean-flow-has-nothing-to-fix`: `workspace-seam-closed` -> `expected/seam-closed.json`, exit 0.
