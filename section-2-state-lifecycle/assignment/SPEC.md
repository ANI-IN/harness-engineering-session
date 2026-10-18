# Assignment 2: State and sessions. Specification: three forced stops, one consistent history

The full requirements for [Assignment 2](README.md). The README gives the story and the steps; this
page is the reference you check your work against.

> **Terms on this page**
>
> - **Work folder**: The folder you submit; `section-2-state-lifecycle/assignment/starter/` unless you pass `A2_IMPL=` to make.
> - **Forced stop**: The end of a session before the work is done: by its turn budget, or by the agent's `finish(claim="not_done")` once the harness stop step has run.
> - **Step ledger**: One line per ticket step, done or not, derived from git at every stop.
> - **Test stand-in agent**: A deterministic program, not a model, that plays the agent in the graded scenarios.
> - **Scenario**: One run of the real runner with your layer, the stand-in agent, and four sessions.
> - **Product file**: Any file except `progress.md`, `session-handoff.md`, `init.sh`, the feature list files, and `docs/exec-plans/`.
> - **Score record**: The file the referee writes for each run, with every measured result.
> - **Live evidence**: The files your real live run wrote, collected into `live/`.
> - **Session turn budget**: The fixed number of turns a session gets before the runner stops it.
> - **Referee**: The program that scores each run after the agent stops.
> - **Exec plan**: A plan file the agent keeps up to date as it works, with steps, decisions, and progress.
> - **Alembic head**: The newest migration in the chain; Alembic is the migration tool TeamTrack uses.
> - **Hidden tests**: Tests the referee runs that the agent never sees.
> - **Mutant**: A copy of the code with one small bug planted on purpose; good tests catch (kill) it.

> Your output will differ: the examples on this page come from the course's own starter, and commit
> hashes change on every run.

## Inputs

- `starter/a2_state/`: a layer that runs but writes nothing at a session stop. It already has the
  initializer step and the Getting up to speed routine of the class's state layer.
- `platform/src/shipharness/harness/state/`: the class's state layer. Build on its helpers:
  templates, `handoff.MachineSummary`, `handoff.merge`, `handoff.migration_heads`,
  `progress.session_entry`, safe file writes, and `commit_paths`.
- `a2_scenario/`: the scenarios, the mini repository, and the test stand-in agent. Do not edit it.

### The visible feature

Three steps, each with an id (`Feature.ticket()` in `a2_scenario/feature.py`):

```text
- S1 Comments table: one migration that creates the comments table, and app/comments/models.py
- S2 Comment service: app/comments/service.py and app/comments/validation.py
- S3 Index and tests: one migration that adds an index on comments.issue_id, and tests/visible/test_comments.py
```

### The test stand-in agent

`a2_scenario/literal_agent.py` follows fixed rules. It is not a recording: each call decides the
next tool call from the current session's transcript, so it reacts to what your layer wrote.

1. Every session starts with three reads, one turn each: `progress.md`, `session-handoff.md`, and
   `docs/exec-plans/active/<feature>.md`.
2. It learns only from those reads and from your resume text, line by line:
   - a line with `[x]` and a step id (`S2`) means that step is done;
   - otherwise, a line with a step id and the word `written` names files of that step that are
     already on disk; it will not write them again;
   - a line `Migration heads: 1 (<rev>)` gives the `down_revision` for a new migration. Without it,
     the agent uses the ticket's base revision, `0001`.

   It never infers progress from commit lines, file listings, or the ticket's step list.
3. It does the steps in order: one turn per file, then one turn for the step commit, with a subject
   that starts with the step id (`S1: Comments table`). When every step is done it runs the visible
   tests and calls `finish(claim="done")`.
4. It ignores the wrap-up message, unless the scenario gives it a behaviour for that session: write
   a note in the handoff, rewrite `progress.md`, or tick the next step in the plan before doing it.
5. Work it does not know about is done again: a new migration with a new revision id, and files
   rewritten with a different `# draft <n>` marker on every line.

## Files you must produce

In your work folder: `a2_state/layer.py`, `a2_state/ledger.py`, `a2_state/progress_log.py`, your
unit tests, and `live/`.

```text
my-a2/                       your work folder (a copy of starter/)
  a2_state/
    layer.py                 ResumableStateLayer (TODO 1-7)
    ledger.py                TODO 1a-1c
    progress_log.py          TODO 4
  live/                      written by the live step; do not edit
    task.jsonl               the four-session F2 task the run used
    command.txt              the wrapper command as run, and the shipharness command it ran
    output.txt               everything the run printed, with its Cost: line
    summary.json             A/B id, run ids, model, sessions and stops per arm, layer hash
    scores/<run_id>.json     the score record of each arm
```

After a scenario, the mini repository must show:

