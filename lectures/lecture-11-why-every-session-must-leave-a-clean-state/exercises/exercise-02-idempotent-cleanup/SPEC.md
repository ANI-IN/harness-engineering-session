# SPEC: exercise-02 idempotent-cleanup

The lecture demo's clean exit ([../../code/SPEC.md](../../code/SPEC.md))
runs once, on a workspace nobody has cleaned. Real exits get interrupted
and re-entered: a run is cancelled after two of its four steps, a retry starts
the protocol again, a wrapper runs it a second time to be sure. This
exercise is that protocol built so running it again is safe.

## CLI surface

```text
main <workspace-dir> --passes=<1-5>
```

The workspace is read from disk once and edited in memory, so the
committed fixture never changes and repeated runs are reproducible.
`--passes` runs the whole protocol that many times over the same in-memory
workspace, which is how the report shows what a second run does.

`<workspace-dir>` carries:

- `session.json`:
  `{"session", "date", "verified": [feature id], "next_step": "<id>: <sentence>"}`,
  what the session did and what it wants recorded.
- `feature_list.json` in the module's schema.
- `claude-progress.md`, whose session entries are `## Session NNN` headings.
- optionally `scratch/`, the session's debris.
- optionally `session-handoff.md`.

## The four steps

Each step returns whether it changed anything, plus its outcome string.

| Step | Wanted state | Outcome when it changes something | Outcome when it does not |
| --- | --- | --- | --- |
| `record-progress` | `claude-progress.md` has a `## Session <id>` entry | `added a session <id> entry to claude-progress.md` | `claude-progress.md already records session <id>` |
| `set-statuses` | every verified feature is `passing` with evidence | `set <ids> to passing with evidence` | `<ids> already passing with evidence` |
| `clear-scratch` | no file under `scratch/` | `removed <paths>` | `no files under scratch/` |
| `write-handoff` | `session-handoff.md` names the recorded next step | `wrote session-handoff.md naming <id>` | `session-handoff.md already names <id>` |

The new progress entry is inserted before the first heading that starts
`## Session`:

```text
## Session <id> (<date>)

- Verified: <ids joined by ", ">.
- Next: <next_step>
```

Evidence written by `set-statuses` is
`{"command": <the feature's verification>, "observed": "exit 0", "date": <session date>}`.
The handoff is rewritten whole, with a `## Verified now` bullet per
verified feature (`- <id>: verified by <verification>`) and the next step
as the single `## Next best step` bullet. The next step's feature id is
the text before its first colon.

## Output

```json
{
  "workspace": "...",
  "session": "002",
  "passes": [ { "pass": 1, "steps": [ { "id", "outcome" } ], "verdict": "changed" | "already-clean" } ],
  "summary": { "handoff_next_step", "passing", "progress_entries", "scratch_files" }
}
```

A pass's `verdict` is `already-clean` when no step in it changed anything.
`summary.progress_entries` counts `## Session <id>` headings in the progress
log, so a protocol that appends instead of reconciling shows up there as
well as in the pass reports.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | the requested passes ran; the report is on stdout |
| 2 | usage error, a `--passes` value outside 1 to 5, or a workspace missing or lacking `session.json`; stdout empty |

The verdict this exercise grades lives in the report, not in the exit
code: an interrupted protocol is not an error, it is a state to reconcile.

## Fixtures

- `workspaces/workspace-dirty`: nothing has been cleaned. `csv-export` is
  `in-progress`, the progress log holds only session 001, `scratch/` holds
  a probe file, and there is no handoff.
- `workspaces/workspace-half-cleaned` (the trap): the protocol was
  interrupted after its second step. The session 002 entry is already in
  the progress log and `csv-export` is already `passing` with evidence,
  while `scratch/` and the missing handoff are still outstanding. A first
  pass over this workspace has to reconcile, not repeat.

## Starter state (the intended failure)

The starter writes the progress entry unconditionally: a progress log is
append-only, so the newest session goes on top. Its other three steps
already reconcile, comparing the wanted state to the current one before
touching anything, so the starter is a working protocol that is safe to
re-run in three places out of four.

Verification fails first on the `half-cleaned-retry` case at
`$.passes[0].steps[0].outcome: 'added a session 002 entry to
claude-progress.md' != 'claude-progress.md already records session 002'`:
the entry is already there and the starter writes a second one. The
`dirty-one-pass` case passes under the starter, because appending and
reconciling agree on the first run over a workspace that has not been
touched, which is exactly why this defect survives testing.

## Expected output

- `dirty-one-pass`: `workspace-dirty` at 1 pass to
  `expected/dirty-one-pass.json`, exit 0 (all four steps change something).
- `half-cleaned-retry`: `workspace-half-cleaned` at 1 pass to
  `expected/half-cleaned-retry.json`, exit 0 (the first two steps report
  the state as already recorded).
- `dirty-two-passes`: `workspace-dirty` at 2 passes to
  `expected/dirty-two-passes.json`, exit 0 (the second pass is
  `already-clean` and `summary.progress_entries` is 1).
