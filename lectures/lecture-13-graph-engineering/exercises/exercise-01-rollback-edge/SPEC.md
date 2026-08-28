# SPEC: exercise-01 rollback-edge

The lecture demo's graph declares one rollback edge, and its `undo` node
replays the journal the `apply` node wrote
([../../code/SPEC.md](../../code/SPEC.md)). This exercise is that node on
its own, over journals the demo does not produce: several writes to one
file, and a workspace something else touched after the run.

## CLI surface

```text
main <workspace-dir> <journal-file>
```

`<workspace-dir>` is the workspace as it stands after a failed
verification, read once and reverted in memory; nothing on disk is
written. `<journal-file>` is what the run recorded while it worked:

```json
{
  "session": "007",
  "operations": [
    { "op": "append", "path": "config/app.conf", "line": "export_dir=out/reports" },
    { "op": "create", "path": "scratch/apply-notes.txt", "lines": ["probe=page-size"] }
  ]
}
```

Operations appear in the order the run made them. Both tracks treat LF and
CRLF alike as line separators (docs/conventions.md, semantic rules), and
"lines" everywhere below means the file's non-empty lines.

## The two operation kinds

Reverting is safe only from the tip: an undo may remove what this run put
there and nothing else.

| `op` | Reverted when | Effect | Kept when |
| --- | --- | --- | --- |
| `append` | `line` is the last line of `path` | that line is removed | anything else is now the last line, so removing `line` would discard a later change |
| `create` | `path` holds exactly the recorded `lines` | the file is removed | the file's lines have changed, so removing it would discard a later change |

Both conditions are already implemented in the starter and are correct.
What decides the outcome of a whole journal is the order the operations
are attempted in, because reverting one operation changes what the tip of
its file is for the next.

## Output

```json
{
  "workspace": "...",
  "session": "007",
  "operations": [
    { "index", "op", "outcome", "path", "target", "why" }
  ],
  "residue": ["config/app.conf still carries export_dir=out/reports"],
  "restored": true,
  "verdict": "restored" | "residue-left"
}
```

Rows appear in journal order, one per operation, whatever order they were
attempted in; `index` is the operation's position in the journal.
`outcome` is `reverted` or `kept`. `target` is the appended line for an
`append` and the path for a `create`. `why` is the sentence that names the
reason. `residue` lists what is still in the workspace because an
operation was kept, in row order:
`<path> still carries <line>` for an append, `<path> is still in the
workspace` for a create. `restored` is true when every operation is
`reverted`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `restored`: the workspace holds nothing this run added |
| 1 | `residue-left`: at least one operation could not be reverted |
| 2 | usage error, a missing workspace directory, or a missing journal file; stdout empty |

## Fixtures

- `workspaces/workspace-applied`: `src/report.txt` ends with the appended
  `writer=csv`, `config/app.conf` ends with the two appended lines
  `export_dir=out/reports` and `writer_dir=out/csv` (over a pre-existing
  `export_dir=out/old` the run did not own), and
  `scratch/apply-notes.txt` holds exactly the lines the run created.
- `workspaces/workspace-touched`: `src/report.txt` carries two appended
  lines, `writer=csv` then `header=on`; `config/app.conf` carries one
  appended `export_dir=out/reports` under a further `owner=platform` line
  that something else added after the run stopped.
- `journals/journal-touched.json`: four operations over
  `workspace-touched`, two of them appends to `src/report.txt`.
- `journals/journal-mixed.json`: four operations over
  `workspace-applied`, two of them appends to `config/app.conf`, plus one
  create.
- `journals/journal-two-appends.json` (the trap): only the two appends to
  `config/app.conf`. It isolates the case the naive draft gets wrong, with
  no operation beside it that could make the report look mostly right.

## Starter state (the intended failure)

The starter walks the journal from the first write to the last, on the
reading that a journal is a list of steps and a list of steps is replayed
in order. Every other part is complete: both reverting rules, the row
shape, the residue strings, the verdict, and the exit codes.

Verification fails first on the
`partly-reverted-under-a-later-change` case at
`$.operations[0].outcome: 'kept' != 'reverted'`: `writer=csv` was appended
to `src/report.txt` before `header=on`, so at the moment the starter
reaches it the tip of the file is the later line, the undo declines to
remove it, and one of the run's own writes survives the rollback. Walking
the journal backwards removes `header=on` first, which makes `writer=csv`
the last line again and reverts it too. That case exits 1 under both
drafts, so the failure the runner reports is the wrong value and not a
wrong exit code. The starter runs cleanly.

## Expected output

- `partly-reverted-under-a-later-change`: `workspace-touched` +
  `journal-touched.json` to `expected/partly-reverted.json`, exit 1. The
  append under `owner=platform` is kept whatever order the journal is
  replayed in, because the tip belongs to someone else; the other three
  operations are the run's own to reverse.
- `mixed-journal`: `workspace-applied` + `journal-mixed.json` to
  `expected/mixed.json`, exit 0 (four operations, all reverted).
- `two-appends-to-one-file`: `workspace-applied` +
  `journal-two-appends.json` to `expected/two-appends.json`, exit 0.