| File | What it must show |
|---|---|
| `migrations/versions/` | One head; a fresh `alembic upgrade head` works; no table created twice |
| git history | One `S<n>:` commit per step; nothing a session wrote rewritten later |
| `progress.md` | Six sections in order; one `- Session <n> ...` entry per session |
| `docs/exec-plans/completed/<feature>.md` | `[x]` per step with its commit; one line per session; an outcome |
| `session-handoff.md` | Last machine summary, `Migration heads: 1 (...)`, the agent's notes |
| working tree | Clean: every harness write committed |

The six `progress.md` sections, in order: `# Progress`, `## Current feature`, `## Done`,
`## In progress`, `## Next`, `## Session log`.

## Requirements

### The ledger

- **R-L1.** At every session end, read `git log` since `ctx.state["harness.setup_sha"]` and
  `git status --porcelain -uall` through `ctx.sandbox.exec`. Host code never runs git on the
  workspace.
- **R-L2.** A step is done when a commit subject starts with its id and a colon. The first such
  commit is the one that did it.
- **R-L3.** The first step that is not done is in progress when there are uncommitted product files.
  Those files are listed as written.
- **R-L4.** The ledger works for any feature whose steps have ids `S1`, `S2`, and so on. Nothing
  depends on the visible feature's file names or step count.

Ledger lines that work with the stand-in agent:

<!-- check-style: allow SC10 the ledger format names the commit that finished a step -->
```text
- [x] S1 Comments table: done in commit 615f2d2
- [ ] S2 Comment service: in progress; written but not committed: app/comments/service.py
- [ ] S3 Index and tests: not started
```

### The files at each stop

- **R-F1.** The exec plan's `## Progress` section is rebuilt from the ledger every time, plus one
  line per session so far with `Session <n>` and `ended by <reason>`. Lines the agent added there
  are not kept: it may tick a step it has not done.
- **R-F2.** `session-handoff.md` has the machine summary from `handoff.MachineSummary` plus the
  ledger lines. The summary names the session (`end of session <n>`) and gives the migration heads.
  The section `## Notes from the agent` stays exactly as the agent left it (`handoff.merge` does
  this).
- **R-F3.** `progress.md` gets one entry per session in the `progress.session_entry` format, with
  the session's own start and end commits and end reason. If the agent rewrote the file, the missing
  sections come back from the template, its text is kept, and the session log is rebuilt from your
  own list of entries.
- **R-F4.** One harness commit per stop for every file the layer wrote (`commit_paths`).

### Resume and completion

- **R-R1.** The resume text has the ledger lines, the next step, and a line
  `Migration heads: <head>`, where the head is the output of `handoff.migration_heads`.
- **R-R2.** `context_prefix` stays the same in every session: it is part of the cached prompt.
- **R-R3.** Once, when the last claim is done and a fresh ledger shows every step done: rebuild
  Progress, replace "Not finished yet." under `## Outcomes & Retrospective`, move the plan to
  `docs/exec-plans/completed/`, and commit `docs/exec-plans`.

## Self-check

| What | Command |
|---|---|
| The self-check | `make check-assignment-2` (another folder: `make check-assignment-2 A2_IMPL=<dir>`) |
| Without make, keeping the repositories | `uv run python section-2-state-lifecycle/assignment/check.py --impl <dir> --keep` |
| Tests of the provided code | `uv run python -m pytest -q -p no:cacheprovider section-2-state-lifecycle/assignment/tests` |

The self-check runs two visible scenarios. V1 (budgets 6, 6, 6, 5) stops right after a step commit.
V2 (budgets 5, 6, 6, 8) stops after a step's files are written but before its commit. With a correct
layer, both finish in session 4 and no session line shows `[REDO`.

On the unchanged starter, scenario V1 prints (lines cut where marked `...`):

```text
  session 2 (6 turns, ended by turn_budget): 3 reads, write S1 migrations/versions/c1a2_comments.py [REDO: S1 was committed in session 1], ...
...
  FAIL one_head: 4 heads: c1a2 (head) | c1a3 (head) | c1a4 (head)
...
  FAIL no_duplicate_table: comments created by c1a1_comments.py, c1a2_comments.py, c1a3_comments.py, c1a4_comments.py
...
Self-check: 2 of 28 checks pass.
```

The `one_head` detail shows the last three lines of `alembic heads`, so only three of the four heads
appear after the count. `check.py` exits 1 on any failing check; make reports that and exits 2.

### Grading criteria, item by item

Each scenario criterion is checked in 6 scenarios: V1, V2, and 4 hidden ones. The hidden scenarios
use other stop points, a four-step feature with two chained migrations, an agent that writes a note
and later rewrites `progress.md`, and an agent that ticks a step before doing it. A criterion's
points are multiplied by the share of scenarios that pass it.

