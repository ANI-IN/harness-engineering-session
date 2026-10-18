# Evidence report: <your target>

<!-- Keep the six sections below; the grader checks that each exists and is not empty. Paste real
output only. Replace every TODO. -->

This report covers generated tests, Filter 6: No duplicate tests, and the check for House rule 8:
Deleted issues stay hidden.

## Target

TODO: the repository and module you ran testgen on (`--target <id>` or `--repo` + `--module`),
its existing tests, and why you picked it.

## Commands

TODO: every command exactly as you ran it, in a code block: `shipharness testgen ...`,
`python -m a4_verification.apply_filter ...`, and `python -m a4_verification.run_r8 ...`.

## Results

TODO: a Markdown table from `testgen-report.json` (proposed, kept, discarded per filter), the
discard reasons, and the cost line the command printed.

## Filter 6 on the kept tests

TODO: the `apply_filter` output: how many kept tests Filter 6 kept, and which test each duplicate
copies.

## House rule 8 on TeamTrack

TODO: the `run_r8` result on `platform/teamtrack/` (probes, findings), and what happens with `--baseline`.

## Limits

TODO: what this evidence does not show.
