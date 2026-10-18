# Module 1: Harness Engineering for Coding Agents - Apply the kit to your repository

## The problem

**Illustrative scenario.** You write an `AGENTS.md` for your own repository by hand, and it grows
into a long list that mixes rules with history. Nothing checks it, so links break and rules drift.
Sessions still start from nothing, and the agent still marks its own work done. When someone asks
whether any of this helped, you have impressions, not measurements.

The cost: time spent on instructions the agent may never read, rules that exist only on paper, and
no evidence for keeping or dropping any part of the harness.

> **Terms on this page**
>
> - **Harness**: the files and code around the agent that decide what it sees and may do.
> - **Harness layer**: one part of the harness: instructions, state, scope, or verification.
> - **Map**: a short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **Kit**: TeamTrack's harness as templates, copied into your repository by `shipharness init`.
> - **REPLACE marker**: a line in a kit template that says what to write in place of the example value.
> - **House rule**: a team convention written as one checkable sentence, with a check that finds violations.
> - **Baseline**: the violations that exist today, recorded once, so only new ones fail.
> - **House rules 1 to 7**: TeamTrack's rules, from House rule 1: Tenant isolation to
>   House rule 7: Migrations. The kit files and the `--rules` option name them by code, `R1` to `R7`.
> - **Mutant**: a copy of the code with one small bug planted on purpose; a good test fails on it ("kills" it).
> - **Doctest**: an example in a docstring that runs as a test.

## Why it happens

- A long file hides the rules: "A giant instruction file crowds out the task, the code, and the
  relevant docs". OpenAI keeps `AGENTS.md` short: "we treat it as the table of contents", "roughly
  100 lines" ([Harness engineering](https://openai.com/index/harness-engineering/)).
- Unchecked docs rot. The same team checks them by machine: "Dedicated linters and CI jobs validate
  that the knowledge base is up to date, cross-linked, and structured correctly."
- Every harness piece is a guess about the model: "every component in a harness encodes an
  assumption about what the model can't do on its own, and those assumptions are worth stress
  testing" ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).

## What the kit does

This guide puts TeamTrack's harness into your repository in seven steps, from install to deciding
which layers earn their place. Steps 1 to 4 make no model calls. Step 5 runs `shipharness testgen`
under a cost cap you set. Each step gives the command, what you should see, how to check it worked,
and common mistakes.

