# SPEC: exercise-01 assembled-run

The lecture demo ([../../code/SPEC.md](../../code/SPEC.md)) runs whichever
levels a definition of done admits. This exercise builds the level the
definition admits when it says `e2e`: the run that assembles the
components and pushes one record through them. Both levels run every time
here, so the report puts the unit verdict and the end-to-end verdict side
by side over the same application.

## CLI surface

```text
main <workspace-dir>
```

`<workspace-dir>` carries `app.json` with the demo's shape: `components`
(each with `ops` and a `unit_case`) and `pipelines` (each with `stages`,
`start`, and `expects`). The op vocabulary, the record rendering, the
detail strings, and the last-writer rule are the demo's, unchanged.

## The report

```json
{
  "workspace": "...",
  "unit": { "checks": [ { "id", "subject", "result", "detail" } ], "result": "pass" | "fail" },
  "e2e": { "checks": [ { "id", "subject", "result", "detail", "trace" } ], "result": "pass" | "fail" },
  "verdict": { "failing_level": "unit" | "e2e" | null, "result": "done" | "blocked" }
}
```

The `unit` level runs one check per component, in declared order, each
component alone on its own `unit_case.input`. The `e2e` level runs one
check per declared pipeline, in declared order. A level's `result` is
`pass` when all of its checks passed. `failing_level` names the first
failing level, `unit` before `e2e`, and is `null` when neither failed.

## The assembled run

The pipeline's first stage receives a copy of `start`. Every later stage
receives the record the previous stage produced. A stage that rejects its
input ends the run, and the `trace` records one entry per stage reached:
the rendered record after that stage, or `rejected: <message>`. The
failure detail names the stage that rejected, the reason, and the
component that last wrote the field the reason is about, so the report
points at both sides of the seam rather than only the side that complained.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `done`: both levels passed |
| 1 | `blocked`: a level failed |
| 2 | usage error, or `<workspace-dir>` is not a directory or lacks `app.json`; stdout empty |

## Fixtures

Three workspaces, all describing the same three-component export feature
and all with a unit level that passes completely:

- `workspaces/workspace-seam-gap` (the trap): `path-builder` emits the
  relative path `exports/quarterly.csv` and `file-writer` accepts only
  paths starting with `/`. Each component's unit case is written in its own
  terms and passes; the assembled run stops at `file-writer`. Its
  `file-writer` unit case uses a scratch path, `/tmp/unit-fixture.csv`,
  the way a unit test usually does.
- `workspaces/workspace-name-gap`: `selection-ui` writes the field
  `report_name` while `path-builder` reads `{report}`. Again both unit
  cases pass; the assembled run stops at `path-builder`, and no component
  in the flow ever wrote `report`.
- `workspaces/workspace-seam-closed`: the same feature with the path
  formats agreed. Both levels pass and the run completes with
  `written=/srv/reports/exports/quarterly.csv`.

The seam-closed workspace is also the control for the starter's mistake.
There, and only there, each component's unit case input happens to equal
the record the previous stage produces, so a runner that ignores the
threading and one that respects it agree exactly, trace included. That
coincidence is what lets the mistake survive in a real repository until a
seam actually disagrees.

## Starter state (the intended failure)

The starter's `run_pipeline` walks the pipeline's stages in declared order
but hands each stage that component's own `unit_case.input` instead of the
record the previous stage produced. Every stage therefore starts from a
prepared input, no record ever crosses a seam, and the end-to-end level
reports whatever the last component did to its own fixture. It is an
ordered batch of unit runs wearing the end-to-end level's name.

Verification fails first on the `seam-gap-blocked` case, at:

```text
diverges at $.e2e.checks[0].detail: 'the assembled run completed but written=/tmp/unit-fixture.csv; the flow expects written=/srv/reports/exports/quarterly.csv' != 'the assembled run stopped at file-writer: path=exports/quarterly.csv does not start with /; path was last written by path-builder'
```

Both runners call the flow broken, so the verdict and the exit code agree
and the divergence is entirely in what the report says happened. The
starter reports a run that reached the end and wrote the unit fixture's
scratch file; the assembled run never reaches `file-writer`'s write at
all, because the path it is handed is rejected. `name-gap-blocked` fails
the same way for the same reason; `seam-closed-done` passes, because there
the two runners coincide. The starter must run cleanly and fail only by
producing those wrong values.

## Expected output

- `seam-gap-blocked`: `workspace-seam-gap` -> `expected/seam-gap.json`, exit 1.
- `name-gap-blocked`: `workspace-name-gap` -> `expected/name-gap.json`, exit 1.
- `seam-closed-done`: `workspace-seam-closed` -> `expected/seam-closed.json`, exit 0.
