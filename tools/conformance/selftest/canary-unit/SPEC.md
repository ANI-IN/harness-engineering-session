# SPEC: canary

A small program whose two implementations intentionally produce cosmetically
different raw output, so the conformance pipeline is exercised for real on
every run. Each divergence class below is one that real curriculum units will
eventually hit; the canary hits them first. This unit is tooling self-test,
not curriculum.

## CLI surface

```text
main <input-file> [--out <file>]
```

Reads the JSON file at `<input-file>`:

```json
{
  "label": "<string, may contain non-ASCII>",
  "factors": [<number>, <number>],
  "segments": ["<string>", "..."],
  "tags": [],
  "meta": {},
  "parent": null,
  "notes_file": "<path to a text file; may use LF or CRLF line endings>"
}
```

Writes a JSON report with exactly these fields:

| Field | Value |
| --- | --- |
| `label` | `label` from the input, unchanged (non-ASCII preserved) |
| `sum` | `factors[0] + factors[1]`, IEEE 754 double addition (0.1 + 0.2 must serialize as 0.30000000000000004 in both tracks) |
| `path` | the `segments` joined with the platform path joiner |
| `segment_count` | number of `segments` |
| `tags` | echoed empty list |
| `meta` | echoed empty object |
| `parent` | echoed null |
| `whole` | `whole_factor` echoed as a number (see divergence table) |
| `notes` | statistics over `notes_file`, see below |

`notes` is nested more than two levels deep by design:

```json
"notes": {
  "lines": <count of lines containing non-whitespace>,
  "words": {
    "total": <count of whitespace-separated words>,
    "longest": { "text": "<first longest word>", "length": <its length> }
  }
}
```

Without `--out`, the report goes to stdout. With `--out <file>`, the report
is written to `<file>` (creating parent directories) and stdout carries
exactly one line: `wrote <file>`.

## Semantic rules (these bind every unit in this repository)

1. **Line endings in inputs**: LF and CRLF are both line separators; a
   trailing newline does not create an extra line. The output normalizer
   applies to outputs only; handling input line endings is the
   implementation's job (Python text mode translates automatically;
   TypeScript must split on `/\r?\n/`).
2. **String length**: counted in Unicode code points. `mega🚀rocket` has
   length 11. JavaScript's `String.length` counts UTF-16 code units and
   would report 12; TypeScript implementations must use code-point
   iteration (`[...str].length`).
3. **stderr is diagnostics only**: never asserted, never compared. The two
   tracks deliberately write different multi-line stderr here to prove the
   contract lives on stdout, exit codes, and written files.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 2 | input file missing/unreadable, or bad usage; stdout empty |

## Deliberate cosmetic divergence (absorbed by the normalizer)

| Class | Python emits | TypeScript emits |
| --- | --- | --- |
| Key order | `label, sum, path, ...` insertion order | reverse insertion order |
| Indentation | 2-space | 4-space |
| Trailing whitespace | none | two trailing spaces per line |
| Non-ASCII in JSON (stdout and written file) | `\uXXXX` escapes (`ensure_ascii=True`) | literal UTF-8 (`café`, `☕`, `🚀`) |
| Integral numbers (`whole` field) | float `2.0` | integer `2` (JS has one number type) |
| stderr wording | `canary: ...` (2 lines) | `[canary] ...` (3 lines) |

Raw outputs therefore always differ; after normalization (canonical JSON
with sorted keys, literal UTF-8, stripped trailing whitespace) they must be
byte-identical to each other and to `expected/`. If this unit fails
conformance, either an implementation or the normalizer is broken.

## Expected output

`expected/basic.json` is the grading authority for the `basic` case and for
the artifact written by `report-to-subdirectory`;
`expected/report-stdout.txt` pins that case's stdout.
