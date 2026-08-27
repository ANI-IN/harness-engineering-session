# SPEC: loop-runner

One goal, one deterministic maker, one independent checker, one simulated
clock. The runner repeats a round until its stopping condition fires or the
clock cannot afford another round. The demo is the divergence between two
runs over the same loop directory, and the only variable is `--stop-on`:
the single signal the stopping condition reads.

## CLI surface

```text
main <loop-dir> --stop-on=maker|checker
```

A loop directory carries three things, all committed:

```text
<loop-dir>/
  goal.json         # the goal, its criteria, and the tick budget
  loop-state.json   # the loop's memory across rounds, in its seed state
  workspace/        # the files the criteria are checked against
```

`workspace/` is read once and edited in memory, and `loop-state.json` is
read once and carried forward in memory. Nothing under `<loop-dir>` is
written, so the committed fixtures are unchanged by any number of runs and
every command in the lecture README is idempotent. The in-memory map is the
seam where a live harness would edit real files and write the loop state
back between rounds
([deterministic fake agent](../../../docs/glossary.md#core-model)).

## goal.json

```json
{
  "loop": "report-export",
  "goal": "...",
  "budget_ticks": 12,
  "criteria": [ { "id", "check": { "kind", ... }, "step": { "path", "line" } } ]
}
```

A criterion is a pair: the `check` that decides whether it is met, and the
`step` the maker takes when it attempts it. Nothing requires the step to
satisfy the check; `fixtures/loop-wrong-target` is a goal where one does
not.

`kind` selects one of two executable probes, the deterministic stand-in for
running the real verification command. Both are carried over unchanged from
lecture 12's demo contract, detail strings included:

| kind | fields | passes when | detail strings |
| --- | --- | --- | --- |
| `key-declared-once` | `path`, `key` | exactly one line starts `<key>=` | `<path> declares <key> once` / `<path> has no <key>= line` / `<path> declares <key> N times` / `<path> missing` |
| `file-has-line` | `path`, `prefix` | some line starts with the prefix | `<path> has a line starting with <prefix>` / `<path> has no line starting with <prefix>` / `<path> missing` |

Both tracks treat LF and CRLF alike as line separators (see
docs/conventions.md, semantic rules).

## loop-state.json

```json
{ "loop": "report-export", "clock": 0, "status": "not-started", "rounds": [] }
```

The loop state is the loop's memory
([glossary](../../../docs/glossary.md)): what each round attempted and what
the two roles reported. Each round appends
`{"round", "criterion", "maker_reported", "checker_verdict"}`, where
`criterion` is `null` for a round in which the maker took no step. The
maker's step rule reads this list and nothing else, so the state file is
load-bearing rather than decorative: without it the maker would attempt the
same criterion every round.

## The round

Each round is the maker's turn followed by the checker's turn.

**The maker** takes the first criterion that is unmet now and does not
appear in the loop state's `criterion` list, applies its `step` (appending
the line, or creating the file with that line when it is absent), and then
re-runs that one criterion's check. `reports_done` is the result of that
single check: the maker grades the step it just took, never the rest of the
goal. When every unmet criterion has already been attempted, the maker
takes no step and reports `false`.

**The checker** grades every criterion of the goal against the workspace,
independent of what the maker did or said. Its `verdict` is `pass` only
when every criterion passes.

## The stopping condition

`--stop-on` names the one signal the condition reads:

| Value | Reads | `signal` is `pass` when |
| --- | --- | --- |
| `maker` | the maker's `reports_done` for the step it just took | the maker's own step passes its own criterion |
| `checker` | the checker's `verdict` over the whole goal | every criterion is met |

`signal` `pass` stops the loop; `fail` runs another round. The condition is
also bounded by the clock (below), which is what ends a loop whose signal
never passes.

## The clock (simulated, never a wall clock)

The clock is a step counter. The maker's turn costs 2 ticks and the
checker's turn costs 1, so a round costs 3. Before each round the runner
checks that the remaining budget covers a whole round; when it does not,
the loop stops with `fired_on: "clock"` and the round is not started.
Because every round advances the clock by a fixed positive amount, the
budget terminates any loop whose stopping condition never fires. No source
of real time is read in either track.

## Output

```json
{
  "loop", "goal", "stop_on", "budget_ticks",
  "rounds": [
    {
      "round", "clock",
      "maker": { "criterion", "action", "reports_done", "why" },
      "checker": { "verdict", "met", "unmet",
                   "checked": [ { "criterion", "status", "detail" } ] },
      "stopping_condition": { "reads", "signal", "decision" }
    }
  ],
  "stop": { "round", "clock", "fired_on", "reason" },
  "loop_state": { "loop", "clock", "status", "rounds" },
  "unmet": [ "..." ],
  "result": "goal-reached" | "stopped-early" | "budget-exhausted"
}
```

`unmet` and `result` are re-graded from the workspace after the loop stops,
never taken from the signal that ended it: the stopping condition is the
thing on trial, so its own claim is not allowed to grade it. `decision` is
`stop` or `continue`; `fired_on` is `maker`, `checker`, or `clock`.

`result` is `goal-reached` when nothing is unmet, `budget-exhausted` when
the clock ended a loop with work remaining, and `stopped-early` when a
stopping condition ended one with work remaining.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `goal-reached`: every criterion of the goal is met |
| 1 | `stopped-early` or `budget-exhausted`: the loop stopped with work remaining |
| 2 | usage error, an unknown `--stop-on` value, or a `<loop-dir>` without `goal.json` and `loop-state.json`; stdout empty |

## Fixtures and seeded symptoms

Both loop directories start from the same workspace: `src/report.txt`
holding `module=report`, `config/app.conf` holding `name=reports`, and no
`tests/` directory. Both carry the same three criteria in the same order
and the same 12 tick budget, so three rounds are affordable and a fourth
one is too.

`fixtures/loop-report-export` is the reachable goal: each criterion's step
satisfies its check. It is the loop both behavioural runs use.

| Run | Rounds | Observable outcome |
| --- | --- | --- |
| `--stop-on=maker` | 1 | The maker appends `writer=csv`, its own criterion passes, it reports done. The checker in the same round reports `export-dir-wired` and `test-case-present` unmet. The condition reads the maker, stops, and `result` is `stopped-early` with exit 1 |
| `--stop-on=checker` | 3 | The same round 1 happens and the loop continues. Rounds 2 and 3 wire the export directory and create the test case; the checker's `met` list grows from one to three, `result` is `goal-reached`, exit 0 |

`fixtures/loop-wrong-target` is the seeded defect: the `test-case-present`
criterion is checked against `tests/report-test.txt` while its step appends
to `src/report.txt`. The step therefore never satisfies its own check, so
the checker's verdict is `fail` in every round and the stopping condition
never fires. Round 3 attempts the criterion and the maker reports
`not-done` (its own check still fails, so it does not claim otherwise);
round 4 has no untried criterion left and takes no step; round 5 is refused
because the clock stands at 12 of 12 ticks. The observable symptom is
`result: budget-exhausted` with `test-case-present` unmet and exit 1, and
both tracks produce it identically.
