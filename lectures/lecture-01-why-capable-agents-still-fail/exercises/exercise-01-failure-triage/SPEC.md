# SPEC: exercise-01 failure-triage

Same contract as the lecture demo
([../../code/SPEC.md](../../code/SPEC.md)): read a JSONL transcript of
agent-run events, attribute each run to a harness subsystem with the five
mechanical rules, print the JSON report. This exercise applies it to a
fresh transcript, and the starter ships with three of the five rules
unimplemented.

## CLI surface

```text
main <transcript.jsonl>
```

Event and report shapes, rule definitions, rule precedence, evidence format,
and exit codes are identical to the demo SPEC. Normative details for this
unit:

- `fixtures/runs.jsonl` has 8 runs: one instructions, one tools, two
  environment, one state, two feedback (one after a failed verification, one
  with no verification at all), and one healthy run.
- `harness_failure_rate` for the fixture is 7/8, which must serialize as
  `0.875` in both tracks.

## Starter state (the intended failure)

The starter implements only `asked-for-repo-fact` (instructions) and
`command-unavailable` (tools). Runs ex-3 through ex-7 therefore come out
`unattributed`, and verification fails with a report mismatch that first
diverges at `$.harness_failure_rate` (0.25 instead of 0.875). The starter
must run cleanly and fail only by producing that wrong report; a crash or
exit-code change is a bug in the starter, not the intended state.

## Expected output

- `basic` case: `fixtures/runs.jsonl` → `expected/triage-report.json`,
  compared with normalization kind `json` (grading authority for both
  tracks).
