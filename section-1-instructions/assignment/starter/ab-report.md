# Assignment 1: Instructions. A/B report: the instructions layer on section-1

<!-- Fill every TODO. Copy the numbers from the output of ab_summary.py; do not type them by hand.
     Counts, not percentages: "3/24", never "12.5%". The self-check compares the command, the runs
     per arm, the two Results rows, and the links with the live evidence in live/. -->

## Setup

- Command: `uv run shipharness experiments --split section-1 --k 3 --layers instructions --batch a1-TODO`
- Instructions tree commit: TODO (the commit of your restructured tree, from `git log -1 --format=%h`)
- Runs per arm: TODO (8 tasks x k=3 = 24, unless the README's 4-task fallback applies)
- Model and reasoning effort: TODO (from the experiment metadata printed by ab_summary.py)

## Results

| Measure | Bare arm (runs failing of N) | Harness arm (runs failing of N) |
|---|---|---|
| R1: runs with at least one new violation of the tenant isolation rule | TODO | TODO | <!-- check-style: allow SC21 the Assignment 1 self-check reads this row verbatim -->
| R3: runs with at least one new failure of the API conventions rule | TODO | TODO | <!-- check-style: allow SC21 the Assignment 1 self-check reads this row verbatim -->

Secondary (optional, not graded; you may delete this line): tenant isolation leaks summed over runs,
and the number of runs aborted or errored, copied from the ab_summary.py output.

## Links

- Bare experiment: TODO
- Harness experiment: TODO
- Comparison view: TODO

## Cost and traces

- Cost: $TODO
- Traces: TODO

## Reading the result

TODO: at least 60 words. Compare the two arms on the tenant isolation rule (`R1`) and on the API
conventions rule (`R3`), task by task where they differ. Say which tasks drove the difference (the
trap task? the control task?), and whether your map and skill were read (the run logs list the files
each harness run opened).

## Limits

TODO: at least 20 words. What this A/B cannot tell you (sample size, one model, what the checks
cover).
