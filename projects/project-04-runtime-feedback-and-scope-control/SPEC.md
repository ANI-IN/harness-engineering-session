# SPEC: project-04 runtime-feedback-and-scope-control

kb v4: the same knowledge-base tool, made observable and scope-controlled.
The delta is structured logging with a `logs` surface, corrupt-index
detection with `index --rebuild` as the recovery, `kb guard` (the
architecture rules executed as behavior), a WIP=1 check in the workspace
doctor, and a server that refuses writes. Both implementations
(`solution/python/main.py`, `solution/typescript/main.ts`) must produce
byte-identical output after normalization for every case in `cases.json`.

The `kb` canonical command form and its per-track expansions are exactly
as in [project 01's SPEC](../project-01-baseline-vs-minimal-harness/SPEC.md);
paths below expand against this directory.

## Delta from project 03

Contract evolution follows
[project 01's pre-1.0 declaration](../project-01-baseline-vs-minimal-harness/SPEC.md#contract-evolution-pre-10):
rows marked **Breaking** change what a caller of the previous surface
observes; everything else is additive.

The starter IS project 03's solution app, verbatim. The delta:

| Area | v3 (starter) | v4 (solution) |
| --- | --- | --- |
| logging | none | `init`, `import`, `index`, and `ask` append structured events to `log/events.jsonl` under the data directory (below); read surfaces stay silent |
| `logs` | absent (usage error) | prints the log, filterable by `--level` and `--event` |
| `status` | states `empty`, `partial`, `ready`, `stale` | **Breaking**: the report gains a `corrupt` list and a `corrupt` state (empty-text chunks detected), taking precedence over `stale`; callers switching on the old shape see a new key and a new value |
| `index` | sha-gated re-chunking | adds `--rebuild` (force re-chunk regardless of sha), the recovery for corruption the sha gate cannot see |
| `ask` | refuses unless `ready` | unchanged rule; a refusal now also logs a WARN naming the state and the offending documents |
| `serve` | answers any method through the GET logic | **Breaking**: non-GET requests get `405 {"error": "read-only"}`; the write boundary is behavior, not documentation |
| `guard` | absent (usage error) | the behavioral architecture guard (below) |
| `workspace-check` | three checks | **Breaking**: a fourth check, `wip-limit` (at most one feature `in-progress`); reports gain a row and a workspace can newly fail |
| `continuity` | as in project 03 | unchanged protocol; its pinned report changes because session commands now log and `status` output carries `corrupt` |

Harness artifacts accrete monotonically; nothing is dropped:

| Artifact | project 03 | project 04 |
| --- | --- | --- |
| router AGENTS.md, CLAUDE.md, init.sh, feature_list.json, claude-progress.md, session-handoff.md, clean-state-checklist.md, docs/ (ARCHITECTURE, PRODUCT, IMPORTING, INDEXING) | present | kept, updated for v4 |
| docs/OBSERVABILITY.md | absent | new focused doc the router points to (logs, guard, recovery) |

Corpus-divergence: kb-data/index/documents-meta.json (carried from
project 03's v3 metadata shape; diverges from project 02's v2 copy for
the same declared reason)

Corpus-divergence: workspaces/workspace-stale/feature_list.json (project
04 seeds a fourth defect: two features in-progress, violating the WIP
limit)

## Structured logging (pinned)

- Events append to `log/events.jsonl` under the data directory, one JSON
  object per line, compact separators:
  `{"seq", "level", "command", "event", "detail"}`.
- **Determinism by module rule**: `seq` is one plus the number of
  existing lines; there are no timestamps. A real deployment would add
  them at this seam; the module's no-wall-clock rule keeps every log
  byte-reproducible.
- Levels: `DEBUG < INFO < WARN < ERROR`. Pinned events: `init/done`
  (created, seeded counts), `import/done` (imported ids, skipped
  filenames), `index/document-chunked` per re-chunked document (document,
  chunks, empty_chunks), `index/done` (indexed, skipped, rebuild),
  `ask/answered` (citations, top_score), `ask/refused` at WARN (state,
  corrupt, stale). Read surfaces (`list`, `show`, `status`, `logs`,
  `serve`, `workspace-check`, `guard`) never write the log.
- `kb logs --data-dir DIR [--level L] [--event E]` prints
  `{"entries": [...], "total"}` filtered to entries at or above the
  level (default DEBUG) and matching the event when given.

## Corruption and recovery (the carried seeded defect)

The reference course seeds a chunker bug (documents over 1000 characters
produce empty chunks) in its starter's source, announced by a comment.
This module keeps the defect but moves it where seeded defects live:
`fixtures/kb-data-corrupt` is a workspace state such a buggy chunker
leaves behind. Its `chunks.json` gives `architecture-notes` an empty
first chunk (`chars` 0, `words` 0, `text` "") while the recorded sha256
still matches the document, which is precisely why the sha-gated
`kb index` cannot heal it and `--rebuild` exists.

| Seeded state | Observable symptom | Caught by |
| --- | --- | --- |
| empty chunk, sha intact | `status` reports state `corrupt` naming `architecture-notes`; `ask` refuses (exit 1) and logs `ask/refused` at WARN | `status`, the WARN in `kb logs --level WARN`, and the pinned `ask-corrupt-refuses` case |
| after `index --rebuild` | chunks.json byte-equals the clean indexed fixture; state `ready` | the `rebuild-recovers-the-corrupt-index` artifact check |

The committed `log/events.jsonl` in the corrupt fixture holds exactly the
WARN a refused `ask` wrote there; `logs-surface-the-warning` pins it.

## The guard (architecture rules as behavior)

`kb guard --data-dir DIR` copies the data directory into a private
sandbox and executes the ARCHITECTURE rules (the reference course grepped
source text for layer violations; executing the properties survives any
refactor that keeps the behavior):

1. **server-read-only**: boots the real server, POSTs to `/documents`,
   requires `405` and a bit-identical data directory afterwards.
2. **storage-containment**: runs a real `import` and requires that no
   file outside the data directory appeared or changed (a probe file is
   planted and checked).
3. **derived-rebuildable**: deletes `chunks.json`, runs `index`, requires
   state `ready` (derived state must be disposable).

Report `{"checks": [{"id", "passed", "detail"}...], "sound"}`; exit 0
sound, 1 not. Deterministic: the sandbox is private, and no path appears
in the output.

## Workspace doctor (v4)

The fourth check, `wip-limit`: at most one feature may be `in-progress`
(WIP=1, the glossary's scope-control discipline).

### Seeded defects (fixtures/workspaces/workspace-stale)

The stale workspace fixture carries four seeded defects, one per check
(defects 1-3 carried from project 02; defect 4 is new here):

| # | Defect | Observable symptom | Caught by |
| --- | --- | --- | --- |
| 1 | `AGENTS.md` routes to `docs/IMPORTING.md`, which does not exist | `unresolved router target(s): docs/IMPORTING.md` | `router-targets` |
| 2 | handoff lacks the `Next best step` section | `missing required section(s): Next best step` | `session-handoff` |
| 3 | feature `document-import` is `passing` with no evidence | `passing without evidence: document-import` | `feature-evidence` |
| 4 | `detail-view` and `chunk-preview` are both `in-progress` | `2 features in-progress (detail-view, chunk-preview); the WIP limit is 1` | `wip-limit` |

## Starter state

The starter (project 03's solution) must keep passing the carried v3
behaviors (list, import, show, index building and idempotency, the
grounded answer, the unknown-id and uninitialized exits, self-check) and
fail every v4 delta case: `logs` and `guard` are usage errors (exit 2);
`init` writes no log (the artifact check fails); `status` output lacks
`corrupt` (both status cases fail; the corrupt directory reads as
`ready` to v3, which is the whole point); `ask` against the corrupt
directory **answers from the broken index where v4 refuses**; `--rebuild`
is unknown; workspace reports lack the fourth check; the continuity
report differs. `verify.sh` asserts the starter stage FAILS conformance.

## Cases

`cases.json` covers: init recording metadata and its first log entry
(both artifact-checked), the carried list/import/show/index/ask surface,
status on ready and corrupt directories, the corrupt refusal, rebuild
recovering to a byte-identical clean index, the WARN surfaced by `logs`,
the sound guard, the self-check, the four-check workspace doctor on the
ready and stale fixtures, the full continuity proof, and a usage error.

## Tests

`solution/python/tests/` (pytest) and `solution/typescript/tests/`
(vitest) cover the log sequence rule and level filtering, corrupt-state
precedence over stale, rebuild recovery end to end, each guard check
against a deliberately violating condition (a mutated sandbox), the WIP
check in isolation, the dogfood check (`harness/` passes its own
four-check doctor), and the independent evidence check: every evidence
command in `harness/feature_list.json` executed through the real CLI as a
subprocess and compared to the recorded `observed` string. `make verify`
runs both suites.