| Criterion | Item | Points |
|---|---|---|
| A (13) | `finished`: three forced stops, `finish(done)` in session 4, tests pass, files exist | 13 |
| B (23) | `one_head`: exactly one Alembic head | 9 |
| | `fresh_upgrade`: `alembic upgrade head` works on an empty database | 9 |
| | `no_duplicate_table`: no table created by two migrations | 5 |
| C (18) | `no_redone_lines`: no session removes earlier lines (0%: all; under 30%: half) | 13 |
| | `steps_once`: each step committed exactly once | 5 |
| D (15) | `progress_sections`: six sections in order | 3 |
| | `session_log`: one entry per session, in order | 8 |
| | `history_consistent`: each entry's commits and end reason match the run | 4 |
| E (15) | `plan_completed`: moved to `completed/`, with an outcome | 5 |
| | `plan_ledger`: every step ticked with a commit whose subject starts with its id | 5 |
| | `plan_sessions`: a `Session <n> ... ended by <reason>` line per session | 5 |
| F (6) | `handoff`: last summary, `Migration heads: 1 (`, notes kept | 4 |
| | `clean_tree`: clean working tree at the end | 2 |
| G (10) | `live_run`: valid live evidence, all or nothing | 10 |

## Evidence to hand in

You run your final layer once, live, with the course model (`gpt-6-luna`), through the real runner,
the Docker sandbox, and the referee. The task is the comments ticket with one change: four build sessions with budgets
10, 10, 10, and 20 instead of two. Hidden tests, mutants, and the primary measure stay the same.

```bash
uv run python section-2-state-lifecycle/assignment/live/run_live.py --impl my-a2 --forced-stops
```

The wrapper writes `my-a2/live/task.jsonl`, registers your layer as the state layer, and runs
`shipharness ab` on that task with `--layers instructions,state --no-reviewer --purpose assignment`.
Both arms run and the referee judges both. Then it writes the other evidence files and ends with
`+ live evidence written` or a list of what is not valid. It never overwrites an existing
`live/summary.json`.

- **R-E1.** Every file under `live/` is present. Each `scores/*.json` is a valid score record with
  `checkpoint_sha` set, one per arm, named by its run id.
- **R-E2.** The run ids and the A/B id agree across `summary.json`, the score records, and
  `output.txt`. `command.txt` names the live task.
- **R-E3.** Both arms ran `gpt-6-luna` with budgets 10, 10, 10, 20. The harness arm had four build
  sessions and three `session_stop` events. Each of sessions 1 to 3 ended by the turn budget, or by
  the agent's own `finish(claim="not_done")` with the harness stop step run for that session: the
  handoff (`session-handoff.md`) and `progress.md` written and committed before the next session.
- **R-E4.** `recorded` is false and `sandboxed` is true in both records.
- **R-E5.** Each arm's cost is at most the run cap ($0.20), and the `Cost:` line is at most the
  command cap ($2.50), both from `platform/src/shipharness/config/settings.py`.
- **R-E6.** The harness record lists the `state` layer, and `summary.json` holds a sha256 of your
  `a2_state/*.py` that matches the folder you submit.

An agent-ended session counts as a stop only when the harness stop step ran: the check reads the
session's `session_stop` event, the state layer's note that it wrote the handoff and `progress.md`,
and the new commit the next session starts from. The run does not count when one of sessions 1 to
3 ends any other way (a time limit, `finish(claim="done")`, an error), when the stop step left no
handoff commit, or when a cap stops the run before session 4. Move `live/` away and run again. The
check reads files only: it never runs a model and needs no keys.

## Limits

- Edit only your work folder's `a2_state/`. Do not edit `a2_scenario/`, `check.py`, `live/run_live.py`,
  or anything under `platform/`.
- No model calls and no network in the layer. Run git in the sandbox, and write workspace files with
  `shipharness.harness.state.files`.
- Run the live step last. Changing `a2_state/` afterwards breaks the hash, and `live_run` fails.

### Cost and trace budget

| Step | OpenAI | LangSmith traces |
|---|---|---|
| Self-check, scenarios, unit tests | $0 | 0 |
| The live step: one A/B, two arms, no review | At most $0.40 (two runs at $0.20) | 4 |

### Common mistakes

- Trusting the exec plan or `progress.md` as written. The agent may tick a step it has not done.
  Rebuild from git every time.
- Listing only committed work. A stop between "files written" and "commit" needs a `written` line,
  or the next session rewrites the files.
- Appending the log entry to whatever `progress.md` holds. After the agent rewrites the file, the
  earlier entries are gone. Keep your own list.
- Forgetting to commit the plan at each stop, or the move at the end (`clean_tree`).
- Moving the plan on the claim alone. The move needs the claim and every step committed.
- Taking the head from the last commit. Call `handoff.migration_heads` on the workspace at every
  stop, so an uncommitted migration counts.
- Hard-coding `S1` to `S3` or the comments file names. A hidden feature has four steps.
