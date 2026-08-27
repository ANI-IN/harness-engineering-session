# SPEC: session-simulator

A deterministic replay of one three-session task under two modes: with the
continuity artifacts present, and without them. Every cost in the report is
computed from the fixture files (line counts, feature statuses); the
timeline itself is fixed by this SPEC. Both tracks read the same workspace
and must emit the same report; `expected/` is the grading authority.

## CLI surface

```text
main <workspace-dir> [--no-handoff | --compare]
```

`<workspace-dir>` contains the continuity artifacts: `claude-progress.md`,
`session-handoff.md`, `feature_list.json` (valid against the library
schema; exactly one `in-progress` and one `not-started` feature), and
`repo-map.json` (`{"files": [{"path", "lines"}]}`, the repository an
agent would otherwise re-scan).

## The timeline (fixed)

Session 1 is identical in both modes: it half-implements the `in-progress`
feature and records everything (cost 0; the fixtures ARE its record).

With handoff, sessions 2 and 3 each reacquire context by reading the
progress and handoff files (`reacquisition_lines` = the sum of their line
counts), recover all four facts (`next-step`, `open-failure`, `decisions`,
`feature-statuses`), finish the in-progress feature (session 2), and
complete the not-started feature (session 3).

Without handoff, sessions 2 and 3 each pay the full repository scan
(`reacquisition_lines` = the sum of `repo-map.json` line counts) and
recover nothing. Session 2 cannot see that work was underway, restarts the
in-progress feature, and re-decides the date-storage decision (rework and
drift). Session 3 re-explores, finishes the in-progress feature, and never
reaches the not-started one (drift again).

## Output

Default and `--no-handoff`: a JSON report with `handoff`, `sessions`
(three rows: `session`, `reacquisition_lines`, `recovered`, `work`,
`rework`, `decision_drift`), and `totals` (`reacquisition_lines`,
`features_completed`, `rework_sessions`, `drift_events`).

`--compare`: a plain-text table, header then one line per mode in the
order with-handoff, no-handoff, formatted
`<mode> | <reacquisition_lines> | <features_completed> | <rework_sessions> | <drift_events>`
(pinned by `expected/compare.txt`).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report or table emitted |
| 2 | usage error or missing workspace; stdout empty |

## Language-neutrality

The continuity artifacts under measurement are the course's canonical
markdown and JSON files; nothing in them names an implementation language,
and both tracks compute identical costs from identical bytes.
