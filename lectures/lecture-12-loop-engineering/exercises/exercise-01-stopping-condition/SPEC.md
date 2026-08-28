# SPEC: exercise-01 stopping-condition

The lecture demo runs a loop and lets `--stop-on` choose the signal its
stopping condition reads ([../../code/SPEC.md](../../code/SPEC.md)). This
exercise is that condition on its own, applied to loops that already ran:
given a recorded trace of rounds, decide where the loop should have
stopped, and what that stop was worth.

## CLI surface

```text
main <transcript-file>
```

## The transcript

A transcript records one loop that ran with no stopping condition at all,
so it continued to the end of the trace. Each round holds both signals the
loop could have read:

```json
{
  "loop": "report-export",
  "budget_ticks": 12,
  "cost_per_round": 3,
  "rounds": [
    {
      "round": 1,
      "maker": { "criterion": "writer-implemented", "reports_done": true },
      "checker": { "verdict": "fail", "unmet": ["export-dir-wired", "test-case-present"] }
    }
  ]
}
```

`maker.reports_done` is the maker's report about the one step it took that
round. `checker.verdict` is the independent grade over every criterion of
the goal, and `checker.unmet` names the criteria still failing. `criterion`
is `null` for a round in which the maker took no step.

## The referee

Rounds are replayed in order, against a clock that starts at 0. Each round
gets exactly one decision, and the first rule that applies wins:

| Rule | Decision | Effect on the clock |
| --- | --- | --- |
| the loop already stopped in an earlier round | `not-run` | unchanged |
| `clock + cost_per_round > budget_ticks` | `stop-budget` | unchanged: the round is never started |
| the stopping condition's signal reads a pass | `stop-done` | advanced by `cost_per_round` |
| otherwise | `continue` | advanced by `cost_per_round` |

The signal is the round's `checker.verdict`: the checker grades the whole
goal and is not the party that did the work. `maker.reports_done` covers
the step the maker just took, which is a different question.

## Output

```json
{
  "loop": "...",
  "budget_ticks": 12,
  "rounds": [ { "round", "clock", "decision" } ],
  "stop": { "round", "clock", "decision", "reason" },
  "unmet_at_stop": [ "..." ],
  "verdict": "goal-reached" | "stopped-early" | "budget-exhausted"
}
```

`clock` on each row is the clock after that row's decision. `stop` repeats
the decision that ended the replay, with one of three reason strings:

| Decision | Reason |
| --- | --- |
| `stop-done` | `the stopping condition read a pass at round <n>` |
| `stop-budget` | `round <n> costs <cost> ticks and the <budget> tick budget has <left> left` |
| `trace-ended` | `the trace ends at round <n> with the loop still running` |

`trace-ended` is the defined behaviour for a trace that runs out while the
loop is still going; none of the committed transcripts reach it.

`unmet_at_stop` is `checker.unmet` from the last round that actually ran,
and it is empty when no round ran. `verdict` is `budget-exhausted` when the
clock ended the loop, `goal-reached` when nothing is unmet, and
`stopped-early` otherwise.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `goal-reached`: the loop stopped with every criterion met |
| 1 | `stopped-early` or `budget-exhausted`: the loop stopped with work remaining |
| 2 | usage error, or a missing transcript file; stdout empty |

## Fixtures

- `transcripts/never-converges.json` (the trap): five rounds of a loop
  whose checker never passes. The maker reports done at rounds 1 and 2
  (each of its steps satisfied its own criterion), round 3 attempts
  `test-case-present` and fails it, rounds 4 and 5 take no step. The
  budget affords four rounds, so a correct referee refuses round 5. Both
  drafts exit 1 here, which is the point: the exit code cannot tell the
  two apart, only the decisions can.
- `transcripts/converges.json`: four rounds where the checker passes at
  round 3, and the loop kept running into a pointless round 4. A correct
  referee stops at round 3 with nothing unmet.
- `transcripts/signals-agree.json`: two rounds of a maker that re-checks
  the whole goal before reporting, so both signals turn to pass in the
  same round. It grades identically under either reading, which is why a
  loop can look correct for a long time before the signals disagree.

## Starter state (the intended failure)

The starter's `reached_the_goal` reads `maker.reports_done`, on the
reasoning that the maker is the party doing the work and its report is the
earliest signal available. Everything else is already right: the clock, the
budget rule that refuses a round it cannot afford, the `not-run` tail after
a stop, `unmet_at_stop` taken from the last round that ran, and the three
reason strings. The starter runs cleanly on every fixture and fails only by
producing wrong decisions.

Verification fails first on the `never-converges` case at
`$.rounds[0].decision: 'stop-done' != 'continue'`: the maker reported done
at round 1 while two criteria were still unmet, so the starter ends a loop
that had eleven ticks of useful work left, and the four rounds it skips
report `not-run`. `signals-agree` passes under the starter, because the two
signals never disagree there.

## Expected output

- `never-converges`: `transcripts/never-converges.json` to
  `expected/never-converges.json`, exit 1 (`budget-exhausted` at round 5,
  `test-case-present` unmet).
- `converges-at-round-three`: `transcripts/converges.json` to
  `expected/converges.json`, exit 0 (`goal-reached` at round 3, round 4
  `not-run`).
- `signals-agree`: `transcripts/signals-agree.json` to
  `expected/signals-agree.json`, exit 0 (`goal-reached` at round 2).