| Step | What you do | Model calls |
|---|---|---|
| [1](#step-1-install) | Install shipharness | None |
| [2](#step-2-copy-the-kit-into-your-repository) | Copy the kit with `shipharness init` | None |
| [3](#step-3-fill-in-the-map) | Fill the REPLACE markers | None |
| [4](#step-4-define-your-house-rules) | Adapt the house rules; run `shipharness check` | None |
| [5](#step-5-the-first-harnessed-run) | Run `shipharness testgen` on one module | Yes, capped |
| [6](#step-6-read-the-results) | Read the check and testgen output | None |
| [7](#step-7-decide-which-layers-earn-their-place) | Keep, change, or drop each layer | None |

The course measures whether each layer helps, and step 7 starts from what it found on TeamTrack.

## Before you start

You need the course repository set up with [setup/](../setup/README.md), up to `make doctor`. Step 5
also needs your OpenAI key in `.env`.

**The worked example.** Every step runs on a real, small repository: three modules of boltons 26.2.0
(`typeutils`, `listutils`, `queueutils`) with their tests. boltons is BSD-3-Clause, and the course
already pins it for `shipharness testgen`. It is a library, not a web app, so it also shows what to
do when most of TeamTrack's house rules do not apply. Every file's end state is in
[kit/examples/boltons-queueutils/](kit/examples/boltons-queueutils/README.md).

Build it from your shipharness checkout. The fetch uses git and the network, never a model:

```bash
uv run python platform/scripts/fetch_testgen_libs.py boltons
bash use-in-your-repo/kit/examples/boltons-queueutils/make_repo.sh /tmp/bq-example
```

> Your output will differ: paths, timings, ids, and the model's tests change on every run.

The fetch prints one line (the pinned commit is cut here; it is listed in the
[evidence](../docs/evidence/final.md#use-in-your-repository-captures)). In every output on this page,
`$SHIPHARNESS` stands for the path of your checkout:

```text
ok boltons 26.2.0 ... -> $SHIPHARNESS/.shipharness/libs/boltons/src
```

`make_repo.sh` copies the three modules and their tests into a new git repository:

```text
created /tmp/bq-example from boltons 4332b35
.gitignore
LICENSE
boltons/__init__.py
boltons/listutils.py
boltons/queueutils.py
boltons/typeutils.py
tests/__init__.py
tests/conftest.py
tests/test_listutils.py
tests/test_queueutils.py
tests/test_typeutils.py
```

Then set two variables once per terminal. Replace the first path with your checkout's path, and
the second with your repository's path when you leave the worked example:

```bash
export SHIPHARNESS=~/shipharness
export TARGET=/tmp/bq-example
```

## Step 1: Install

**What it is.** shipharness runs from its own checkout, with its own Python environment. Your
repository does not need to install anything.

```bash
cd "$SHIPHARNESS"
uv sync
uv run shipharness --version
```

**You should see:**

```text
Resolved 85 packages in 14ms
Checked 83 packages in 9ms
shipharness 0.1.0
```

**Check it worked.** `uv run shipharness init --help` lists `--target`, `--check`, `--skills`, and
`--force`.

**Common mistakes.**

- Running `uv sync` outside the checkout. It stops with exit code 2:

  ```text
  error: No `pyproject.toml` found in current directory or any parent directory
  ```

  Run `cd "$SHIPHARNESS"` first.
- On Windows, running from PowerShell. Use the Ubuntu terminal ([setup/windows.md](../setup/windows.md)).

## Step 2: Copy the kit into your repository

**What it is.** `shipharness init` copies the kit's templates and the four course skills into your
repository. The file list, and where each file comes from, is in [kit/README.md](kit/README.md).
Commit or stash your own changes first, so the kit's files show up as one change.

```bash
cd "$SHIPHARNESS"
uv run shipharness init --target "$TARGET"
```

**You should see** one `+ <path>` line per file, then a summary (first two and last eleven lines):

```text
Kit: $SHIPHARNESS/use-in-your-repo/kit/templates -> /tmp/bq-example
+ .agents/skills/assured-tests/README.md
...
+ feature_list.json
+ feature_list.schema.json
+ harness/check-params.json
+ harness/sandbox-policy.toml
+ harness/shipharness_adapter.py
+ init.sh
+ progress.md
+ session-handoff.md
wrote 97 files, 0 overwritten, 0 skipped, 0 unchanged
Next: fill the REPLACE markers, then run: shipharness init --check /tmp/bq-example
Cost: $0.000000 (no model calls)
```

The 97 files are 27 templates plus the four skills twice: once in `.claude/skills/` (Claude Code,
Cursor) and once in `.agents/skills/` (Codex, Cursor). `--skills claude` or `--skills agents`
installs one copy only.

**Check it worked.**

1. Run the same command again. It writes nothing:

   ```text
   Kit: $SHIPHARNESS/use-in-your-repo/kit/templates -> /tmp/bq-example
   wrote 0 files, 0 overwritten, 0 skipped, 97 unchanged
   Next: fill the REPLACE markers, then run: shipharness init --check /tmp/bq-example
   Cost: $0.000000 (no model calls)
   ```

2. Validate the installed skills from your repository with
   `uv run --project "$SHIPHARNESS" shipharness skills validate .claude/skills`:

   ```text
   + assured-tests: valid (SKILL.md 96 lines)
   + harness-setup: valid (SKILL.md 103 lines)
   + house-rules: valid (SKILL.md 94 lines)
   + skill-template: valid (SKILL.md 46 lines)
   4 skills checked, 0 errors, 0 warnings
   Cost: $0.000000 (no model calls)
   ```

   The same command on `.agents/skills` ends with the same two lines.

3. Commit the kit as copied, so the next commit shows exactly what you filled in:

   ```bash
   cd "$TARGET" && git add -A && git commit -m "kit: shipharness init"
   ```

**Common mistakes.**

- The target does not exist:

  ```text
  x target directory not found: /tmp/no-such-repo
  Cost: $0.000000 (no model calls)
  ```

- Your repository already has one of the files, for example its own `AGENTS.md`. `init` never
  overwrites it, and says so. From a folder that held only an `AGENTS.md`, with the `+` lines
  filtered out:

  ```text
  Kit: $SHIPHARNESS/use-in-your-repo/kit/templates -> /tmp/bq-skip-demo
  ! skipped AGENTS.md: exists with other content (--force overwrites)
  wrote 61 files, 0 overwritten, 1 skipped, 0 unchanged
  Next: fill the REPLACE markers, then run: shipharness init --check /tmp/bq-skip-demo
  Cost: $0.000000 (no model calls)
  ```

  Merge by hand: open [kit/templates/AGENTS.md](kit/templates/AGENTS.md) next to your own file. Use
  `--force` only when you want the template to replace your file.

## Step 3: Fill in the map

**What it is.** You replace TeamTrack's values with facts about your repository, file by file,
until no REPLACE marker is left. Each marker says what the value means; the TeamTrack value below it
shows the shape. Markers have one form per file type: `<!-- REPLACE: ... -->` in Markdown,
`# REPLACE: ...` in shell, YAML, TOML, and Python, and a `"_replace"` key in JSON.

```bash
cd "$TARGET"
uv run --project "$SHIPHARNESS" shipharness init --check .
```

**You should see**, at first, one line per marker, a count, and exit code 1 (first four and last
three lines):

```text
.github/workflows/shipharness.yml:1: CI for your repository's house rules. The values are TeamTrack's, as if teamtrack/ were its own repository: the app is at the repository root, the existing tests are in tests/visible, and the adapter is harness/shipharness_adapter.py.
.github/workflows/shipharness.yml:22: the module testgen writes tests for, relative to the repository root.
.github/workflows/shipharness.yml:26: the existing tests of that module (filter 3 measures coverage over them).
.github/workflows/shipharness.yml:43: the shipharness repository you cloned for the course (README, Quick start).
...
session-handoff.md:14: nothing to fill now: the agent writes these notes at the end of each session. Delete this line.
x 103 REPLACE markers left in 27 files
Cost: $0.000000 (no model calls)
```

Fill the files in this order, because later files point at earlier ones:

1. `AGENTS.md`: what the repository is, where each rule lives, the commands, and the session start
   and end steps. Keep it a map, near 100 lines; the rules go into the documents it points to.
2. `ARCHITECTURE.md`: modules or packages, layers, and what each may import.
3. `docs/`: the rules, quality grades, plans, design decisions, product specs, notes on tools, and
   the clean-state checklist.
4. `feature_list.json`, `docs/exec-plans/active/F1.md`, `progress.md`, `session-handoff.md`: one
   real feature to work on next. Every entry starts with `"passes": false`.
5. `init.sh`: reach a known state, then run one basic end-to-end test.

Delete a document that does not apply; do not leave it half-filled. `--check` lists a deleted kit
file as not present and does not count it. Run every command you write into `AGENTS.md`, `init.sh`,
and the checklist before you commit it.

In the worked example, six documents were deleted, because a library with no API, tenants, or
database has no use for them. The feature is a real bug: the docstrings of `peek` and `pop` say an
empty queue raises `KeyError`, but the code raises `IndexError`. The last line of the traceback from
`uv run --project "$SHIPHARNESS" python -c "from boltons.queueutils import HeapPriorityQueue; HeapPriorityQueue().pop()"`:

```text
IndexError: pop on empty queue
```

Compare [the filled map](kit/examples/boltons-queueutils/filled/AGENTS.md) with
[the template](kit/templates/AGENTS.md) to see the edits.

**Check it worked.**

1. `--check` exits 0. In the filled worked example:

   ```text
   - docs/RELIABILITY.md: not present (deleted, or never installed)
   - docs/SECURITY.md: not present (deleted, or never installed)
   - docs/design-docs/api-conventions.md: not present (deleted, or never installed)
   - docs/design-docs/cursor-pagination.md: not present (deleted, or never installed)
   - docs/product-specs/teamtrack-base.md: not present (deleted, or never installed)
   - docs/references/alembic-llms.txt: not present (deleted, or never installed)
   + no REPLACE markers left in the kit files
   Cost: $0.000000 (no model calls)
   ```

2. `init.sh` passes. From `uv run --project "$SHIPHARNESS" bash init.sh`:

   ```text
   == imports: the three modules load
   == basic end-to-end test: queueutils, stop at the first failure (full suite: see AGENTS.md)
   ...                                                                      [100%]
   3 passed in 0.46s
   ```

3. Every path the map names exists. Open each row of its "Where to look" table.

**Common mistakes.**

- Deleting the marker line but leaving TeamTrack's value under it. `--check` cannot see that. Read
  each file once more and search for `TeamTrack`, `org_id`, and `app/api`.
- Leaving a `"_replace"` key in `feature_list.json`. The schema forbids extra keys, so the file no
  longer validates until the key is gone.
- A map that grows into a manual. Move each rule into the document it belongs to, and leave one line
  and a pointer in `AGENTS.md`.
- Commands that were never run. An agent trusts `AGENTS.md`; a wrong test command costs it a session.

## Step 4: Define your house rules

**What it is.** A house rule is the course's name for what OpenAI calls "golden principles": a
convention checked by code, not by memory. Their reason: "When documentation falls short, we promote
the rule into code" (Source 1).
`shipharness check` runs TeamTrack's seven rules on any FastAPI app, with no model calls.

Three files hold your version:

| File | What you decide |
|---|---|
| `docs/house-rules.md` | Which of the seven house rules you keep, and why |
| `harness/shipharness_adapter.py` | The facts the checks need about your app |
| `harness/check-params.json` | `regression_targets`: the pytest targets of your suite |

For a FastAPI service, keep the adapter's methods and change their values: two seeded tenants, how
a test client signs in as a role, the seeded ids, and how to count audit rows. The template answers
exactly like TeamTrack's built-in adapter, so it is a working start.

For a library, keep House rule 6: Layering (`R6`) for your packages, plus the check that existing tests
keep passing. The worked example keeps an import-linter layers contract: `queueutils` above `listutils`
above `typeutils` ([its adapter](kit/examples/boltons-queueutils/filled/harness/shipharness_adapter.py)).

Record today's violations once as the baseline, then check against it. Run both from your
repository:

```bash
cd "$TARGET"
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
  --params harness/check-params.json --json > harness/check-baseline.json
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
  --params harness/check-params.json --baseline harness/check-baseline.json
```

For a service that keeps all seven rules, write `--rules R1,R2,R3,R4,R5,R6,R7`.

**You should see** one `PASS` or `FAIL` line per check, from the second command:

```text
UNSANDBOXED: the checks import and run this app's code on this machine.
  R6 import-linter
  existing tests
PASS  r6_layering      new=0 baseline=0 probes=1 722 ms
PASS  regression       new=0 baseline=0 probes=21 7006 ms
Cost: $0.000000 (no model calls)
```

The 21 probes of `regression` are 16 test functions and 5 doctests: `check-params.json` sets
`regression_targets` to `--doctest-modules boltons tests`.

**Check it worked.** Break the rule on purpose and watch the check fail:

```bash
echo "from .queueutils import PriorityQueue" >> boltons/typeutils.py
PYTHONPATH=harness uv run --project "$SHIPHARNESS" shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
  --params harness/check-params.json --baseline harness/check-baseline.json
```

```text
UNSANDBOXED: the checks import and run this app's code on this machine.
  R6 import-linter
  existing tests
FAIL  r6_layering      new=1 baseline=0 probes=1 924 ms
      [violation] forbidden import: boltons.typeutils -> boltons.queueutils
PASS  regression       new=0 baseline=0 probes=21 9078 ms
Cost: $0.000000 (no model calls)
```

The exit code is 3, a new violation. Undo the change with `git checkout -- boltons/typeutils.py`. A
check that never fails proves nothing.

Then wire it into CI. `.github/workflows/shipharness.yml` runs the second command on every push;
commit `harness/check-baseline.json` with it. The workflow checks out shipharness next to your
repository; change the repository name in it if you use a fork.

**Common mistakes.**

- `PYTHONPATH=harness` missing, so the adapter cannot be imported. The last line of the error:

  ```text
  ModuleNotFoundError: No module named 'shipharness_adapter'
  ```

- A rule in `--rules` whose adapter methods you deleted. With `--rules R2` in the worked example,
  the exit code is 1:

  ```text
  UNSANDBOXED: the checks import and run this app's code on this machine.
  FAIL  r2_roles         new=1 baseline=0 probes=0 0 ms
        [error] check crashed: AttributeError: 'HouseRulesAdapter' object has no attribute 'create_app'
  Cost: $0.000000 (no model calls)
  ```

  Drop the rule, or add the methods `docs/house-rules.md` lists for it.
- Running the checks on code you do not trust. They import and run your app in this process; the
  first line says so.
- Writing the layering contract (`R6`) only into your repository's own `.importlinter`. The check reads the
  contract from the adapter on purpose, so a change under review cannot weaken it.

## Step 5: The first harnessed run

**What it is.** The first command that puts a model to work on your code. `shipharness testgen` asks
a model for tests of one module and keeps a proposed test only if it passes five filters:

1. Filter 1: Builds and collects. It imports and runs.
2. Filter 2: Passes five runs. It passes five runs in a row.
3. Filter 3: Adds coverage or catches a mutant. It adds line coverage, or kills a mutant no
   existing test kills.
4. Filter 4: Real assertions. It has real assertions and does not mock the unit under test.
5. Filter 5: No source changes. It changed no source file.

Filters 1 to 3 come from Meta's
[Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171);
Filters 4 and 5 are the course's own. `--layers verify` gives the model the
course's verification layer. `shipharness testgen` works on any repository with a pytest suite, so it is the first
harnessed run for a repository that is not TeamTrack.

It costs money. Set a cap below the default for a first try. `MAX_RUN_COST_USD` is $0.20 per run by
default (`platform/src/shipharness/config/settings.py`), and the cost tracker refuses a model call
that would cross it. Prices per token are in `platform/config/prices.toml`. The variable overrides the
default for one command; this check prints the cap the command will use:

```bash
MAX_RUN_COST_USD=0.10 uv run --project "$SHIPHARNESS" python -c "from shipharness.config import Settings; print(Settings().max_run_cost_usd)"
```

```text
0.1
```

The command for the worked example, run from the repository, with a $0.10 cap and three proposed
tests:

```bash
cd "$TARGET"
MAX_RUN_COST_USD=0.10 uv run --project "$SHIPHARNESS" shipharness testgen --repo . \
  --module boltons/queueutils.py --tests tests/test_queueutils.py --layers verify \
  --max-tests 3 --sandbox local --python "$SHIPHARNESS/.venv/bin/python" \
  --out /tmp/boltons-queueutils-testgen
```

- `--sandbox local` runs the generated tests on your machine with your permissions, and the command
  prints UNSANDBOXED. For code you do not trust, build an image and pass `--sandbox docker --image`.
- `--python` is an interpreter with your repository's dependencies, pytest, and coverage. The
  shipharness environment has all three for this example.
- With `--layers verify`, the tests the layer runs are the folder of `--tests` (here `tests/`). The
  migration check runs only when the repository has an Alembic configuration, so a library needs no
  database.

**You should see** a baseline line, a summary, one line per proposed test (`+` kept, `-` discarded
with the filter and reason), the output folder, and the cost line. From the course's run, with the
run id replaced:

```text
! UNSANDBOXED — results not official: generated tests run on this machine
Baseline: existing suite without doctests
testgen <run id>: completed; kept 3 of 3 proposed tests
+ tests/test_queueutils_generated.py::test_priority_updates_preserve_order_for_equal_priorities
+ tests/test_queueutils_generated.py::test_remove_and_empty_queue_defaults
+ tests/test_queueutils_generated.py::test_custom_priority_key_and_unexpected_keyword
Kept tests and report: /tmp/boltons-queueutils-testgen
Cost: $0.002031 (testgen, model gpt-6-luna)
```

The run stayed far below the $0.10 cap ([evidence](../docs/evidence/final.md#use-in-your-repository)).

**Check it worked.** The output folder holds the kept tests and `testgen-report.json`, and the last
line is a cost line at or below your cap.

**Common mistakes.**

- No API key. testgen stops before any model call. With `OPENAI_API_KEY=` (empty) in front of the
  command:

  ```text
  x OPENAI_API_KEY is missing: add it to .env at the repo root
  Cost: $0.000000 (no model calls)
  ```

  The key goes into `.env` in the shipharness checkout, never into your repository.
- `--python` points at an interpreter without your dependencies. Then even the existing tests fail,
  and nothing can be kept.
- `--out` inside your repository leaves untracked files behind. Use a folder outside it, or add the
  folder to `.gitignore`.

## Step 6: Read the results

**The check output**, part by part:

| Part | Meaning |
|---|---|
| `PASS` / `FAIL` | `FAIL` means at least one new violation |
| `new=` | Violations not in the baseline: these fail CI |
| `baseline=` | Violations already in `check-baseline.json`: shown, not counted |
| `probes=` | Requests sent (rules `R1` to `R5`), import contracts run (`R6`, layering), or tests run |
| `[violation] ...` | One line per new violation, naming the endpoint or import |
| Exit code | 0 no new violation, 3 a new violation, 1 an error |

Add `--json` for one JSON document with every finding; that is also the baseline format.

**The testgen output.** A kept test asserts what the code does today. So it guards against future
regressions, but it "cannot detect existing faults residing in the code base"
([Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)).
Review each kept test as code before you commit it. A discarded test's line names the filter that
rejected it. Without mutants, Filter 3 keeps only tests that add line coverage, so on a well-covered
module most proposals are discarded there.

In the worked example, `testgen-report.json` lists the kept tests and one result per filter per
test. Cut to the first test's five results, reformatted to one result per line, with the repeated
test id shortened to `...` and the run id replaced:

```json
  "run_id": "<run id>",
  "status": "completed",
  "unsandboxed": true,
  "kept": [
    "tests/test_queueutils_generated.py::test_priority_updates_preserve_order_for_equal_priorities",
    "tests/test_queueutils_generated.py::test_remove_and_empty_queue_defaults",
    "tests/test_queueutils_generated.py::test_custom_priority_key_and_unexpected_keyword"
  ],
  "results": [
    {"test_id": "...", "filter": 1, "passed": true, "reason": "collected 1 test"},
    {"test_id": "...", "filter": 2, "passed": true, "reason": "passed 5 of 5 runs"},
    {"test_id": "...", "filter": 3, "passed": true, "reason": "adds 5 covered lines: boltons/queueutils.py:134,163-165,170"},
    {"test_id": "...", "filter": 4, "passed": true, "reason": "has real assertions and does not mock boltons.queueutils"},
    {"test_id": "...", "filter": 5, "passed": true, "reason": "no source file changed during the test phase"},
```

The other two kept tests passed Filter 3 by adding 9 covered lines and 1 covered line. All three
are in one file, `tests/test_queueutils_generated.py`, under the `--out` folder.

When a result surprises you, rerun the check alone (`--rules R6`) to see one rule's findings. For
testgen, open `testgen-report.json` and read the reason recorded for each test.

## Step 7: Decide which layers earn their place

**What it is.** The course's harness has four layers: instructions, state, scope, and verification.
Not every repository needs all of them in full. Anthropic's method is "removing one component at a
time and reviewing what impact it had on the final result"
(Source 2).
On TeamTrack, `make demo-2 LAYERS=-state` does that for you, and it costs money
([after-class.md](../docs/after-class.md)). Your own repository has no A/B runner (the course tool
that runs the same ticket with and without a layer), so decide each layer from what it prevents and
what it costs to keep current.

Start from what the course measured on TeamTrack. The instructions, state, and verification layers
showed no measurable difference on their primary measures. With the scope layer on, the agent kept
to the allowed files in 3 of 3 runs of one ticket; without the harness, it did in 0 of 3
([evidence](../docs/evidence/final.md#use-in-your-repository)). A result like that is a reason to
keep a layer small and cheap, or to measure it on your own failures. It is not a reason to keep
every layer by default.

The worked example's decisions:

| Layer | Kit files | Decision | Why |
|---|---|---|---|
| Instructions | `AGENTS.md`, `ARCHITECTURE.md`, `docs/` | Kept, smaller | Six TeamTrack documents do not apply to a library |
| State | `progress.md`, `session-handoff.md`, `init.sh` | Kept | A feature can span sessions; `init.sh` is fast |
| Scope | `feature_list.json`, sandbox policy | Kept | One feature at a time; policy kept as reference |
| Verification | `harness/`, checklist, CI workflow | Kept | The layering check caught a seeded violation for free |

**Check it worked.** Write the decision in `docs/PLANS.md` with the date. Revisit it when an agent
makes a mistake that a dropped layer would have caught. The failure each part prevents is listed in
[skills/harness-setup/references/failure-modes.md](skills/harness-setup/references/failure-modes.md).

## When something goes wrong

| Symptom | Fix |
|---|---|
| `ERROR boltons clone not found` from `make_repo.sh` | Run the fetch command in "Before you start" first |
| `ERROR /tmp/bq-example already exists` | Pick a new folder |
| `x target directory not found` | Create the repository folder, or fix `--target` |
| `! skipped <file>` | Your file exists; merge by hand or pass `--force` |
| `--check` still lists markers you removed | Delete the whole marker line, not only its text |
| `ModuleNotFoundError: No module named 'shipharness_adapter'` | Run from the repository root with `PYTHONPATH=harness` |
| `check crashed: AttributeError: ... no attribute 'create_app'` | A dropped rule is still in `--rules` |
| `x OPENAI_API_KEY is missing` | Add the key to `.env` in the shipharness checkout |

More on the kit itself: [kit/README.md](kit/README.md). More on the skills:
[use-in-your-repo/](README.md).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 3: Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM),
  <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
- Source 4: Mutation-Guided LLM-based Test Generation at Meta (ACH),
  <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta), 2025-01-22
