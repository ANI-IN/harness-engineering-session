# Module 1: Harness Engineering for Coding Agents - Reference live evidence for Assignment 4: Verification

Live evidence of the reference solution, in the layout every submission uses (see
[SPEC.md](../../SPEC.md#evidence-to-hand-in)). Two runs, both captured on 2026-10-17: one testgen
run with Filter 6: No duplicate tests applied to its report, and one A/B on Feature 4: Version checks
on issue edits (`F4` in the command). Their run ids, A/B id, and results are on
the [evidence page](../../../../docs/evidence/s4.md#s4-a4-solution). The grader validates these
files the same way as a learner's (`assignment/visible_tests/a4_live.py`) and re-runs nothing;
`../portfolio/` reports what they show.

- `testgen.txt`: the testgen run. A `$ <testgen command>` line, then everything the command
  printed, ending with `Cost: $0.003287 (testgen, model gpt-6-luna)`; "kept 1 of 5 proposed tests". Paths
  shortened for privacy.
- `testgen-report.json`: `.shipharness/a4/testgen/testgen-report.json` after
  `apply_filter --update-report`; 17 rows of filters 1-5, one filter-6 row, and `filter6` (1 kept
  test, 23 existing tests).
- `ab.txt`: the A/B. A `$ <ab command>` line, then everything the command printed (the A/B line,
  one line per arm, the `Cost:` line).
- `scores/`: the A/B's two ScoreRecords, bare arm and harness arm, copied from `exports/scores/`;
  each file is named by its run id.

The commands that produced them (from the repository root; keys in `.env`; Docker running for the
A/B). The testgen command runs without `--image`, so its tests ran on the host and it printed an
UNSANDBOXED warning (first lines of `testgen.txt`).

```bash
L=section-4-verification/assignment/solution/live
export PYTHONPATH=section-4-verification/assignment/solution
mkdir -p $L/scores
echo '$ uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 --out .shipharness/a4/testgen' > $L/testgen.txt
uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 \
    --out .shipharness/a4/testgen 2>&1 | tee -a $L/testgen.txt
uv run python -m a4_verification.apply_filter --repo platform/teamtrack --kept .shipharness/a4/testgen \
    --existing tests/visible/test_tenant_isolation.py --existing tests/visible/test_issues.py \
    --existing tests/visible/test_legacy_and_schema.py --update-report
cp .shipharness/a4/testgen/testgen-report.json $L/
echo '$ uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview' > $L/ab.txt
uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview 2>&1 | tee -a $L/ab.txt
AB=$(grep -o 'ab-[0-9]\{8\}-[0-9]\{6\}-[0-9a-f]\{6\}' $L/ab.txt | head -1)
grep -l "\"ab_id\": \"$AB\"" exports/scores/*.json | xargs -I{} cp {} $L/scores/
make grade-assignment-4 SUBMISSION=section-4-verification/assignment/solution   # instructor only
```

What `apply_filter` printed is not kept here; its result is in the report (the filter-6 row and
`filter6`). A new capture replaces all five files at once, then the run sections of
`../portfolio/` and `../captured/grade-solution.txt` are updated from them.
