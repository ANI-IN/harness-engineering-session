# Product, project 03 workspace

kb v3 keeps the seven project 02 features and adds four: everything is
re-verified against version 3, nothing is "carried over".

## The eleven features of this milestone

1. **Data directory**: `kb init` creates the layout, seeds documents, and
   records them, now with extracted metadata.
2. **Document list**: from the index alone, with origins.
3. **Question answering**: grounded answers with the citation contract,
   now chunk-based.
4. **App starts**: the self-check proves health, list, detail, and index
   state end to end.
5. **Document import**: copies files in, records them with metadata,
   skips known ids.
6. **Document detail**: entry plus full content, CLI and HTTP.
7. **Metadata persistence**: a fresh process lists everything from the
   index alone.
8. **Document chunking**: `kb index` builds the deterministic chunk index
   with per-document sha256.
9. **Index status**: `kb status` reports empty, partial, ready, or stale
   from disk only.
10. **Metadata extraction**: every entry carries chars, words, and
    paragraph counts extracted from content.
11. **Session continuity**: `kb continuity` proves a fresh process chain
    resumes from repository state alone.

## Non-goals for this milestone

Structured logging, architecture guards, scope control, and model answer
generation are later projects. The chunk and citation contracts are fixed
now so those can arrive without breaking callers.
