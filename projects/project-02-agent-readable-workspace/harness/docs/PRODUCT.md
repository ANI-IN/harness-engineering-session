# Product, project 02 working copy

kb v2 keeps the four project 01 features and adds three: everything is
re-verified against version 2, nothing is "carried over".

## The seven features of this milestone

1. **Data directory**: `kb init` creates the layout, seeds documents, and
   records every seeded document in the metadata index.
2. **Document list**: `kb list` reports each known document with its
   origin, from the index alone.
3. **Question answering**: unchanged citation contract from project 01.
4. **App starts**: the self-check now also proves the detail endpoint.
5. **Document import**: `kb import` copies files in and records them; a
   file whose id is already known is skipped, not duplicated.
6. **Document detail**: `kb show` returns metadata plus full content,
   also served at `/documents/{id}`.
7. **Metadata persistence**: a fresh process lists the imported document
   from the index alone; nothing depends on process memory.

## Non-goals for this milestone

Chunking, index structures beyond the metadata index, deletion, and model
answer generation are later projects. The citation and metadata contracts
are fixed now so those can arrive without breaking callers.
