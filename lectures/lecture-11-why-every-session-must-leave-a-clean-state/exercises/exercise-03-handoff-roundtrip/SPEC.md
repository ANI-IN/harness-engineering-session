# SPEC: exercise-01 handoff-roundtrip

A handoff is only trustworthy if it is machine-checkable, and it is only
machine-checkable if parsing and rendering round-trip exactly. This
exercise implements both directions over the canonical handoff format.

## CLI surface

```text
main parse <handoff.md>     # markdown in, JSON out
main render <handoff.json>  # JSON in, markdown out
```

## Canonical handoff format

One `# <title>` line, then sections: `## <heading>`, a blank line, then
one `- <item>` line per item. Sections are separated by exactly one blank
line before each heading; the file ends with a single newline. Items are
stored WITHOUT the "- " bullet prefix (the marker is syntax, not content).

Parsed shape:

```json
{ "title": "Session handoff", "sections": [ { "heading": "...", "items": ["..."] } ] }
```

**Round-trip law**: `render(parse(x)) == x` byte-identically for canonical
input; the committed fixture and expected files enforce it (the render
case's expected markdown equals the parse case's fixture, byte for byte).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | output emitted |
| 1 | `render` given malformed JSON; stdout empty |
| 2 | usage error or unreadable input; stdout empty |

## Starter state (the intended failure)

Both directions run, each with one naive mistake that loses handoff
meaning rather than handoff formatting:

| Direction | Its mistake | What the round trip loses |
| --- | --- | --- |
| parse | keeps only a whitelist of "core" section headings | the `Broken or unverified` section, silently |
| render | sorts sections alphabetically | the document's priority order |

Verification fails first at:

```text
diverges at $.sections[2].heading: 'Next best step' != 'Broken or unverified'
```

The dropped section is the one that tells the next session what is known
to be broken, which is precisely the content whose loss costs a re-derive.
The starter must run cleanly and fail only by producing these wrong
values.

## Expected output

- `parse` case: `fixtures/handoff.md` → `expected/handoff.json` (kind json).
- `render` case: `fixtures/handoff.json` → `expected/handoff.md` (kind
  text; byte-equal to `fixtures/handoff.md`, which is the round-trip law
  made into a committed check).
