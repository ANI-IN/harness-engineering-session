# Product, project 05 workspace

kb v4 keeps the eleven project 03 features and adds four: everything is
re-verified against version 4, nothing is "carried over".

## The seventeen features of this milestone

1. **Data directory**: `kb init` creates the layout, seeds documents,
   records metadata, and writes its first log event.
2. **Document list**: from the index alone, with origins.
3. **Question answering**: chunk-grounded with the refusal rule; answers
   and refusals both leave log events.
4. **App starts**: the self-check proves health, list, detail, and index
   state end to end.
5. **Document import**: copies files in, records them with metadata,
   skips known ids, logs what it did.
6. **Document detail**: entry plus full content, CLI and HTTP.
7. **Metadata persistence**: a fresh process lists everything from the
   index alone.
8. **Document chunking**: `kb index` builds the deterministic chunk index
   with per-document sha256.
9. **Index status**: `kb status` reports empty, partial, ready, stale, or
   corrupt, from disk only.
10. **Metadata extraction**: every entry carries chars, words, and
    paragraph counts.
11. **Session continuity**: `kb continuity` proves a fresh process chain
    resumes from disk state alone.
12. **Structured logging**: mutating commands append sequence-numbered
    events; `kb logs` filters by level and event.
13. **Corruption recovery**: `kb index --rebuild` re-chunks everything
    the sha gate would skip, healing empty-chunk corruption.
14. **Architecture guard**: `kb guard` executes the layer rules
    (read-only server, storage containment, disposable derived state).
15. **WIP limit**: the workspace doctor fails a workspace holding more
    than one feature in-progress.
16. **Document delete**: `kb delete` removes the file, the index entry,
    and the chunk record, and logs it; `kb status` names any orphan a
    half-done delete leaves, and `kb index` reconciles it away.
17. **Verified-work ladder**: `kb ladder` replays the scripted work item
    under three role configurations and exits 0 only when the rubric
    scores strictly climb.

## Non-goals for this milestone

The observable-harness capstone composes what projects 01-05 built.
Contracts are frozen within this milestone; the surface is pre-1.0
across projects, and any break a successor makes is declared in its
SPEC's delta table, never silent.
