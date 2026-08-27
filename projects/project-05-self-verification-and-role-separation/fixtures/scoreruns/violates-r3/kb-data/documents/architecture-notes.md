# Architecture notes

The kb tool is one program with two faces: a command line interface for
scripted use and a small local HTTP server for interactive use. Both faces
call the same functions, so behavior never depends on the invoking face.

## Storage

All state lives in a data directory that the init command creates. Inside
it, a documents folder holds the imported text and markdown files, and an
index folder is reserved for derived structures. Nothing is stored outside
the data directory, and deleting it returns the tool to a clean state.

## Answering

Answers carry citations that name the source document and the exact line
they quote. An answer without a citation is treated as a bug, not a
feature. The composer that turns citations into prose is deliberately
simple; it marks the seam where a language model would sit in a real
assistant.

## Boundaries

The HTTP server binds to the loopback interface only and talks to the same
storage layer as the command line. No network calls leave the machine.
