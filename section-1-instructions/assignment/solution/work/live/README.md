# Module 1: Harness Engineering for Coding Agents - Live evidence of the reference A/B

This folder holds the live evidence for the reference solution of Assignment 1: Instructions. It is
the real output of one A/B run, collected by `assignment/live_evidence.py`. The self-check and the
grader read these files. They never re-run anything.

## What the run was

One A/B on the eight tasks of Section 1: Instructions, three runs per task and arm: 24 bare runs and 24 harness runs
with gpt-6-luna. The harness arm used the instructions layer with this solution's `instructions/`
tree. The bare arm had the ticket and the repository only. The run took place on 2026-10-17 and cost
$0.545310, within the Assignment 1 budget of $2.50.

The commands, from the repository root (they need keys and Docker):

```bash
git switch -c a1-reference-run                     # throwaway branch: never merge it
rm -rf platform/teamtrack/harness/instructions
cp -r section-1-instructions/assignment/solution/work/instructions platform/teamtrack/harness/instructions
git add platform/teamtrack/harness/instructions && git commit -m "Assignment 1: reference tree for the live A/B"
CMD="uv run shipharness experiments --split section-1 --k 3 --layers instructions --batch a1-reference"
echo "\$ $CMD" > ~/a1-reference-output.txt
$CMD | tee -a ~/a1-reference-output.txt
git switch -                                       # back to your branch
uv run python section-1-instructions/assignment/live_evidence.py --batch a1-reference --output ~/a1-reference-output.txt --work section-1-instructions/assignment/solution/work
uv run python section-1-instructions/assignment/ab_summary.py --batch a1-reference --exports section-1-instructions/assignment/solution/work/live
```

## What the folder holds

| Path | What it is |
|---|---|
| `output.txt` | The command line and everything it printed, ending with its cost line |
| `experiments/` | The two experiment exports, one for the bare arm and one for the harness arm |
| `scores/` | One score record per run (48), as the referee wrote it |
| `runs/` | The run log of each harness run (24) |

In `output.txt`, paths are shortened for privacy.

Each harness run log notes the instruction files the layer placed. The grader checks that this list
equals the files of `../instructions/`.

## The result

No measurable difference between the arms:

- House rule 1: Tenant isolation: 0 of 24 runs failing in the bare arm, 0 of 24 in the harness arm.
- House rule 3: API conventions: 0 of 24 runs failing in each arm.
- Two bare runs reached the agent time limit; the referee still judged their builds.

The full report is [../ab-report.md](../ab-report.md). With this folder, the grader gives the
reference solution 100 out of 100 (`../../captured/grade-solution.txt`).
