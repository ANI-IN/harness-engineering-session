# Module 1: Harness Engineering for Coding Agents - Reference live step for Assignment 2: State and sessions

This folder holds the live step of the reference solution for Assignment 2: State and sessions. It
is one A/B run on the four-session comments task (task id `F2-a2-four-sessions`, built on Feature 2:
Comments on issues, split over sessions of 10, 10, 10, and 20 turns). The harness arm used the reference
`ResumableStateLayer` as its state layer. The agent model was gpt-6-luna.

Command (from the repository root, with keys, Docker, and the checkpoints; `make doctor` passes):

```bash
uv run python section-2-state-lifecycle/assignment/live/run_live.py --impl section-2-state-lifecycle/assignment/solution --forced-stops
```

The script writes these files next to this README: `task.jsonl`, `command.txt`, `output.txt`,
`summary.json`, and `scores/` (one score record per arm). The grader checks them with
`assignment/a2_scenario/live_evidence.py`.

## What the run shows

This is the fifth attempt, run on 2026-10-17. It cost $0.027010.

- The harness arm ran four build sessions.
- The state layer wrote and committed a handoff and a `progress.md` entry at every stop.
- The referee found no continuity failure in either arm: no second migration head, no table
  created twice, no large share of an earlier session's lines redone.
- Neither arm finished the feature in its 50 build turns: each passed 3 of 56 hidden tests.

## How the sessions ended

The live step's rule says that sessions 1 to 3 of the harness arm end by a forced stop. A forced stop
is the turn budget (the fixed number of turns a session gets), or the agent's own
`finish(claim="not_done")` when the harness stop step still ran for that session: the handoff and
`progress.md` written and committed before the next session.

Sessions 1 and 3 ended by their turn budget. Session 2 ended on its last turn, when the agent called
`finish` with the claim `not_done`. The stop step ran for it: `summary.json` lists the handoff, the
two files the state layer wrote, and the new commit session 3 started from. So the run counts.

The fourth attempt, run just before this one, ended session 2 in the same way. It was judged under
the earlier rule, which accepted only the turn budget, so it did not count; its files are kept
outside the course folders.

The grade of this folder is 100 out of 100 (`../captured/grade-solution.txt`): every scenario
criterion passes, and the live criterion gives its 10 points.

To try again, move the files listed above out of this folder (keep this README), then run the
command again. The script refuses to run while `summary.json` is here.
