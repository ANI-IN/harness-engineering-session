# Architecture, project 05 workspace

Unchanged layering: CLI and loopback HTTP server as surfaces, core
functions, plain-file storage. Version 3 adds a derived-state layer and a
rule about it.

## State files

| File | Role | Writer |
| --- | --- | --- |
| `index/documents-meta.json` | system of record: what the kb knows | `init`, `import` |
| `index/chunks.json` | derived state: chunked text plus per-document sha256 | `index` |

Derived state is never trusted blindly: `kb status` recomputes currency
from the sha256s on every call, and `kb ask` refuses unless the state is
`ready`. Deleting `index/chunks.json` loses nothing; `kb index` rebuilds
it from the system of record.

## Surfaces

| Command | HTTP | Notes |
| --- | --- | --- |
| `kb list` | `GET /documents` | from the metadata index |
| `kb show ID` | `GET /documents/{id}` | entry (with metadata) plus content |
| `kb status` | `GET /status` | index state from disk, incl. `corrupt` |
| `kb logs`, `kb guard` | none | observability surfaces; read-only |
| `kb ask` | `GET /ask?q=` | chunk-grounded; refuses (exit 1 / 503) unless ready |
| `kb index`, `kb import` | none | writes go through the CLI only; the server answers non-GET with 405 |
| `kb continuity` | none | study apparatus; spawns child CLI processes |

## The rules are executable

`kb guard` runs these rules as behavior in a sandbox: the server answers
non-GET with 405 and must leave the data directory bit-identical; an
import must write only inside the data directory; deleting
`index/chunks.json` must lose nothing (`kb index` restores `ready`).
A rule the guard cannot check does not belong on this page.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success; workspace ready; continuity resumed |
| 1 | missing dir/index, unknown id, index not ready, not resumed |
| 2 | usage error or unreadable input |
