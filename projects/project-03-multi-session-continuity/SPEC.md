# SPEC: project-03 multi-session-continuity

kb v3: the same knowledge-base tool, made to survive session restarts.
The product delta is metadata extraction, deterministic chunking, an
indexing status surface, and chunk-grounded answers; the continuity delta
is `kb continuity`, a two-session resume proof whose every step crosses a
real process boundary. Both implementations (`solution/python/main.py`,
`solution/typescript/main.ts`) must produce byte-identical output after
normalization for every case in `cases.json`.

The `kb` canonical command form and its per-track expansions are exactly
as in [project 01's SPEC](../project-01-baseline-vs-minimal-harness/SPEC.md);
paths below expand against this directory.

## Delta from project 02

Contract evolution follows
[project 01's pre-1.0 declaration](../project-01-baseline-vs-minimal-harness/SPEC.md#contract-evolution-pre-10):
rows marked **Breaking** change what a caller of the previous surface
observes; everything else is additive.

The starter IS project 02's solution app, verbatim (v2: `init`, `list`,
`ask`, `show`, `import`, `serve`, `workspace-check`). Everything v2 does,
v3 still does; `workspace-check` is carried unchanged (its cases must
keep passing against the starter). The delta:

| Area | v2 (starter) | v3 (solution) |
| --- | --- | --- |
| metadata entries | `id`, `title`, `filename`, `lines`, `origin` | plus `metadata` `{chars, words, paragraphs}` extracted on seed and import |
| `show` | entry plus content | entry (with `metadata`) plus content |
| `index` | absent (usage error) | chunks every document into `index/chunks.json`; idempotent via per-document content sha256; re-chunks only what changed |
| `status` | absent (usage error) | `{documents, indexed, total_chunks, state, stale}` with state `empty`, `partial`, `ready`, or `stale`, computed from disk only |
| `ask` | line-grounded, works without an index | **Breaking** twice over: citations change shape (chunk-grounded: `chunk` replaces `line`, excerpts come from chunks) and the command refuses (exit 1, pinned error) unless state is `ready`, where v2 answered from any initialized directory |
| `serve` | `/health`, `/documents`, `/documents/{id}`, `/ask` | adds `/status`; `/ask` returns 503 when the index is not ready; `--self-check` also reports the index `status` state |
| `continuity` | absent (usage error) | the two-session resume proof (below) |
| `list`, `import`, `init` surfaces | v2 shapes | unchanged output shapes except `import` echoing entries now includes `metadata`, and the metadata index `init` records carries it |

Corpus-divergence: kb-data/index/documents-meta.json (project 03's
committed metadata index carries the v3 `metadata` object per entry; the
document corpus itself stays byte-identical across projects)

Harness artifacts accrete monotonically over project 02; nothing is
dropped (the reference's fullest-harness project drops CLAUDE.md at this
stage, which this project deliberately does not):

| Artifact | project 02 | project 03 |
| --- | --- | --- |
| router AGENTS.md, CLAUDE.md, init.sh, feature_list.json, claude-progress.md, session-handoff.md, docs/ (ARCHITECTURE, PRODUCT, IMPORTING) | present | kept, updated for v3 |
| docs/INDEXING.md | absent | new focused doc the router points to |
| clean-state-checklist.md | absent | new; command-backed checklist (library template instance) |

## CLI surface

```text
kb init --data-dir DIR [--seed SRC]
kb list --data-dir DIR
kb ask --data-dir DIR "QUESTION"
kb show --data-dir DIR ID
kb import --data-dir DIR FILE...
kb index --data-dir DIR
kb status --data-dir DIR
kb serve --data-dir DIR [--port N] [--self-check]
kb workspace-check --workspace DIR
kb continuity [--workdir DIR]
```

| Exit code | Meaning |
| --- | --- |
| 0 | success; `workspace-check` ready; `continuity` resumed |
| 1 | missing data dir/index; unknown id; index not ready (`ask`); workspace not ready; continuity did not resume |
| 2 | usage error, unreadable input, invalid port |

New pinned error string: `error: index not ready in DIR; run kb index
first`. All project 02 pinned errors are unchanged.

## Chunking (pinned)

1. Paragraphs are the blank-line separated blocks of the document
   (split on a newline, optional spaces or tabs, newline), trimmed,
   empties dropped.
2. Paragraphs pack greedily into chunks: a paragraph joins the current
   chunk (joined with one blank line) unless that would exceed 500
   characters and the chunk is non-empty; a single paragraph longer than
   500 characters stays whole as its own chunk.
3. A chunk record is `{"index", "chars", "words", "text"}`; per-document
   records in `index/chunks.json` are
   `{"document", "sha256", "chunks"}`, sorted by document id, where
   `sha256` is the hex digest of the document's UTF-8 text. The sha256 is
   what makes `index` idempotent and `status` able to name `stale`
   documents.

## Retrieval (v3, pinned)

Tokenization is unchanged from project 01. Candidates are the indexed
chunks; score is the number of distinct question tokens in the chunk's
token set; rank by score descending, document id ascending, chunk index
ascending; keep the top 2 with score >= 1. Citations are
`{"document", "title", "chunk", "excerpt", "score"}` where `excerpt` is
the chunk's first line. The composer (the model seam) emits exactly
`Based on "TITLE" (chunk N): EXCERPT` plus, with a second citation, a
space followed by `See also "TITLE2" (chunk M).`; the no-match refusal
sentence is unchanged from project 01.

## The two-session continuity proof

`kb continuity [--workdir DIR]` (default: a private temp directory,
removed afterwards) seeds a workspace from this project's fixtures and
runs:

- **Session A**: `init` (seeding the corpus), `import` of the field
  guide, `index`, `status`; then writes `session-handoff.md` in the
  canonical handoff format.
- **Session boundary**: nothing carries over except the disk.
- **Session B**: `status`, `ask` (the pinned continuity question),
  `show` of the imported document; B first parses the handoff and the
  report records its section count.

**The process boundary is a contract, not an implementation detail**:
every step in both sessions is executed by spawning this track's own CLI
as a child process (Python: `sys.executable` plus this file; TypeScript:
the repository's `tsx` binary plus this file), each with the workspace
as its working directory. In-process function calls are forbidden for
continuity steps; a fresh interpreter per step is what makes "session B
resumed from repository state alone" a measured fact rather than a claim.

The report pins, per step, the canonical command, exit code, and compact
observed output, and derives: `status_matches_session_a` (B's fresh
process printed byte-identical status), `state`, `documents`,
`answer_grounded` (B's answer carries citations), and the overall
`resumed` verdict, which is also the exit code. The full report is
byte-identical across tracks; `expected/continuity.json` pins it.

## Seeded defects (fixtures/workspaces/workspace-stale)

Carried unchanged from project 02, caught by the same checks:

| # | Defect | Observable symptom | Caught by |
| --- | --- | --- | --- |
| 1 | `AGENTS.md` routes to `docs/IMPORTING.md`, which does not exist | `unresolved router target(s): docs/IMPORTING.md` | `router-targets` |
| 2 | handoff lacks the `Next best step` section | `missing required section(s): Next best step` | `session-handoff` |
| 3 | feature `document-import` is `passing` with no evidence | `passing without evidence: document-import` | `feature-evidence` |

## Starter state

The starter must keep passing the carried v2 behaviors (list, the
workspace doctor cases, the error exits, and `show`, which spreads
recorded entries as-is and therefore forwards the fixture's v3 `metadata`
untouched, a small forward-compatibility lesson) and fail every v3
delta case: `index`, `status`, and `continuity` are usage errors (exit 2)
in v2; `init` and `import` record entries without the `metadata` field
(the init artifact check and the import stdout fail); v2 `ask` answers
without an index where v3 must refuse, and cites lines where v3 must cite
chunks; the v2 self-check lacks the `status` field. `verify.sh` asserts
the starter stage FAILS conformance.

## Cases

`cases.json` covers: init recording v3 metadata (artifact-checked), the
list, the missing-dir exit, import extracting metadata (with the copied
document byte-checked), the detail view with metadata, the unknown-id
exit, `index` building chunks (artifact-checked against the committed
indexed fixture, which proves the two fixture directories are one
`kb index` apart), index idempotency (everything `up-to-date`), status on
an unindexed and an indexed directory, the ask refusal before indexing,
the chunk-grounded answer, the self-check with index state, the ready and
stale workspaces, the full two-session continuity proof, and a usage
error.

## Tests

`solution/python/tests/` (pytest) and `solution/typescript/tests/`
(vitest) cover the chunking rule (packing, the oversized-paragraph case,
determinism), metadata extraction, staleness detection after a document
edit, the ask refusal, chunk-grounded citations, the continuity proof's
process boundary (asserting the report's steps ran as child processes
with session B re-deriving state from disk), the dogfood check
(`harness/` passes `workspace-check`), and the independent evidence
check: every evidence command in `harness/feature_list.json` executed
through the real CLI as a subprocess and compared to the recorded
`observed` string. `make verify` runs both suites.
