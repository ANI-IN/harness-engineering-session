# Field guide to importing

Importing is the moment a document becomes part of the knowledge base
instead of a file that happens to sit nearby. The import command copies
the file into the documents folder and, just as important, records it in
the metadata index.

## Why the metadata index exists

A directory scan tells you what files exist; the metadata index tells you
what the system knows. Listing reads the index, never the directory, so
the answer to "what is in the knowledge base" comes from recorded state
rather than rediscovery. That is the system of record principle applied
to a single JSON file.

## What survives a restart

Everything: the copied document, its index entry, its title and line
count. A fresh process lists the imported document without re-reading the
original source, which is the whole point of persistence.
