# Module 1: Harness Engineering for Coding Agents - Final project part 2: your own repository

## The problem

**Illustrative scenario.** The A/B on TeamTrack is done, and you want the same harness on your own
code on Monday. You copy a few files, write an `AGENTS.md` from memory, and start the agent. A week
later nobody knows which of those files the agent reads, which rules anything checks, or whether
any of it helped.

> **Terms on this page**
>
> - **Kit**: TeamTrack's harness as templates, copied into your repository by `shipharness init`.
> - **Map**: a short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **REPLACE marker**: a line in a kit template that says what to write in place of the example value.
> - **House rule**: a team convention written as one checkable sentence, with a check that finds violations.
> - **Baseline**: the violations that exist today, recorded once, so only new ones fail.
> - **Harnessed run**: a model run on your code with a harness layer turned on and a cost cap.

This page takes you through the six steps in order. Each step gives the command, the output it
printed when it ran on the worked example, and how to check that it worked. The worked example is a
real small repository: three modules of boltons 26.2.0 with their tests. Every output below was
captured by running exactly these commands, and the full output of each step is in
[example/](example/README.md). The longer guide with common mistakes per step is
[use-in-your-repo/apply-to-your-repo.md](../../use-in-your-repo/apply-to-your-repo.md).

## Before you start

Run everything from the root of your shipharness checkout, in the Ubuntu or macOS terminal, after
`make doctor` passes ([setup/](../../setup/README.md)). Step 4 needs your OpenAI key in `.env`; the
other steps make no model calls.

Set two variables. `SHIPHARNESS` is your checkout; `TARGET` is the repository you harness. For the
worked example, build it first; the fetch uses git and the network, never a model:

```bash
export SHIPHARNESS="$(pwd)"
uv run python platform/scripts/fetch_testgen_libs.py boltons
bash use-in-your-repo/kit/examples/boltons-queueutils/make_repo.sh /tmp/fp-example
export TARGET=/tmp/fp-example
```

> Your output will differ: paths, timings, ids, and the model's tests change on every run.

In the outputs on this page, `$SHIPHARNESS` stands for the checkout's path. `make_repo.sh` ends
with the eleven files it committed:

```text
created /tmp/fp-example from boltons 4332b35
.gitignore
LICENSE
boltons/__init__.py
...
tests/test_typeutils.py
```

For your own repository, set `TARGET` to its path instead, and commit or stash your work first.

## Step 1: Copy the kit with shipharness init

```bash
cd "$SHIPHARNESS"
uv run shipharness init --target "$TARGET"
```

**You should see** one `+` line per file, then the summary:

```text
Kit: $SHIPHARNESS/use-in-your-repo/kit/templates -> /tmp/fp-example
+ .agents/skills/assured-tests/README.md
...
+ session-handoff.md
wrote 97 files, 0 overwritten, 0 skipped, 0 unchanged
Next: fill the REPLACE markers, then run: shipharness init --check /tmp/fp-example
Cost: $0.000000 (no model calls)
```

**Check it worked.** Commit the kit as copied, so the next commit shows only what you filled in:

```bash
cd "$TARGET" && git add -A && git commit -q -m "kit: shipharness init" && git log --oneline | head -2
```

Two commits are listed: the kit, then your repository's previous head.

## Step 2: Fill the map

Count the markers first. At the start, `--check` lists every marker and exits 1:

```bash
cd "$TARGET"
uv run --project "$SHIPHARNESS" shipharness init --check . | tail -3
```

```text
session-handoff.md:14: nothing to fill now: the agent writes these notes at the end of each session. Delete this line.
x 103 REPLACE markers left in 27 files
Cost: $0.000000 (no model calls)
```

Then fill each file with facts about your repository: `AGENTS.md` first, then `ARCHITECTURE.md`,
`docs/`, the feature files, and `init.sh`. Delete documents that do not apply. In the worked example
the filled files already exist, so the example copies them and deletes the six documents a library
has no use for. For your own repository, you write these files yourself:

```bash
cp -r "$SHIPHARNESS/use-in-your-repo/kit/examples/boltons-queueutils/filled/." .
git rm -q docs/SECURITY.md docs/RELIABILITY.md docs/design-docs/api-conventions.md docs/design-docs/cursor-pagination.md docs/product-specs/teamtrack-base.md docs/references/alembic-llms.txt
uv run --project "$SHIPHARNESS" shipharness init --check .
uv run --project "$SHIPHARNESS" bash init.sh
```

**You should see** `--check` exit 0, with one line per deleted document, and `init.sh` pass:

```text
- docs/references/alembic-llms.txt: not present (deleted, or never installed)
+ no REPLACE markers left in the kit files
Cost: $0.000000 (no model calls)
== imports: the three modules load
== basic end-to-end test: queueutils, stop at the first failure (full suite: see AGENTS.md)
...                                                                      [100%]
3 passed in 0.26s
```

**Check it worked.** `--check` prints `+ no REPLACE markers left in the kit files`, and every path in
the map's "Where to look" table exists.

## Step 3: Set the house rules

Record today's violations once as the baseline, then check against it. The worked example keeps
House rule 6: Layering (`R6` in the commands: `queueutils` above `listutils` above `typeutils`) and the check that
existing tests keep passing:

```bash
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression --params harness/check-params.json --json > harness/check-baseline.json
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression --params harness/check-params.json --baseline harness/check-baseline.json
```

**You should see**, from the second command:

```text
UNSANDBOXED: the checks import and run this app's code on this machine.
  R6 import-linter
  existing tests
PASS  r6_layering      new=0 baseline=0 probes=1 364 ms
PASS  regression       new=0 baseline=0 probes=21 3351 ms
Cost: $0.000000 (no model calls)
```

