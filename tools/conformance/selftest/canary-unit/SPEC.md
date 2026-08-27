# SPEC: canary

A trivial program whose two implementations intentionally produce
cosmetically different raw output, so that the conformance pipeline is
exercised for real on every run. This unit is tooling self-test, not
curriculum.

## CLI surface

```text
main <input-file>
```

Reads the JSON file at `<input-file>`:

```json
{ "label": "<string>", "factors": [<number>, <number>], "segments": ["<string>", "..."] }
```

Writes to stdout a JSON object with exactly these fields:

| Field | Value |
| --- | --- |
| `label` | `label` from the input, unchanged |
| `sum` | `factors[0] + factors[1]`, IEEE 754 double addition (0.1 + 0.2 must serialize as 0.30000000000000004 in both tracks) |
| `path` | the `segments` joined with the platform path joiner |
| `segment_count` | number of `segments` |

Nothing else is written to stdout. Diagnostics go to stderr.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success, JSON written to stdout |
| 2 | input file missing or unreadable; stdout empty |

## Deliberate cosmetic divergence

The Python track emits keys in insertion order `label, sum, path,
segment_count` with 2-space indent. The TypeScript track emits the reverse
key order with 4-space indent and two trailing spaces on every line. Raw
outputs therefore always differ; the conformance normalizer (canonical JSON,
stripped trailing whitespace) must make them identical. If this unit fails
conformance, either an implementation or the normalizer is broken.

## Expected output

`expected/basic.json` is the grading authority for the `basic` case
(compared with normalization kind `json`).
