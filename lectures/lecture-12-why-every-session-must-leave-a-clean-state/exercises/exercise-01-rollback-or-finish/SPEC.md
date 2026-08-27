# SPEC: exercise-01 rollback-or-finish

The lecture demo's clean exit rolls back a half applied draft and keeps a
verified change ([../../code/SPEC.md](../../code/SPEC.md)). This exercise
is the decision behind that step, generalized: a session ends holding a
list of edits, and each one gets exactly one of three moves before the
session may end.

## CLI surface

```text
main <workspace-dir> <ending-file>
```

`<workspace-dir>` carries `checks.json` and the files the checks probe,
with the demo's two check kinds, detail strings, and line-ending rule
unchanged:

| kind | fields | passes when |
| --- | --- | --- |
| `key-declared-once` | `path`, `key` | exactly one line starts `<key>=` |
| `file-has-line` | `path`, `prefix` | some line starts with the prefix |

`<ending-file>` is the list of edits the session made:

```json
{
  "session": "003",
  "edits": [ { "path", "check", "created": true | false } ]
}
```

`created` is true when this session brought the file into existence and
false when the file was already in the workspace and the session changed
it. It is a fact about the session, not about the file's current content.

## The three moves

Every edit is re-checked, and the check result plus `created` selects one
move:

| Check result | `created` | Move | Why |
| --- | --- | --- | --- |
| `pass` | either | `finish` | verified work; it stays |
| `fail` | `true` | `roll-back` | reverting deletes only what this session added, which restores the last consistent state exactly |
| `fail` | `false` | `declare` | reverting would discard state the session does not own, so the change stays and the handoff must name the failing check |

The distinction is the point: an unverified change a session created and
declares instead of reverting is a half applied change left in the tree,
which is what the next session trips over.

## Output

```json
{
  "workspace": "...",
  "session": "003",
  "edits": [ { "path", "check", "created", "actual", "detail", "decision" } ],
  "summary": { "declare", "finish", "roll_back" },
  "verdict": "may-end" | "exit-protocol-owed"
}
```

`actual` is `pass` or `fail` from the fresh check run and `detail` is that
run's detail string; both are reported whatever the decision is. `summary`
counts decisions (`roll_back` with an underscore, since it is a JSON key).
`verdict` is `may-end` when every edit is `finish`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `may-end`: every edit is verified, so the session may end as it stands |
| 1 | `exit-protocol-owed`: at least one edit must be rolled back or declared |
| 2 | usage error, or a missing workspace, `checks.json`, or ending file; stdout empty |

## Fixtures

- `workspaces/workspace-open`: `src/list.txt` declares `sort` once (its
  check passes), `src/tags.txt` is a draft with no `writer=` line, and
  `config/store.conf` has no `index_path=` line.
- `workspaces/workspace-settled`: the same three files with every check
  passing.
- `endings/ending-mixed.json`: three edits, one per file, with
  `src/tags.txt` created this session and the other two pre-existing.
- `endings/ending-created-only.json` (the trap): one edit,
  `src/tags.txt`, created this session and unverified. It isolates the
  case the naive draft gets wrong, with no passing edit beside it to make
  the report look mostly right.

## Starter state (the intended failure)

The starter has two moves instead of three: a passing check is `finish`
and a failing check is `declare`, on the reasoning that an unverified
change is not lost as long as the handoff mentions it. It re-checks every
edit and reports `actual` and `detail` correctly; it never reads
`created`, so it cannot tell a change it can safely revert from one it
cannot.

Verification fails first on the `mixed-ending` case at
`$.edits[1].decision: 'declare' != 'roll-back'`: `src/tags.txt` was
created by this session and its check fails, so the exit protocol owes a
rollback and the starter records a declaration. The `settled-may-end`
case passes under the starter, because the two drafts differ only where a
check fails. The starter runs cleanly and fails only by producing that
wrong value.

## Expected output

- `mixed-ending`: `workspace-open` + `ending-mixed.json` to
  `expected/mixed.json`, exit 1 (one `finish`, one `roll-back`, one
  `declare`).
- `created-and-unverified`: `workspace-open` +
  `ending-created-only.json` to `expected/created-only.json`, exit 1.
- `settled-may-end`: `workspace-settled` + `ending-mixed.json` to
  `expected/settled.json`, exit 0.
