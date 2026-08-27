# SPEC: instruction-walk

Demonstrates what an instruction architecture costs, behaviorally first:
`walk` sends a budgeted deterministic reader through one instruction tree
for one task and reports, with its exit code, whether every hard
constraint was actually read. `stats` supplies the supporting numbers
(per-task signal-to-noise, constraint zones). Both tracks read the same
trees and must emit the same reports; `expected/` is the grading
authority.

## CLI surface

```text
main walk <tree-dir> <tasks.json> <task-id> --budget N
main stats <trees-dir> <tasks.json>
```

A tree is an `AGENTS.md` entry file plus optional `docs/*.md` topic
files, where `docs/<topic>.md` covers topic `<topic>`. `<tasks.json>` is
`{"tasks": [{"id", "topics": ["..."]}]}`. `stats` analyzes every tree
subdirectory of `<trees-dir>` in name order.

## Instruction format

An instruction line matches `- [<topic>] <text>`, with hard constraints
marked by a `!` suffix on the topic: `- [security!] <text>`. Everything
else in a file is prose and counts only toward line totals.

## The reader (the demo, pinned)

The reader models a session with a context budget of N lines:

1. It reads `AGENTS.md` first, top-down, consuming budget line by line;
   when the budget runs out mid-file, the remaining lines are unread.
2. For each of the task's topics, in task order: it follows the route to
   `docs/<topic>.md` only when that file exists AND some line it has
   **actually read** in the entry file mentions `docs/<topic>.md`. A
   route buried below the budget line is as lost as a rule. Routed files
   are read the same way while budget remains.
3. Every hard constraint in the tree (entry and all topic files) is then
   judged: `read` is true exactly when its file was visited and its line
   number is within the lines read of that file.

Output:

```json
{
  "tree": "...", "task": "...", "budget": 0,
  "files_visited": [ { "file": "...", "lines_read": 0, "lines_total": 0 } ],
  "lines_spent": 0,
  "hard_constraints": [ { "text": "...", "file": "...", "line": 0, "read": false } ],
  "missed": 0
}
```

**The exit code is the behavioral verdict**: 0 when every hard constraint
was read, 1 when any was missed. On the committed fixtures, budget 24
makes the monolith miss its line-28 constraint while the router reads
everything relevant in 19 lines; budget 60 recovers the monolith, which
pins the claim precisely: the failure is the architecture's interaction
with a finite budget, not the file's content.

## stats (supporting evidence, pinned)

For each task: the entry file is always loaded; `docs/<topic>.md` is
additionally loaded for each of the task's topics when that file exists.
Then:

- `loaded_lines` = total line count of loaded files (prose included:
  loading a file costs its whole length).
- `relevant_lines` = instruction lines among loaded files whose topic is
  in the task's topics.
- `snr` = `relevant_lines / loaded_lines` (IEEE 754 division; both tracks
  must serialize identically).

`mean_snr` averages the per-task SNR values in task order, accumulating
**left to right with plain addition**. This is pinned because the two
languages' idioms genuinely differ: Python's built-in `sum()` applies
Neumaier-compensated summation to floats (3.12+), producing a result one
ulp away from JavaScript's naive `reduce` fold on this very fixture.
Implementations must use the naive fold in both tracks.

A hard constraint's zone is computed by thirds of its own file
(`(line-1)*3 // total_lines` → top, middle, bottom). It is **buried**
when its zone is `middle` and its file is longer than 20 lines: short
files have no middle to get lost in. The stats report shape is:

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
| 0 | `walk`: every hard constraint read; `stats`: report emitted |
| 1 | `walk`: at least one hard constraint missed (the demo's failure) |
| 2 | usage error, missing tree/trees dir, unknown task, unreadable tasks file; stdout empty |

## Fixtures

`fixtures/trees/monolith` and `fixtures/trees/router` carry the same
rules in two architectures, including the identical `security!`
constraint at monolith line 28 (zone middle of 45 lines) and router entry
line 7 (a 15-line file); `fixtures/tasks.json` holds five tasks. The
pinned walk reports carry the behavioral outcome; the pinned stats report
shows the router roughly doubling mean SNR and reducing buried hard
constraints from 1 to 0. The exact figures live in `expected/` and
nowhere else.
