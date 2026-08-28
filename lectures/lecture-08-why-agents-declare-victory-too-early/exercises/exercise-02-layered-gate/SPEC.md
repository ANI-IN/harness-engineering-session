# SPEC: exercise-02 layered-gate

The lecture demo's gate audits a claim after the fact and reports every
divergence. This exercise builds the gate a session should run **instead
of** declaring done: the declared checks executed as a termination
procedure in three layers, cheapest and most fundamental first, stopping
at the first layer that fails.

## CLI surface

```text
main <workspace-dir>
```

`<workspace-dir>` carries `checks.json` and the probed files, with the
demo's check kinds, detail strings, and line-ending rule unchanged
([../../code/SPEC.md](../../code/SPEC.md)). Every check's `layer` is one
of `static`, `tests`, `system`; `cost` is not used by this gate.

## The layered run

Layers run in the fixed order `static`, `tests`, `system`. Within a
layer, every declared check executes in declared order, and the layer's
status is `passed` when all of them pass and `failed` otherwise. Once a
layer has failed, no later layer executes: each of its checks is reported
with status `not-reached` and detail `gated by failing layer <layer>`,
naming the layer that stopped the run, and the layer's status is
`not-reached`. A layer with no declared checks is `passed`.

Output:

```json
{
  "workspace": "...",
  "layers": [ { "layer", "status", "checks": [ { "id", "status", "detail" } ] } ],
  "verdict": { "stopped_at": "<layer>" | null, "result": "done" | "not-done" }
}
```

Check `status` is `pass`, `fail`, or `not-reached`; `detail` is the
engine's detail string for executed checks.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `done`: every layer passed |
| 1 | `not-done`: a layer failed; `stopped_at` names it |
| 2 | usage error or `<workspace-dir>` lacks `checks.json`; stdout empty |

## Fixtures

- `workspaces/workspace-settled`: all five checks pass; exit 0.
- `workspaces/workspace-cracked` (the trap): the static layer passes,
  the tests layer fails (`tests/unit-export.txt` reads `result=fail`),
  and every system check would pass if run: the config line is present,
  the migration agrees, the end-to-end log exists. Exit 1, stopped at
  `tests`.
- `workspaces/workspace-torn`: the static layer fails
  (`src/export.txt` contains `TODO`); the tests layer would pass and the
  system layer would fail on all three counts if run. Exit 1, stopped at
  `static`.

## Starter state (the intended failure)

The starter executes every layer regardless of what failed above it, and
expresses the gate only in its verdict: `stopped_at` names the first
failing layer, but the rows below it carry real executed results.

Verification fails first on the `cracked-stops-at-tests` case at
`$.layers[2].checks[0].detail: 'config/app.conf has a line starting with export_dir=' != 'gated by failing layer tests'`:
the starter ran the system layer over a failing test suite and reports a
green config check as if it were evidence. The exit codes and verdicts
agree with the expected output on every case; only the gated rows
differ, and only where a layer above them failed (`workspace-settled`
passes under the starter). The starter must run cleanly and fail only by
producing those unearned rows.

## Expected output

- `cracked-stops-at-tests`: `workspace-cracked` → `expected/cracked.json`,
  exit 1.
- `torn-stops-at-static`: `workspace-torn` → `expected/torn.json`, exit 1.
- `settled-passes-every-layer`: `workspace-settled` →
  `expected/settled.json`, exit 0.
