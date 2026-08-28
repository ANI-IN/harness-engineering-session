# SPEC: resume-trace

Two sessions over one workspace. `build` is the first session: it walks a
plan, writes settings, leaves a session note, and declares done. `resume`
is the second session: it runs the workspace's declared checks, attributes
each failure to the write that caused it, and restores what that write
overwrote. The demo is the pair of `resume` runs under the two
observability modes, which differ in exactly one thing: whether the
harness wrote a structured event log during the build.

## CLI surface

```text
main build <workspace-dir> --observability=structured|none
main resume <workspace-dir> --observability=structured|none
```

A workspace is a directory carrying `plan.json`, `checks.json`, and the
files they name. The flag is required and has no default: the condition
under study is never implicit.

## The workspace contract

`plan.json` is the first session's script:

```json
{ "task": "...", "steps": [ { "action": "...", "write": {"path", "key", "value"} } ] }
```

`checks.json` is the workspace's declared health, owned by the harness
rather than by either session:

```json
{ "checks": [ { "id", "path", "key", "rule": "non-empty" | "positive-integer" } ] }
```

Settings files are `key=value` lines. A key read takes the first line
starting `<key>=`; the value is the rest of that line, trimmed. A key with
no line reads as absent, and an absent key writes as the empty string in
an event's `from`. Implementations treat LF and CRLF alike as line
separators (see docs/conventions.md, semantic rules).

| Rule | Passes when | Detail strings (pass / fail) |
| --- | --- | --- |
| `non-empty` | the value is a non-empty string | `<path> <key>=<v> is set` / `<path> <key> is empty` |
| `positive-integer` | the value matches `^-?[0-9]+$` and is above zero | `<path> <key>=<v> is a positive integer` / `<path> <key>=<v> is not a positive integer` |

A missing file fails with `<path> missing`; a missing key fails with
`<path> has no <key>= line`.

## Session writes are an in-memory overlay

Both sessions apply their writes to an in-memory copy of the workspace,
loaded file by file on first touch. Nothing on disk is modified, so the
fixtures stay pristine and the two conditions are re-runnable in any
order. That overlay is the seam where a real harness writes to the
filesystem.

## The build session (the first session, pinned)

For each plan step in order, the session reads the key's current value,
writes the new one, and records a transcript line
`{"step", "action", "outcome"}` whose outcome reads
`<path> <key>=<new> (was <old-or-unset>)`. When every step is done it
writes `notes/session-note.md`, its own prose summary, and declares done.
Exit 0.

**The observability flag changes one thing.** Under
`--observability=structured` the harness appends one line per event to
`log/events.jsonl`, compact JSON, one object per line:

```json
{"seq", "level", "command", "event", "detail"}
```

`seq` is the count of events already written plus one. **There are no
timestamps**: sequence numbers order the log, which is what the course's
no-wall-clock rule leaves and what a resume actually needs. Events:

| Event | `detail` |
| --- | --- |
| `session/start` | `{"task"}` |
| `workspace/write` | `{"step", "path", "key", "from", "to"}` |
| `session/end` | `{"steps", "declared"}` |

Under `--observability=none` the harness writes no log. The plan, the
steps, the resulting settings files, and the session note are identical
under both modes.

`build` output:
`{"workspace", "observability", "task", "transcript", "handoff":
{"files", "session_note", "events"}, "declared"}`, where `events` is the
parsed log and is `[]` under `none`.

## The resume session (the second session, pinned)

`resume` replays the build to obtain the workspace overlay and the
handoff artifacts, and receives **only** those: the build's transcript is
stdout, which ends with the session, so the second session never sees it.
Then:

1. Run every declared check; collect the failures in declared order.
2. For each failing check, scan the event log backwards for the last
   `workspace/write` whose `detail.path` and `detail.key` both match the
   check's. Matching on the file alone is wrong: a later write to a
   different key in the same file is not what broke this check.
3. On a match, record the attribution and restore `detail.from`. With no
   match (no log, or a log that never covered this key), record
   `unattributed` and repair nothing.
4. Re-run every check against the repaired overlay.

Output: `{"workspace", "observability", "handoff": {"files",
"events_read"}, "diagnosis": [{"check", "path", "key", "observed",
"attribution", "repair"}], "recheck": [{"id", "status", "detail"}],
"outcome": {"failing_before", "repaired", "failing_after", "result"}}`.
`result` is `resumed` when nothing fails after the repair and `stuck`
otherwise. Attribution strings:

```text
event <seq> recorded step <n> setting <key> in <path> from <old> to <new>
unattributed: the handoff records no write to <key> in <path>
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `build`: the session ran to its declaration. `resume`: the workspace passes every check after the repair (`resumed`) |
| 1 | `resume`: at least one check still fails (`stuck`) |
| 2 | usage error, a missing `--observability` flag, or `<workspace-dir>` not a directory or lacking `plan.json` or `checks.json`; stdout empty |

## Fixtures and the seeded defect

`workspaces/workspace-ingest` seeds one defect in the plan: step 2 sets
`chunk_size=512`, and step 4 (`copy the batch defaults from the
template`) overwrites it with the template's `0`. The session never runs
the checks, so it declares done over a workspace that fails one of them.

| Seeded state | Observable symptom | Caught by |
| --- | --- | --- |
| `config/app.conf chunk_size=0` after step 4 | check `chunk-size-positive` fails: `config/app.conf chunk_size=0 is not a positive integer` | the resume session's first check pass, in both modes |
| the overwritten value `512` | recoverable only from `log/events.jsonl` event 5; it appears in no file the build left behind | the resume session's attribution step, which succeeds only under `--observability=structured` |

Step 5 writes `retries` to the same file after step 4, so the last write
to `config/app.conf` is not the write that broke the check. Attribution
has to match the key, not the file.

`workspaces/workspace-clean` is the control: the same plan with step 4
writing `batch_size` instead of overwriting `chunk_size`. Nothing fails,
so there is nothing to attribute, and `resume --observability=none` exits
0 over it. The silent mode is not wired to fail; it fails when the
question needs a record that no one kept.
