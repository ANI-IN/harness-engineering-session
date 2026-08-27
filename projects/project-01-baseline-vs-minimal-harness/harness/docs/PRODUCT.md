# Product, project 01 working copy

kb is a local knowledge base: it holds a small set of text and markdown
documents and answers questions about them with citations.

## The four features of this milestone

1. **Data directory**: `kb init` creates the storage layout and seeds the
   sample documents. Everything the tool knows lives under that directory;
   deleting it is a full reset.
2. **Document list**: `kb list` reports every stored document with its
   identifier, title, filename, and line count.
3. **Question answering**: `kb ask` returns an answer grounded in at most
   two cited lines. When nothing matches, it says so; it never invents
   prose.
4. **App starts**: `kb serve --self-check` proves the HTTP server binds,
   answers `/health` and `/documents`, and shuts down cleanly.

## Non-goals for this milestone

Importing new documents, indexing structures, and answer generation by a
real model are later projects. The citation contract is fixed now so those
can arrive without breaking callers.
