# SPEC: exercise-01 carried-loop-state

The lecture demo runs a loop whose maker chooses each round's step from the
rounds recorded in `loop-state.json`
([../../code/SPEC.md](../../code/SPEC.md)). This exercise is that memory on
its own. A loop directory arrives with rounds already behind it, and the
runner takes the next ones: it reads the carried state to see what has been
attempted, attempts the first criterion the state does not name, and writes
the attempt back before the next round reads it. A runner that gets any of
those three moves wrong is not a loop, it is that many independent retries.

## CLI surface

```text
main <loop-dir>
```

A loop directory carries three things, all committed:

```text
<loop-dir>/
  goal.json         # the goal, its criteria, and the round budget
  loop-state.json   # the loop's memory of the rounds already run
  workspace/        # the files the criteria are checked against
```

`workspace/` is read once and edited in memory, and `loop-state.json` is
read once and carried forward in memory. Nothing under `<loop-dir>` is
written, so the committed fixtures are unchanged by any number of runs and
every run is idempotent. The in-memory map is the seam where a live harness
would edit real files and write the state back between rounds
([deterministic fake agent](../../../../docs/glossary.md#core-model)).

## goal.json

```json
{
  "loop": "report-export",
  "goal": "...",
  "max_rounds": 3,
  "criteria": [ { "id", "check": { "kind", ... }, "step": { "path", "line" } } ]
}
```

A criterion is a pair: the `check` that decides whether it is met, and the
`step` the runner takes when it attempts it. Nothing requires the step to
satisfy the check; `fixtures/loop-resumed-blocked` is a goal where one does
not.

`max_rounds` counts rounds over the whole loop, including the ones already
recorded in the state, so a resumed loop has fewer rounds left than a fresh
one with the same budget. `kind` selects one of two executable probes, the
deterministic stand-in for running the real verification command. Both are
carried over unchanged from the lecture demo's contract, detail strings
included:

| kind | fields | passes when | detail strings |
| --- | --- | --- | --- |
| `key-declared-once` | `path`, `key` | exactly one line starts `<key>=` | `<path> declares <key> once` / `<path> has no <key>= line` / `<path> declares <key> N times` / `<path> missing` |
| `file-has-line` | `path`, `prefix` | some line starts with the prefix | `<path> has a line starting with <prefix>` / `<path> has no line starting with <prefix>` / `<path> missing` |

`key-declared-once` fails on a duplicate, which is what makes re-attempting
a criterion worse than wasteful: a second `writer=csv` line un-satisfies a
criterion that was already met.

Both tracks treat LF and CRLF alike as line separators (see
docs/conventions.md, semantic rules).

## loop-state.json (the carried memory)

```json
{
  "loop": "report-export",
  "rounds_done": 2,
  "attempted": [
    { "round": 1, "criterion": "writer-implemented", "outcome": "met" },
    { "round": 2, "criterion": "test-case-present", "outcome": "unmet" }
  ]
}
```

Every entry in `attempted` records a round that ran to completion, and
`rounds_done` equals the number of entries and the number of the last round
that ran. `outcome` is `met` or `unmet`: an attempt whose step failed to
satisfy its own criterion is still an attempt, and the loop does not take
that step again.

## The round

The runner repeats this until one of the three stop conditions holds:

1. **Budget.** When `rounds_done` has reached `max_rounds`, no round is
   started.
2. **Read the memory.** `attempted` yields the criterion ids this loop has
   already tried, in order.
3. **Choose.** The round attempts the first criterion in goal order whose
   id is not among them. When the memory names every criterion, no round is
   started and the loop stops.
4. **Act.** The chosen criterion's `step` is applied (the line is appended,
   or the file is created holding it), then that one criterion's check is
   re-run: `criterion_met_after` is `met` or `unmet`, with the check's
   `detail`.
5. **Write the memory.** The round is appended to `attempted` and
   `rounds_done` becomes this round's number, which is `rounds_done + 1`.
   This happens before the next round reads the state, so a criterion is
   attempted at most once.
6. **Stop on the goal.** Every criterion is graded against the workspace.
   When nothing is unmet the loop stops there.

## Output

```json
{
  "loop", "goal", "max_rounds",
  "rounds": [
    {
      "round", "memory_read", "chosen_criterion", "step_taken",
      "criterion_met_after", "detail", "unmet_after"
    }
  ],
  "state_written": { "loop", "rounds_done", "attempted" },
  "stop": { "after_round", "reason" },
  "unmet": [ "..." ],
  "verdict": "goal-reached" | "budget-exhausted" | "steps-exhausted"
}
```

`memory_read` is the list of criterion ids the round read from the carried
state before choosing, so the report shows what the loop knew as well as
what it did. `state_written` is the state the next session would resume
from, printed rather than written to disk. `unmet` is re-graded from the
workspace after the loop stops, in goal order.

| Stop condition | `after_round` | `reason` |
| --- | --- | --- |
| goal met | this round's number | `every criterion of the goal is met after round <n>` |
| budget | `rounds_done` | `the loop has run <n> of its <max> rounds, so it cannot start another` |
| nothing left to attempt | `rounds_done` | `the carried state names every criterion of the goal, so there is no step left to take` |

`verdict` is `goal-reached` when nothing is unmet, `budget-exhausted` when
the budget ended a loop with work remaining, and `steps-exhausted` when the
loop ran out of untried criteria with work remaining.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `goal-reached`: every criterion of the goal is met |
| 1 | `budget-exhausted` or `steps-exhausted`: the loop stopped with work remaining |
| 2 | usage error, or a `<loop-dir>` without `goal.json` and `loop-state.json`; stdout empty |

## Fixtures and seeded symptoms

All three loop directories share a workspace shape: `src/report.txt`,
`config/app.conf`, and a `tests/` directory that exists only once
`test-case-present` has been satisfied. They differ in how much of the loop
has already run.

- `loop-resumed-blocked` (the trap): two rounds behind it, budget 3, so one
  round is left. The state records round 2 as an attempt at
  `test-case-present` whose `outcome` is `unmet`: that criterion's step
  appends to `src/report.txt` while its check reads
  `tests/report-test.txt`, a defect seeded in the goal exactly as the
  lecture demo's `loop-wrong-target` seeds it. The observable symptom is
  that no round can ever satisfy `test-case-present`. A runner that reads
  the whole memory spends its last round on `export-dir-wired` and ends
  `budget-exhausted` with one criterion unmet; a runner that reads one
  entry too few spends it re-attempting the blocked criterion and ends with
  two. Both exit 1, so only the decisions separate them.
- `loop-resumed-clean`: two rounds behind it, budget 3, both earlier
  attempts `met`. The last round creates the test case and the goal is
  reached. Re-attempting `export-dir-wired` here appends a second
  `export_dir=` line, and `key-declared-once` then reports
  `config/app.conf declares export_dir 2 times`, so a round spent on
  already-finished work also undoes it.
- `loop-fresh-start`: an empty memory (`rounds_done` 0) and a budget of 4.
  Three rounds reach the goal. A fresh loop is where a broken memory is
  least visible on round 1, because there is nothing yet to remember.

## Starter state (the intended failure)

The starter's `attempted_criteria` (`attemptedCriteria` in TypeScript)
reads `state["attempted"][: state["rounds_done"] - 1]`, on the reasoning
that `rounds_done` is the number of the last round that ran and therefore
its index. It is an off-by-one over the carried history: the most recent
attempt is dropped from the memory on every round, so the loop re-attempts
the criterion it worked on last. Everything else is already right: the
budget rule, the check engine, the step application, the round numbering,
`state_written`, the three stop reasons, and the verdict mapping. The
starter runs cleanly on every fixture and fails only by choosing the wrong
criterion.

Verification fails first on the `resumed-blocked-attempt` case at
`$.rounds[0].chosen_criterion: 'test-case-present' != 'export-dir-wired'`:
the loop's last round goes to a criterion the state already records as
attempted and blocked, so `export-dir-wired` is never reached and the run
ends with two criteria unmet instead of one. The same off-by-one costs
`loop-resumed-clean` its goal (the duplicate `export_dir=` line un-satisfies
a met criterion) and makes `loop-fresh-start` repeat round 1's step in round
2.

## Expected output

- `resumed-blocked-attempt`: `fixtures/loop-resumed-blocked` to
  `expected/resumed-blocked.json`, exit 1 (`budget-exhausted` after round 3,
  `test-case-present` unmet).
- `resumed-one-round-left`: `fixtures/loop-resumed-clean` to
  `expected/resumed-clean.json`, exit 0 (`goal-reached` after round 3).
- `fresh-start`: `fixtures/loop-fresh-start` to
  `expected/fresh-start.json`, exit 0 (`goal-reached` after round 3, with
  round 4 of the budget unspent).
- `not-a-loop-directory`: a path with no `goal.json`, exit 2 and empty
  stdout.