**Check it worked.** Break the rule on purpose, run the second command again, and undo:

```bash
echo "from .queueutils import PriorityQueue" >> boltons/typeutils.py
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression --params harness/check-params.json --baseline harness/check-baseline.json
git checkout -- boltons/typeutils.py
git add -A && git commit -q -m "kit: filled for boltons, house-rule baseline" && git log --oneline | head -3
```

The check fails with exit code 3, a new violation:

```text
FAIL  r6_layering      new=1 baseline=0 probes=1 444 ms
      [violation] forbidden import: boltons.typeutils -> boltons.queueutils
PASS  regression       new=0 baseline=0 probes=21 3256 ms
```

## Step 4: Run the first harnessed run

`shipharness testgen` asks a model for tests of one module, with the verify layer on, and keeps a
test only if it passes five filters. It costs money, so the command sets a $0.10 cap:

```bash
MAX_RUN_COST_USD=0.10 uv run --project "$SHIPHARNESS" shipharness testgen --repo . --module boltons/queueutils.py --tests tests/test_queueutils.py --layers verify --max-tests 3 --sandbox local --python "$SHIPHARNESS/.venv/bin/python" --out /tmp/fp-example-testgen
```

**You should see**, with the run id cut:

```text
! UNSANDBOXED — results not official: generated tests run on this machine
Baseline: existing suite without doctests
testgen ...: completed; kept 3 of 3 proposed tests
+ tests/test_queueutils_generated.py::test_queue_order_peek_and_priority_update
+ tests/test_queueutils_generated.py::test_queue_custom_priority_key_and_removal
+ tests/test_queueutils_generated.py::test_queue_empty_operations_and_defaults
Kept tests and report: /tmp/fp-example-testgen
Cost: $0.001522 (testgen, model gpt-6-luna)
```

**Check it worked.** The last line is a cost line at or below your cap, and the `--out` folder holds
`testgen-report.json` and `tests/`. `--sandbox local` runs the generated tests with your permissions;
for code you do not trust, use `--sandbox docker --image` with an image of your repository.

## Step 5: Read the results

The report holds one result per filter per proposed test. This one-line script prints them:

```bash
uv run --project "$SHIPHARNESS" python -c "import json; r = json.load(open(\"/tmp/fp-example-testgen/testgen-report.json\")); print(r[\"status\"], \"kept\", len(r[\"kept\"])); [print(x[\"filter\"], \"pass\" if x[\"passed\"] else \"FAIL\", x[\"test_id\"].split(\"::\")[-1], \"-\", x[\"reason\"][:90]) for x in r[\"results\"]]"
```

The first test's five results:

```text
completed kept 3
1 pass test_queue_order_peek_and_priority_update - collected 2 tests
2 pass test_queue_order_peek_and_priority_update - passed 5 of 5 runs
3 pass test_queue_order_peek_and_priority_update - adds 5 covered lines: boltons/queueutils.py:134,163-165,170
4 pass test_queue_order_peek_and_priority_update - has real assertions and does not mock boltons.queueutils
5 pass test_queue_order_peek_and_priority_update - no source file changed during the test phase
```

**Check it worked.** Every kept test has five `pass` lines. A discarded test stops at its first
`FAIL`, and the reason names the filter. Read each kept test as code before you commit it: it asserts
what the code does today, so it guards against regressions but cannot find a bug that already exists.

For the house-rule check, `new=` counts violations that fail CI, `baseline=` counts the ones
already recorded, and the exit code is 0 (none new), 3 (a new violation), or 1 (an error).

## Step 6: Decide which layers to keep

Your repository has no A/B runner. Decide each layer from what it prevented and what it costs to keep
current, starting from what the course measured on TeamTrack
([evidence](../../docs/evidence/final.md#use-in-your-repository)). Write the decision down with the
date, next to your plans:

```bash
printf "\n## Layer decisions (%s)\n\n- Instructions: kept, smaller; six TeamTrack documents do not apply to a library.\n- State: kept; a feature can span sessions, and init.sh runs in seconds.\n- Scope: kept; one feature at a time in feature_list.json.\n- Verification: kept; the R6 check caught a planted import, and testgen kept only filtered tests.\n" "$(date +%Y-%m-%d)" >> docs/PLANS.md
tail -7 docs/PLANS.md
git add docs/PLANS.md && git commit -q -m "plans: which layers we keep, and why" && git log --oneline | head -4
```

**You should see** the new section at the end of `docs/PLANS.md`:

```text
## Layer decisions (2026-10-17)

- Instructions: kept, smaller; six TeamTrack documents do not apply to a library.
- State: kept; a feature can span sessions, and init.sh runs in seconds.
- Scope: kept; one feature at a time in feature_list.json.
- Verification: kept; the R6 check caught a planted import, and testgen kept only filtered tests.
```

**Check it worked.** `git log --oneline` shows three commits after your repository's own: the kit,
the filled kit with its baseline, and the decision. Revisit the decision when an agent makes a
mistake that a dropped layer would have caught.

## What you run yourself

The steps above run on any repository with a pytest suite. Two things are yours to do on your own
code, because no output from this course can stand in for them:

- Writing the map, the docs, and the house rules for your repository (step 2 copies the worked
  example's filled files only because they already exist).
- A full A/B with the agent building a feature. `make final` runs only on TeamTrack; on your own code,
  the harnessed run is `shipharness testgen`, as in step 4.

`shipharness testgen` also leaves a `.shipharness/` folder (its cost ledger) in your repository. Add it to your
`.gitignore`.
