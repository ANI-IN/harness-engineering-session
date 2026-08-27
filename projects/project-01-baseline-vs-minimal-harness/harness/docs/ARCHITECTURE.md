# Architecture, project 01 working copy

The kb tool is a single program with two entry surfaces and one storage
layer.

## Layers

| Layer | Owns | Never does |
| --- | --- | --- |
| CLI | argument parsing, exit codes, stdout/stderr discipline | business logic of its own |
| HTTP server | loopback endpoints `/health`, `/documents`, `/ask` | logic the CLI cannot reach |
| Core functions | documents, retrieval, answer composition | I/O outside the data directory |
| Storage | the data directory: `documents/`, `index/` | writes anywhere else |

Both surfaces call the same core functions, so behavior cannot depend on
which surface invoked it. The server binds `127.0.0.1` only; nothing
leaves the machine.

## Determinism

Retrieval and answer composition are pure functions of the document set
and the question. The composer is the seam where a language model would
sit; replacing it must not change the citation contract (document, title,
line, excerpt, score).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | data directory not initialized |
| 2 | usage error or unreadable input |
