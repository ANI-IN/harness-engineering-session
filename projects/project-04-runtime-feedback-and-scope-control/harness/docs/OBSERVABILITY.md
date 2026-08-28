# Observability, project 04 workspace

The focused doc the router points at when the task touches logs, the
guard, or corruption recovery.

## Logs

Mutating commands (and `ask`) append structured events to
`log/events.jsonl` under the data directory; `kb logs --data-dir kb-data
--level WARN` is the first move when behavior surprises you. Entries
carry a sequence number instead of a timestamp: this module's
determinism rule; a real deployment adds timestamps at that seam.

## The failure this project teaches

A past buggy chunker can leave empty chunks whose recorded sha still
matches the document. The sha-gated `kb index` therefore skips them
forever: the state looks done and is wrong. `kb status` detects it
(state `corrupt`, naming documents), a refused `kb ask` logs it at WARN,
and `kb index --rebuild` recovers it. Diagnosis order: status, then
logs, then rebuild; never hand-edit `chunks.json`.

## The guard

`kb guard --data-dir kb-data` executes the architecture rules in a
sandbox copy: the server refuses writes (405) and leaves the data
directory bit-identical; an import writes only inside the data
directory; deleting the chunk index loses nothing. Run it before calling
architecture-touching work done.
