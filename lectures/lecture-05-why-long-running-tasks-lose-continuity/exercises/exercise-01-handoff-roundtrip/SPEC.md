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

Both directions run, each with one naive mistake:

| Direction | Its mistake | Divergence it produces |
| --- | --- | --- |
| parse | keeps the "- " bullet prefix on items | the first item value carries the prefix |
| render | omits the blank line after each heading | `line 4: '- ...' != ''` |

Verification fails first at:

```text
diverges at $.sections[0].items[0]: '- `./verify.sh import-notes`: exit 0' != '`./verify.sh import-notes`: exit 0'
```

The starter must run cleanly and fail only by producing these wrong
values.

## Expected output

- `parse` case: `fixtures/handoff.md` → `expected/handoff.json` (kind json).
- `render` case: `fixtures/handoff.json` → `expected/handoff.md` (kind
  text; byte-equal to `fixtures/handoff.md`, which is the round-trip law
  made into a committed check).
