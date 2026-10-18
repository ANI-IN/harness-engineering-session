# Assignment 1: Instructions. A/B report: the instructions layer on the tasks of Section 1: Instructions (reference tree)

This is the reference solution's report for Assignment 1: Instructions. Its structure is what your
report must have. Every number below comes from the live evidence in [live/](live/), as printed by
`ab_summary.py --exports live`.

## Setup

- Command: `uv run shipharness experiments --split section-1 --k 3 --layers instructions --batch a1-reference`
- Runs per arm: 24 (8 Section 1 tasks, 3 runs each)
- Model and reasoning effort: gpt-6-luna, medium (the course defaults, recorded in each
  experiment's metadata)

Instructions tree commit: 19a1731 <!-- check-style: allow SC10 the Section 1 checker reads this commit -->

That commit holds this folder's `instructions/`, copied unchanged to
`platform/teamtrack/harness/instructions/` on a throwaway branch before the run.

## Results

| Measure | Bare arm (runs failing of N) | Harness arm (runs failing of N) |
|---|---|---|
| R1: runs with at least one new violation of House rule 1: Tenant isolation | 0/24 | 0/24 | <!-- check-style: allow SC21 the Assignment 1 self-check reads this row verbatim -->
| R3: runs with at least one new failure of House rule 3: API conventions | 0/24 | 0/24 | <!-- check-style: allow SC21 the Assignment 1 self-check reads this row verbatim -->
| Leaks found by the tenant isolation probes (sum over runs) | 0 | 0 |
| Runs aborted or errored | 2 | 0 |

The two aborted runs are bare runs that reached the agent time limit. The referee still judged their
builds, so they count as runs. Neither one fails a measure.

Per task (runs failing of 3; bare arm first, then harness arm):

| Task | Tenant isolation | API conventions |
|---|---|---|
| Control task: role filter on the user list | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1: Org-wide issue search, canonical ticket | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, legacy-pattern ticket | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, ticket written as a bug report | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, ticket written by a product manager | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, terse ticket | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, other starting code (version a) | 0/3, 0/3 | 0/3, 0/3 |
| Feature 1, other starting code (version b) | 0/3, 0/3 | 0/3, 0/3 |

## Links

- [Bare arm experiment in LangSmith](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/datasets/c8c46487-1d0a-406b-bf4a-11a19b2c405b/compare?selectedSessions=a0b770c7-c675-4ebc-9861-f7ae1fc718d8)
- [Harness arm experiment in LangSmith](https://smith.langchain.com/o/10fe45d9-7a3d-4f39-92ad-8c5dc97653d4/datasets/c8c46487-1d0a-406b-bf4a-11a19b2c405b/compare?selectedSessions=33ae45f5-c9bb-41fb-9a18-684a1ee97f98)

## Cost and traces

- Cost: $0.545310 (agent and review cost, summed over the 48 score records; the command's own cost
  line reads $0.545313). The budget for this command is $2.50.
- Traces: 96 (one agent trace and one referee trace per run, counted from the trace links in the
  score records). The budget is 150.

## Reading the result

No measurable difference. The primary measure for Section 1 is registered by the course: a run fails
when it adds at least one new violation of House rule 1: Tenant isolation (`R1`). No run failed it:
0 of 24 bare runs and 0 of 24 harness runs. The secondary measure, House rule 3: API conventions
(`R3`), gives the same counts: 0 of 24 in each arm.

Task by task, every row reads 0 of 3 in both arms. That includes the legacy-pattern ticket, where
an unscoped legacy handler sits next to the right pattern, and the control task, where both arms
should pass.

With no failing bare run, the map had nothing to fix on these tasks with this model. The result does
not show that the restructured tree is useless. It shows that gpt-6-luna at medium effort already
keeps these two rules here when it can read the long handbook.

## Limits

Three runs per task is a small sample, so even a difference of one or two runs between the arms would
not be evidence on its own. One model and one effort level were used. The referee counts only what
the tenant isolation and API conventions probes (the requests the referee sends to test each rule)
cover. Both arms read the same facts, so the comparison measures organisation, not content. Two bare
runs reached the agent time limit, so the bare arm had a little less agent time in total.
