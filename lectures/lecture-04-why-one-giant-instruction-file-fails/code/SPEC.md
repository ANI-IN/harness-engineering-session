# SPEC: instruction-stats

Measures what an instruction architecture costs: per-task signal-to-noise
under a fixed loading rule, and the zone of every hard constraint. Both
tracks read the same trees and must emit the same report; `expected/` is
the grading authority.

## CLI surface

```text
main <trees-dir> <tasks.json>
```

`<trees-dir>` contains one subdirectory per instruction tree, analyzed in
name order. A tree is an `AGENTS.md` entry file plus optional `docs/*.md`
topic files, where `docs/<topic>.md` covers topic `<topic>`.

`<tasks.json>` is `{"tasks": [{"id", "topics": ["..."]}]}`.

## Instruction format

An instruction line matches `- [<topic>] <text>`, with hard constraints
marked by a `!` suffix on the topic: `- [security!] <text>`. Everything
else in a file is prose and counts only toward line totals.

## Loading rule (the simulated agent)

For each task: the entry file is always loaded; `docs/<topic>.md` is
additionally loaded for each of the task's topics when that file exists.
Then:

- `loaded_lines` = total line count of loaded files (prose included:
  loading a file costs its whole length).
- `relevant_lines` = instruction lines among loaded files whose topic is in
  the task's topics.
- `snr` = `relevant_lines / loaded_lines` (IEEE 754 division; both tracks
  must serialize identically).

`mean_snr` averages the per-task SNR values in task order, accumulating
**left to right with plain addition**. This is pinned because the two
languages' idioms genuinely differ: Python's built-in `sum()` applies
Neumaier-compensated summation to floats (3.12+), producing a result one
ulp away from JavaScript's naive `reduce` fold on this very fixture.
Implementations must use the naive fold in both tracks.

## Zones and burial

A hard constraint's zone is computed by thirds of its own file
(`(line-1)*3 // total_lines` → top, middle, bottom). It is **buried** when
its zone is `middle` and its file is longer than 20 lines: short files
have no middle to get lost in, which is why the router's entry-file hard
constraint is `middle` but not buried, while the same rule at the same
relative depth of the 45-line monolith is.

## Output

```json
{
  "trees": [
    {
      "name": "...", "files": 0, "total_lines": 0, "entry_lines": 0,
      "tasks": [ { "id": "...", "loaded_lines": 0, "relevant_lines": 0, "snr": 0 } ],
      "mean_snr": 0,
      "hard_constraints": [ { "text": "...", "file": "...", "line": 0, "zone": "...", "buried": false } ],
      "buried_hard_constraints": 0
    }
  ],
  "comparison": { "mean_snr": {}, "buried_hard_constraints": {} }
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error, missing trees dir, or unreadable tasks file; stdout empty |

## Fixtures

`fixtures/trees/monolith` and `fixtures/trees/router` carry the same rules
in two architectures; `fixtures/tasks.json` holds five tasks. The pinned
report shows the router roughly doubling mean SNR and reducing buried hard
constraints from 1 to 0; the exact figures live in
`expected/stats-report.json` and nowhere else.
