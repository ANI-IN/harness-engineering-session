# Architecture, project 02 workspace

Unchanged layering from project 01: CLI and loopback HTTP server as
surfaces, core functions, plain-file storage. What version 2 adds is a
rule about truth, not a new layer.

## The metadata index

`index/documents-meta.json` is the system of record. Every document the
knowledge base knows has an entry (`id`, `title`, `filename`, `lines`,
`origin`), the array stays sorted by `id`, and `init`, `import` are the
only writers. `list`, `ask`, `show`, and the server read the index and
never scan the documents directory; a scan answers "what files exist",
which is not the question.

## Surfaces

| Command | HTTP | Notes |
| --- | --- | --- |
| `kb list` | `GET /documents` | index order |
| `kb show ID` | `GET /documents/{id}` | entry plus full content; 404/exit 1 unknown |
| `kb ask` | `GET /ask?q=` | retrieval semantics identical to project 01 |
| `kb import FILE...` | none | writes go through the CLI only |
| health | `GET /health` | document count from the index |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success; workspace ready |
| 1 | uninitialized, index missing, unknown id, workspace not ready |
| 2 | usage error or unreadable input |
