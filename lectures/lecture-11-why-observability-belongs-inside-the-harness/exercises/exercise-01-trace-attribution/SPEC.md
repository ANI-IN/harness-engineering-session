# SPEC: exercise-01 trace-attribution

The lecture demo's resume session replays a build it controls, so it knows
the log it is reading. This exercise reads a **recorded** trace: a
`log/events.jsonl` file some earlier session's harness left behind, next to
the workspace that session left behind. The job is attribution: for every
check that fails now, name the recorded write that put the current value
there, and the value it overwrote.

## CLI surface

```text
main <workspace-dir> <trace-file>
```

`<workspace-dir>` carries `checks.json` and the settings files it names,
with the demo's rules and detail strings unchanged
([../../code/SPEC.md](../../code/SPEC.md)). `<trace-file>` is one JSON
object per line:

```json
{"seq", "level", "command", "event", "detail"}
```

Blank lines are skipped. `workspace/write` events carry
`detail: {"step", "path", "key", "from", "to"}`; `session/start` and
`session/end` carry other shapes and are not writes. Sequence numbers
order the trace; there are no timestamps. The workspace is read only:
this surface diagnoses, it does not repair.

## The audit

Run every declared check. For each failing check, in declared order:

1. Find the **last** `workspace/write` whose `detail.path` and
   `detail.key` both equal the check's `path` and `key`.
2. On a match, record
   `event <seq> recorded step <n> setting <key> in <path> from <old> to <new>`
   and the repair `restore <key>=<old> in <path>`.
3. With no match, record
   `unattributed: the trace records no write to <key> in <path>` and the
   repair `none`.

Output:

```json
{
  "workspace": "...",
  "handoff": { "trace": "<file name>", "events_read": 0 },
  "diagnosis": [ { "check", "path", "key", "observed", "attribution", "repair" } ],
  "outcome": { "failing", "attributed", "unattributed", "result" }
}
```

`observed` is the value the failing check read. `result` is `located` when
every failing check was attributed (vacuously so when nothing fails) and
`blind` otherwise.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `located`: every failing check has an attributing event |
| 1 | `blind`: at least one failing check has none |
| 2 | usage error, a workspace without `checks.json`, or a missing trace file; stdout empty |

## Fixtures

- `workspaces/workspace-clobbered`: the settings a build session left,
  with `chunk_size=0`. One check fails, `chunk-size-positive`.
- `workspaces/workspace-healthy`: the same settings with
  `chunk_size=512`; every check passes.
- `traces/trace-clobber.jsonl` (the trap): the full seven-event log of
  that build. Event 5 is the write that set `chunk_size` to 0, and
  **event 6 is a later write to `retries` in the same file**, so the last
  write to `config/app.conf` is not the write that broke the check.
- `traces/trace-scoped.jsonl`: the same session logged by a harness whose
  logging covered `src/` and `index/` only. It is a real log, four events
  long, and it says nothing about the key being diagnosed.

## Starter state (the intended failure)

The starter attributes by file: `attribute(events, path)` returns the last
`workspace/write` recorded against the failing check's file, whatever key
that write touched. Against `trace-clobber.jsonl` that is event 6, the
`retries` write, so the audit blames the wrong write and proposes
restoring a value that was never lost.

Verification fails first on the `clobber-attributed` case at
`$.diagnosis[0].attribution: 'event 6 recorded step 5 setting retries in config/app.conf from 1 to 3' != 'event 5 recorded step 4 setting chunk_size in config/app.conf from 512 to 0'`.
The other cases pass under the starter: `trace-scoped.jsonl` records no
write to `config/app.conf` at all, so file matching and key matching both
come up empty, and the healthy workspace has no failing check to
attribute. Attributing by file misleads only when a session wrote to the
same file more than once, which is what the trap trace arranges and what
every real session does. The starter runs cleanly and fails only by
producing that wrong value.

## Expected output

- `clobber-attributed`: `workspace-clobbered` + `trace-clobber.jsonl` to
  `expected/clobber-attributed.json`, exit 0.
- `scoped-blind`: `workspace-clobbered` + `trace-scoped.jsonl` to
  `expected/scoped-blind.json`, exit 1.
- `healthy-nothing-failing`: `workspace-healthy` + `trace-clobber.jsonl`
  to `expected/healthy-nothing-failing.json`, exit 0.
