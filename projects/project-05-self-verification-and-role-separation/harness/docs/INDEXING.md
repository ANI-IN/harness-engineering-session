# Indexing, project 05 workspace

The focused doc the router points at when the task touches chunking, the
index state, or grounded answers.

## Chunking

`kb index` splits every known document into paragraphs (blank-line
separated) and packs them greedily into chunks of at most 500 characters,
joined with one blank line; an oversized paragraph stays whole. Chunks
live in `index/chunks.json` beside a per-document content sha256.

## State

`kb status` computes everything from disk: `empty` (nothing indexed),
`partial` (some documents indexed), `ready` (all indexed and current),
`stale` (a document changed after indexing; the report names it). Re-run
`kb index` to converge; it re-chunks only what the sha256 says changed.

## Grounded answers

`kb ask` refuses unless the state is `ready` (exit 1, pinned error), then
scores chunks by distinct question-token overlap and cites at most two as
`document`, `title`, `chunk`, `excerpt`, `score`. The composer that turns
citations into prose is the model seam; a real model must keep both the
citation contract and the refusal.

## Continuity

`kb continuity` proves a fresh session resumes from disk alone: two
sessions of real child processes with a handoff written at the boundary.
If your change breaks resume, the continuity report says which step.
