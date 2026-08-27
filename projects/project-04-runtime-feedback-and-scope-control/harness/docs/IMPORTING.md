# Importing, project 04 workspace

The focused doc the router points at when the task touches import or the
metadata index.

## Flow

1. `kb import --data-dir kb-data FILE...` checks the file is readable
   (exit 2 if not) and the workspace is initialized (exit 1 if not).
2. The document id is the filename without its extension. An id already
   present in the index is reported under `skipped` with reason
   `already-imported`; the file is not copied twice.
3. Otherwise the file is copied into `kb-data/documents/`, an entry is
   appended, and the index is rewritten sorted by id.

## Invariants

- Title comes from the first `#` heading line, else the filename.
- `lines` counts content lines with trailing newlines stripped.
- The index is valid JSON at every step; there is no partial-write state
  a fresh session could misread.
- Import is the only way a document acquires origin `imported`; `init`
  seeding is the only way it acquires `seeded`.
- Version 3 note: an import leaves the chunk index behind; `kb status`
  reports the workspace `partial` until `kb index` runs again.
