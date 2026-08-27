# SPEC: project-02 agent-readable-workspace

kb v2: the same knowledge-base tool as project 01, made agent-readable.
The product delta is import, a detail view, and metadata persistence; the
harness delta is a router AGENTS.md, a session handoff, and
`workspace-check`, the workspace-readability doctor. Both implementations
(`solution/python/main.py`, `solution/typescript/main.ts`) must produce
byte-identical output after normalization for every case in `cases.json`.

The `kb` canonical command form and its per-track expansions are exactly
as in [project 01's SPEC](../project-01-baseline-vs-minimal-harness/SPEC.md);
paths below expand against this directory.

## Delta from project 01

The starter IS project 01's solution app (v1: `init`, `list`, `ask`,
`serve`) with the project 01 experiment apparatus removed; that apparatus
was project 01's study harness, not product, and stays there. Everything
v1 does, v2 still does. The delta:

| Area | v1 (starter) | v2 (solution) |
| --- | --- | --- |
| `init` | creates dirs, copies seed files | also records every document in `index/documents-meta.json` (origin `seeded`); reports `metadata_entries` |
| `list` | scans `documents/` | reads the **metadata index only** (the system of record; a directory scan is rediscovery); adds `origin` per document; exit 1 with a pinned error when the index is missing |
| `ask` | scans `documents/` | reads documents via the metadata index; output shape unchanged |
| `import` | absent (usage error) | copies files in, records them (origin `imported`), skips already-imported ids; the index stays sorted by id |
| `show` | absent (usage error) | detail view: the metadata entry plus full `content`; exit 1 for unknown ids |
| `serve` | `/health`, `/documents`, `/ask` | adds `/documents/{id}` (404 unknown); `--self-check` also fetches the first document's detail and reports `{"id", "lines"}` |
| `experiment` | absent here | stays in project 01 |
| `workspace-check` | absent (usage error) | the workspace-readability doctor (below) |

Harness artifacts accrete monotonically over project 01's set; nothing is
dropped (the reference course dropped CLAUDE.md, init.sh, and the
progress log at this stage, which this project deliberately does not):

| Artifact | project 01 | project 02 |
| --- | --- | --- |
| AGENTS.md | single instruction file | **router**: a short map that links to the focused docs (lecture 04) |
| CLAUDE.md, init.sh, claude-progress.md, feature_list.json, docs/ARCHITECTURE.md, docs/PRODUCT.md | present | kept, updated for v2 |
| docs/IMPORTING.md | absent | new focused doc the router points to |
| session-handoff.md | absent | new; canonical handoff format (below) |

## CLI surface

```text
kb init --data-dir DIR [--seed SRC]
kb list --data-dir DIR
kb ask --data-dir DIR "QUESTION"
kb show --data-dir DIR ID
kb import --data-dir DIR FILE...
kb serve --data-dir DIR [--port N] [--self-check]
kb workspace-check --workspace DIR
```

| Exit code | Meaning |
| --- | --- |
| 0 | success; `workspace-check`: workspace ready |
| 1 | data directory or metadata index missing; unknown document id; `workspace-check`: workspace not ready |
| 2 | usage error, unreadable seed/file/workspace, invalid port |

Pinned error strings (stderr, stdout empty): missing data directory as in
project 01; missing index exactly
`error: metadata index missing in DIR; run kb init first`; unknown id
exactly `error: no document with id ID`.

## Output shapes

- `init`: `{"data_dir", "created", "seeded", "metadata_entries"}`.
- Metadata entry (in the index file, `list`, `import`, `show`): keys in
  order `id`, `title`, `filename`, `lines`, `origin`; `origin` is
  `seeded` or `imported`; the index file is a JSON array sorted by `id`.
- `list`: `{"documents": [entry...]}` in index (id) order.
- `import`: `{"imported": [entry...], "skipped": [{"filename",
  "reason": "already-imported"}]}`.
- `show`: the entry plus `"content"` (the file's full text).
- `ask`: unchanged from project 01 (question, citations, answer);
  retrieval semantics, tokenization, ranking, and the composer seam are
  identical to project 01's SPEC.
- `serve --self-check`: `{"self_check": {"health": {"status",
  "documents"}, "documents", "detail": {"id", "lines"}}}` (detail `null`
  for an empty knowledge base); no port in any output.

## The workspace-readability doctor

`kb workspace-check --workspace DIR` answers "can a fresh session resume
from this directory's recorded state alone?" with three checks, reported
as `{"checks": [{"id", "passed", "detail"}...], "ready"}` and the verdict
in the exit code (0 ready, 1 not):

1. **router-targets**: every relative markdown link target in `AGENTS.md`
   exists (fragments stripped; http/https ignored). A router that points
   at missing docs sends the fresh session back to rediscovery.
2. **session-handoff**: `session-handoff.md` exists, parses in the
   canonical handoff format, and contains the required sections
   `Verified now`, `Broken or unverified`, and `Next best step`.
3. **feature-evidence**: `feature_list.json` uses only the statuses
   `not-started`, `in-progress`, `blocked`, `passing`, and every
   `passing` feature carries evidence with non-empty `command`,
   `observed`, and `date`.

### Canonical handoff format (pinned)

The format taught by lecture 05's handoff-roundtrip exercise: one
`# <title>` line, then `## <section>` headings whose items are `- <item>`
lines; parsing collects every section in document order and never drops
unknown sections. This project's committed
[`harness/session-handoff.md`](./harness/session-handoff.md) is an
instance, and the test suites run the doctor against `harness/` itself:
the project's own workspace must pass its own readability check.

## Seeded defects (fixtures/workspaces/workspace-stale)

| # | Defect | Observable symptom | Caught by |
| --- | --- | --- | --- |
| 1 | `AGENTS.md` routes to `docs/IMPORTING.md`, which does not exist | `unresolved router target(s): docs/IMPORTING.md` | `router-targets` |
| 2 | handoff lacks the `Next best step` section | `missing required section(s): Next best step` | `session-handoff` |
| 3 | feature `document-import` is `passing` with no evidence | `passing without evidence: document-import` | `feature-evidence` |

Both tracks report all three identically; `expected/workspace-stale.json`
pins the report and the case pins exit 1.

## Starter state

The starter must pass the v1-carryover cases it can express and fail
every v2 case: `import`, `show`, and `workspace-check` are usage errors
(exit 2) in v1; `list` output lacks `origin`; `init` writes no index (the
case's artifact check fails); `serve --self-check` lacks `detail`.
`verify.sh` asserts the starter stage FAILS conformance: a starter that
already passes the v2 cases is not a genuine starting point.

## Cases

`cases.json` covers: init recording metadata (artifact-checked against
the committed index fixture), list from metadata, the missing-index exit,
the grounded answer (unchanged from project 01 on the same corpus),
import (stdout plus two artifact checks: the updated index and the
byte-equal copied document), duplicate import skipping, the detail view,
the unknown-id exit, the HTTP self-check with detail, the ready and stale
workspaces, and a usage error.

## Tests

`solution/python/tests/` (pytest) and `solution/typescript/tests/`
(vitest) cover metadata round-trip through a fresh process, title and
line-count extraction, duplicate skipping, each stale-workspace defect in
isolation, the handoff parser, the dogfood check above (`harness/` passes
`workspace-check`), and the **independent evidence check**: every feature
evidence command in `harness/feature_list.json` executed through the real
CLI as a subprocess, output compared to the recorded `observed` string.
`make verify` runs both suites.
