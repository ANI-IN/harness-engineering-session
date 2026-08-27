# SPEC: exercise-02 write-the-trace

Exercise 01 read a trace someone else recorded. This one records it. The
program replays a scripted session over a workspace, emits the harness's
event log as it goes, and then hands that log to the consumer from
exercise 01: for every check the session leaves failing, attribute the
write that caused it and name the repair. The consumer half is complete;
the log is the part under construction.

## CLI surface

```text
main <workspace-dir>
```

`<workspace-dir>` carries `plan.json`, `checks.json`, and the settings
files they name, exactly as in the lecture demo
([../../code/SPEC.md](../../code/SPEC.md)). Observability is not optional
here: the harness always logs.

## The session and its writes

The session applies each plan step to an **in-memory overlay** of the
workspace: files are loaded on first touch and modified in memory, and
nothing reaches the filesystem until the session ends. That is the
ordinary shape of a buffered writer, and it is what makes the recorded
`from` a real decision rather than a formality.

## The trace the harness records

One event per emission, `seq` counting from 1, no timestamps:

```json
{"seq", "level": "INFO", "command": "build", "event", "detail"}
```

| Event | Emitted | `detail` |
| --- | --- | --- |
| `session/start` | once, before any step | `{"task"}` |
| `workspace/write` | once per plan step | `{"step", "path", "key", "from", "to"}` |
| `session/end` | once, after the last step | `{"steps", "declared"}` |

`from` is the value that write replaced, and `to` is the value it wrote.
A key with no line reads as the empty string.

## The consumer (given, unchanged)

Run every declared check against the finished overlay. For each failure,
find the last `workspace/write` matching the check's `path` and `key`, and
record:

```text
event <seq> recorded step <n> setting <key> in <path> from <old> to <new>
restore <key>=<old> in <path>
```

With no match, record the `unattributed` attribution and the repair
`none`.

## Output

```json
{
  "workspace": "...",
  "events": [ ... ],
  "repair_plan": [ { "check", "failure", "attribution", "repair" } ],
  "outcome": { "failing", "attributed", "unattributed", "result" }
}
```

`failure` is the failing check's detail string. `result` is `located` when
every failing check was attributed and `blind` otherwise.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `located`: every failing check has an attributing event |
| 1 | `blind`: at least one failing check has none |
| 2 | usage error, or `<workspace-dir>` not a directory or lacking `plan.json` or `checks.json`; stdout empty |

## Fixtures

- `workspaces/workspace-ingest` (the trap): the plan writes `chunk_size`
  twice, 512 at step 2 and the template's 0 at step 4. Only a `from`
  taken from the session's own state can say that step 4 destroyed 512.
- `workspaces/workspace-clean`: the same plan with step 4 writing
  `batch_size` instead. Every key is written at most once, so the value
  on disk and the value the session holds are the same value, and a
  logger that reads either one records the same trace. Nothing fails, so
  there is nothing to attribute.

## Starter state (the intended failure)

The starter records `from` by reading the settings file from disk:
`read_key(load_lines(workspace, path), key)`. The session's writes are
buffered in the overlay, so that read always returns the value the file
had when the session started. For a key written once the two agree, which
is why the mistake survives the clean workspace; for `chunk_size` it does
not, and event 5 comes out claiming the value went `from 0 to 0`, a write
that changed nothing.

Verification fails first on the `overwrite-recorded` case at
`$.events[4].detail.from: '0' != '512'`. The consumer then attributes to
that same event and proposes `restore chunk_size=0`, which is the value
the check already rejects, so the trace is present, well formed, and
useless. `single-writes-agree` and `missing-workspace` pass under the
starter. The starter runs cleanly and fails only by producing that wrong
value.

## Expected output

- `overwrite-recorded`: `workspace-ingest` to
  `expected/overwrite-recorded.json`, exit 0.
- `single-writes-agree`: `workspace-clean` to
  `expected/single-writes-agree.json`, exit 0.
