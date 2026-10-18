# LangSmith traces: version checks A/B, bare vs harness

Reference version. The links and the numbers come from the reference solution's live run,
captured on 2026-10-17: one A/B ([A/B id and run ids](../../../../docs/evidence/s4.md#s4-a4-solution)), files in `../live/` (`ab.txt` and the two
score records in `scores/`).

## Trace links

From `trace_url` (agent root) and `referee_trace_url` in each score record, LangSmith project
`shipharness-assignments`:

- bare arm:
  [agent trace](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/projects/p/a3d726fd-59b3-4715-836b-739793773f93/trace/01a1493e-e2d0-7ef1-b796-be92452e067b/run/01a1493e-e2d0-7ef1-b796-be92452e067b?start_time=2026-10-17T09%3A43%3A40.496300%2B00%3A00),
  [referee trace](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/projects/p/a3d726fd-59b3-4715-836b-739793773f93/trace/01a14943-b2b2-7681-8010-4b893400dca7/run/01a14943-b2b2-7681-8010-4b893400dca7?start_time=2026-10-17T09%3A48%3A55.859016%2B00%3A00)
- harness arm:
  [agent trace](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/projects/p/a3d726fd-59b3-4715-836b-739793773f93/trace/01a1493e-e2ea-7c42-99e8-91d9b4e2361f/run/01a1493e-e2ea-7c42-99e8-91d9b4e2361f?start_time=2026-10-17T09%3A43%3A40.522986%2B00%3A00),
  [referee trace](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/projects/p/a3d726fd-59b3-4715-836b-739793773f93/trace/01a14945-9948-7742-b36f-43eca834f874/run/01a14945-9948-7742-b36f-43eca834f874?start_time=2026-10-17T09%3A51%3A00.424150%2B00%3A00)

## Command

```bash
uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview
```

The command runs the ticket for Feature 4: Version checks on issue edits (`F4` in the command; its
main example is the `F4-canonical` line of `platform/datasets/teamtrack-features-v1.jsonl`, on the
checkpoint tag `m1-s4-start`, the repository state at the start of Section 4: Verification) in both arms: bare with no harness layer, harness with the demo-4 stack
(instructions, state, scope, verify; `SECTION_STACKS` in `platform/src/shipharness/ab/demo.py`). The
referee, the program that scores each run after the agent stops, judges both builds the same way and writes one score record per arm to
`exports/scores/<run_id>.json`. `--no-preview` skips the board preview containers. The command
prints the A/B id, one line per arm, and the cost line. `--purpose assignment` traces each run
to the LangSmith project `shipharness-assignments` (agent root and referee) and counts its spend in
the `assignment` cost session (`_trace_target` in `platform/src/shipharness/ab/commands.py`).

## What the comparison shows

Per-arm counts from the two score records:

| Measure | bare | harness |
|---|---|---|
| Status | completed | ABORTED: timeout |
| Agent's claim | none | none |
| Hidden tests passed | 68 of 69 | 43 of 69 |
| Referee mutants killed | 4 of 4 | 0 of 4 |
| Primary measure passed | false | false |
| Existing tests that keep passing | 189 of 190 | 188 of 190 |
| New house rule violations | 0 | 0 |
| Tests shipped | 34 | 0 |
| Out-of-scope files | 1 | 0 |
| Reviewer verdict | reject | reject |
| Agent turns | 52 | 43 |
| Agent cost, review cost | $0.018503, $0.00363 | $0.016211, $0.003794 |

"New house rule violations" is 0 in both records: `r1_new_violations`, `r2_new_violations`,
`r3_new_failures`, `r4_duplicates`, and `r5_audit_missing` are 0, and `r6_ok` and `r7_ok` are true.
Both reviewer verdicts agree with the referee (`reviewer_agrees` true).

The cost line printed by the ab command (last line of `../live/ab.txt`):

```
Cost: $0.042138 (this command: gpt-5.6-luna $0.007424, gpt-6-luna $0.034714; session $0.063847 of $2.50; build $2.186817 of $15.00 ($12.813183 left))
```

How to read it: the feature's primary measure has two parts, hidden tests passed and mutants killed
(planted faults that a shipped test caught), each against its total (`primary_measure` in the
feature's dataset line), and a run passes it only when both
counts equal their totals (`evaluate_primary` in `platform/src/shipharness/ab/score.py`). Neither arm
passed. The bare arm missed by one hidden test and killed every referee mutant with its 34 shipped
tests. The harness arm stopped with `ABORTED: timeout` after 43 turns, before it shipped a test, so
no test of its own could kill a referee mutant, and 26 hidden tests failed on its unfinished
build. One A/B at k=1 (one try per arm) is one run per arm, so a difference between the arms is a single
observation; this page reports counts, not rates, and does not show that one arm does better in
general.
