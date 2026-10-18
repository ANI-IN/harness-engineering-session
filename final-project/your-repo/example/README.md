# Module 1: Harness Engineering for Coding Agents - Final project part 2: the worked example

This folder holds the real output of every command in [../README.md](../README.md), run in order on
the worked example: three modules of boltons 26.2.0 (`typeutils`, `listutils`, `queueutils`) and
their tests, built into a new git repository by
[make_repo.sh](../../../use-in-your-repo/kit/examples/boltons-queueutils/make_repo.sh). boltons is
BSD-3-Clause. The filled kit files the example uses are in
[use-in-your-repo/kit/examples/boltons-queueutils/filled/](../../../use-in-your-repo/kit/examples/boltons-queueutils/README.md).
When and from which checkout it was captured is on the
[evidence page](../../../docs/evidence/final.md#final-project-captures).

## The files

Each step file lists every command as it was typed, after a `$`, then its output and its exit code.
The checkout's path is replaced by `$SHIPHARNESS`; nothing else is edited.

| File | Step | What it shows |
|---|---|---|
| `step-0-setup.txt` | Before you start | The fetch, the new repository, the version |
| `step-1-init.txt` | 1 | The 97 files `shipharness init` copies, and the first commit |
| `step-2-map.txt` | 2 | 103 markers at first, then 0 after filling; `init.sh` passes |
| `step-3-house-rules.txt` | 3 | The baseline, a PASS, the planted import that fails with exit code 3 |
| `step-4-testgen.txt` | 4 | The harnessed run: 3 of 3 proposed tests kept, and its cost |
| `step-5-results.txt` | 5 | The five filter results of each kept test |
| `step-6-decide.txt` | 6 | The layer decisions written to `docs/PLANS.md`, and the commits |
| `testgen-report.json` | 5 | The report testgen wrote, as it wrote it |

## What ran, and what you run yourself

Every step ran for real, including the harnessed run in step 4: one `shipharness testgen` call
with the verify layer and a $0.10 cap. Two parts are yours on your own code: writing the filled
files (step 2 copies them here because the worked example already has them), and judging whether a
kept test is worth committing. A full agent A/B such as `make final` runs only on TeamTrack.

## How to read it against your run

- Step 1 and step 2: the counts (97 files, 103 markers in 27 files) depend only on the kit version,
  so yours match unless the kit changed.
- Step 3: the probe counts depend on your test suite. The exit codes do not: 0 with no new
  violation, 3 with one.
- Step 4 and step 5: the model writes different tests on every run, so the test names, the number
  kept, the covered lines, and the cost differ. The cost line must stay at or below your cap.
