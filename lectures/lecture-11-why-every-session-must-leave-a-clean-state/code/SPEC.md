# SPEC: session-ending

Two sessions run in sequence over one workspace. The first session does
the same work either way and then ends in one of two disciplines; the
second session runs one protocol against whatever it inherited. The demo
is the divergence in the second session's behaviour, and the only variable
between the two runs is `--exit`.

## CLI surface

```text
main resume <workspace-dir> --exit=clean|dirty   # both sessions; the behavioural run
main first  <workspace-dir> --exit=clean|dirty   # the first session and its checklist
```

The workspace is read from disk once and edited in memory. Nothing under
`<workspace-dir>` is written, so the committed fixture is unchanged by any
number of runs and every command in the lecture README is idempotent. The
in-memory map is the seam where a live harness would edit real files
([deterministic fake agent](../../../docs/glossary.md#core-model)).

## The workspace contract

`<workspace-dir>` carries `checks.json`, `feature_list.json`,
`claude-progress.md`, and the probed sources:

```json
{ "task": "...", "checks": [ { "id", "feature", "kind", ...kind fields } ] }
```

`feature` names the `feature_list.json` entry the check proves. `kind`
selects one of two executable probes, the deterministic stand-in for
running the real verification command:

| kind | fields | passes when | detail strings |
| --- | --- | --- | --- |
| `key-declared-once` | `path`, `key` | exactly one line starts `<key>=` | `<path> declares <key> once` / `<path> has no <key>= line` / `<path> declares <key> N times` / `<path> missing` |
| `file-has-line` | `path`, `prefix` | some line starts with the prefix | `<path> has a line starting with <prefix>` / `<path> has no line starting with <prefix>` / `<path> missing` |

Both tracks treat LF and CRLF alike as line separators (see
docs/conventions.md, semantic rules).

### Artifact parsing

One parser reads all three artifact sections this unit consults: the ids
named by `- <id>: <text>` bullets under a given `##` heading.

- `claude-progress.md`, `## Verified now`: the features the record calls
  verified.
- `session-handoff.md`, `## Next best step`: the feature the previous
  session named for this one.
- `session-handoff.md`, `## Broken or unverified`: the checks whose
  failure the previous session declared.

## The first session (pinned)

Five work steps, identical under both disciplines:

1. implement the csv writer: append `writer=csv` to `src/export.txt`.
2. wire the export directory: append `export_dir=out/reports` to
   `config/app.conf`.
3. run check `unit-csv`: passes.
4. open `pdf-export`: set its status to `in-progress` and draft
   `src/pdf.txt` with `stage=draft` and no `writer=` line.
5. probe the pdf page size by hand: write `scratch/probe-pdf.txt`.

Then the ending:

- `--exit=dirty` records one event and stops. The session leaves
  `csv-export` `in-progress` with every check on it passing, no progress
  entry, a half applied `src/pdf.txt`, a scratch file, and no handoff.
- `--exit=clean` runs the exit protocol as five further events: run the
  declared checks; roll back the half applied pdf draft (delete
  `src/pdf.txt`, return `pdf-export` to `not-started`); set `csv-export`
  to `passing` with evidence (`check unit-csv`, `exit 0, src/export.txt
  declares writer once`, `2026-08-27`); record the session in
  `claude-progress.md` (a verified-now bullet plus a session 002 entry);
  delete `scratch/probe-pdf.txt` and write `session-handoff.md` naming
  `pdf-export` as the next best step.

## The second session (pinned, one protocol)

1. read `session-handoff.md` for the next best step.
2. read `claude-progress.md` for the features recorded verified.
3. read `feature_list.json` for the statuses, and count how many features
   are `in-progress`.
4. choose the feature: the handoff's next step if there is one; otherwise
   the first `in-progress` feature the progress log does not record as
   verified; otherwise the first feature declared.
5. implement the chosen feature: append its declaration line to its file,
   creating the file with its module header when absent. The edit does not
   consult whether a declaration is already there, because the session
   that runs it believes the feature is unstarted.
6. run every declared check.
7. close the session, naming what completed or what regressed.

## Outcome and exit codes

The checks are run once more after the first session, before the second
begins; that snapshot is what the first session handed over. `regressed`
lists checks that were `pass` in the snapshot and are `fail` now.
`completed` lists features whose every check passes now and did not in the
snapshot. `result` is `resumed` when nothing regressed and something
completed, `derailed` otherwise.

| Code | Meaning |
| --- | --- |
| 0 | `resume`: `resumed`. `first`: every checklist item passed |
| 1 | `resume`: `derailed`. `first`: at least one checklist item failed |
| 2 | usage error, an unknown `--exit` value, or `<workspace-dir>` missing or lacking `checks.json`; stdout empty |

Output of `resume`: `{"workspace", "exit_discipline", "first_session":
{"task", "events"}, "second_session": {"chose", "events", "checks"},
"outcome": {"completed", "regressed", "result"}}`, where an event is
`{"step", "action", "outcome"}` and a check result is `{"id", "feature",
"status", "detail"}`.

## The clean state checklist (supporting evidence)

`first` grades the ending against five items of
[`clean-state-checklist.md`](../../../library/templates/clean-state-checklist.md),
the five that are mechanical over this workspace model. Output:
`{"workspace", "exit_discipline", "task", "events", "clean_state":
[{"item", "status", "detail"}], "failed"}`.

| Item | Passes when |
| --- | --- |
| `verification-recorded` | every failing check either belongs to a `not-started` feature or is named under the handoff's `## Broken or unverified` |
| `statuses-true` | no feature is `passing` without all its checks green and evidence recorded, and no feature whose checks are all green is left at another status |
| `progress-recorded` | `claude-progress.md` records every feature whose checks all pass |
| `no-stray-artifacts` | no file under `scratch/` |
| `next-step-written` | `session-handoff.md` names a next best step that is a declared feature and is not already `passing` |

The checklist's other three items (a clean-state build, uncommitted
changes, and the `./init.sh` startup path) are outside this fixture's
model and are not graded here.

## Fixtures and seeded symptoms

`fixtures/workspace` is the single committed workspace, in the state the
first session opens it: `csv-export` `in-progress` with no writer line,
`pdf-export` `not-started`, a progress log whose verified-now section
names nothing, no `session-handoff.md`, no `scratch/`.

The dirty ending seeds three leavings, each with an exact consequence in
the second session:

| Leaving | Caught by | Consequence in the second session |
| --- | --- | --- |
| `claude-progress.md` carries no entry for the session's work | `progress-recorded` | step 2 reads nothing verified, so `csv-export` is not skipped |
| `csv-export` left `in-progress` beside `pdf-export` `in-progress`, no handoff | `statuses-true`, `next-step-written` | step 4 has two features in flight and no next step, so it takes `csv-export`, which is finished |
| `src/pdf.txt` left half applied, `scratch/probe-pdf.txt` left in the tree | `verification-recorded`, `no-stray-artifacts` | `unit-pdf` stays failing on a feature nobody is working on |

The observable symptom is the redo in step 5: `src/export.txt` ends up
declaring `writer` twice, so `unit-csv` reports
`src/export.txt declares writer 2 times` and the run exits 1. Both tracks
produce that same failure. The clean ending removes all three leavings and
the same second-session protocol finishes `pdf-export` instead, exiting 0.
