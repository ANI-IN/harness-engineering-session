# Assignment 2: State and sessions. Solution: three forced stops, one consistent history

This folder is the reference solution for [Assignment 2](../README.md): a finished
`ResumableStateLayer`, its unit tests, the captured checks, and the live run's evidence. This page
explains how it was built and why.

> **Terms on this page**
>
> - **Forced stop**: The end of a session before the work is done: by its turn budget, or by the agent's `finish(claim="not_done")` once the harness stop step has run.
> - **Step ledger**: One line per ticket step, done or not, derived from git at every stop.
> - **Test stand-in agent**: A deterministic program, not a model, that plays the agent in the graded scenarios.
> - **Product file**: Any file except `progress.md`, `session-handoff.md`, `init.sh`, the feature list files, and `docs/exec-plans/`.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Exec plan**: A plan checked into the repository, with its progress and its decisions.
> - **Live evidence**: The files your real live run wrote, collected into `live/`.
> - **Session turn budget**: The fixed number of turns a session gets before the runner stops it.

What is in this folder:

| Path | What it is |
|---|---|
| `a2_state/` | The layer: `layer.py`, `ledger.py`, `progress_log.py` |
| `tests/` | Unit tests of the ledger and the `progress.md` helpers |
| `class_s2_layer/` | The class's state layer under the name the grader loads, as a baseline |
| `captured/` | Real output of the self-check and the grade |
| `live/` | The evidence of the live step |

## The approach, step by step

At every session end the layer asks the repository what happened, and writes that where the next
session reads it.

1. **Collect the evidence.** `git log --reverse --format=%H%x09%s <setup>..HEAD` and
   `git status --porcelain -uall`, both through the sandbox. The harness's own files are left out,
   so only product files count as work.

2. **Derive the ledger.** A step is done when a commit subject starts with its id and a colon; the
   first such commit is the one that did it. The first step that is not done is in progress when
   product files are uncommitted, and those files are listed as written:

   ```python
   # section-2-state-lifecycle/assignment/solution/a2_state/ledger.py (lines 83-103)
   def derive_ledger(
       steps: list[TicketStep], commits: list[tuple[str, str]], uncommitted: list[str]
   ) -> list[StepStatus]:
       """`commits` oldest first. The first commit for a step is the one that did it."""
       done: dict[str, str] = {}
       for sha, subject in commits:
           match = _STEP_SUBJECT.match(subject)
           if match and match.group(1) not in done:
               done[match.group(1)] = sha[:7]
       ledger: list[StepStatus] = []
       current_seen = False
       for step in steps:
           if step.id in done:
               ledger.append(StepStatus(step, "done", commit=done[step.id]))
           elif not current_seen and uncommitted:
               ledger.append(StepStatus(step, "in_progress", written=tuple(uncommitted)))
               current_seen = True
           else:
               ledger.append(StepStatus(step, "not_started"))
               current_seen = True
       return ledger
   ```

3. **Render it as checkbox lines.** One line per step: done with its commit, in progress with
   the files written but not committed, or not started (examples in
   [SPEC.md, "The ledger"](../SPEC.md#the-ledger)). The same lines go into the plan, the handoff,
   and the resume text, so every place the next session looks agrees.

4. **Rebuild the plan's Progress section.** The ledger, then one line per session:
   `Session <n> (<phase>) ended by <reason> after <turns> turns at commit <sha7> (<UTC time>)`.

5. **Write the handoff.** The class layer's `MachineSummary` (files changed, visible tests, last
   commits, TODO markers, migration heads) plus the ledger, merged with `handoff.merge`, which keeps
   the agent's notes as written.

6. **Rebuild `progress.md`.** The layer keeps its own list of session-log entries in the
   `progress.session_entry` format. `normalise_progress` restores missing sections from the
   template, keeps the agent's text, and writes the log from the layer's list.

7. **Commit once per stop**, then send the resume text: the ledger, the next step, and
   `Migration heads: <head>`.

8. **Finish once.** When the last claim is done and a fresh ledger shows every step done, the layer
   rebuilds Progress, writes the outcome, moves the plan to `docs/exec-plans/completed/`, and
   commits.

Everything else comes from the class's state layer: templates, safe file writes, the session-log
format, the machine summary, migration heads read as text, and sandboxed commits.

## Design choices and why

- **Evidence over claims.** The ledger comes from commits and the working tree, never from the files
  the agent edits. An agent that ticks a step early does no harm: the next stop rebuilds Progress
  from git. Anthropic's harness pairs the progress file with "the git history"
  ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)); taking
  the status from git alone is this course's choice.
- **The harness owns the plan's Progress section.** The agent's own words go to Surprises &
  Discoveries and the Decision Log, and the wrap-up message says so.
- **Uncommitted work is recorded, not committed.** At a stop between "files written" and "commit",
  the ledger lists the files as written and the next session commits them. The step's commit stays
  the agent's own `S<n>:` commit, so each step is committed once.
- **Session history in two places.** `progress.md` keeps the session log; the plan keeps one line per
  session too. The plan alone is then enough to restart from, as OpenAI's recipe asks
  ([Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans)).
- **Entries kept in memory.** The session log is rebuilt from the layer's own list, so an agent that
  rewrites `progress.md` cannot delete history.

## Alternatives considered

- **Harness commits of the agent's work at every stop.** Simpler to describe, but it mixes agent
  work into harness commits and leaves the step commit empty. The ledger would then need a map from
  files to steps.
- **Keep the agent's Progress lines and mark unproven ticks.** It keeps more of the agent's text,
  but adds a second grammar the next session must read correctly.
- **Parse earlier log entries back out of `progress.md`.** It survives a harness restart, but not an
  agent that rewrote the file before the stop.
- **A JSON state file.** Anthropic's team found the model "is less likely to inappropriately change
  or overwrite JSON files compared to Markdown files"
  (Source 1). The course keeps Markdown files as the workspace state, so the harness owns the parts that matter
  instead.

## Common mistakes this avoids

- No trust in what the agent wrote: every stop rebuilds the ledger from git.
- No lost uncommitted work: a `written` line names it, so the next session does not rewrite it.
- No lost history: the session log comes from the layer's list, not from the file.
- No dirty tree: the plan, the handoff, and `progress.md` are committed at every stop and after the
  move.
- No early move: the plan moves only when the claim is done and every step is committed.
- No stale head: `handoff.migration_heads` reads the workspace at every stop, so an uncommitted
  migration counts.
- Nothing hard-coded: the ledger reads step ids from the ticket, so a four-step feature works.

Limits that remain: commit subjects are written by the agent, so an agent can write `S3: ...`
without doing step 3; the ledger records what git says, not whether the step works. A ticket without
step ids gets an empty ledger, and the layer still writes the log, the plan's session lines, the
handoff, and the heads.

## Run and verify it

From the repository root. These commands need no keys and no Docker:

```bash
make check-assignment-2 A2_IMPL=section-2-state-lifecycle/assignment/solution
uv run python -m pytest -q -p no:cacheprovider section-2-state-lifecycle/assignment/solution/tests
```

> Your output will differ: commit hashes change on every run, and your own live run has its own
> ids, costs, and results.

The self-check prints, for scenario V1 (real output, cut where marked `...`; the full output is in
`captured/check-solution.txt`):

```text
Scenario V1-boundary-stops: each stop lands just after a step is committed (budgets [6, 6, 6, 5])
  session 1 (6 turns, ended by turn_budget): 3 reads, write S1 migrations/versions/c1a1_comments.py, write S1 app/comments/models.py, commit S1
  session 2 (6 turns, ended by turn_budget): 3 reads, write S2 app/comments/service.py, write S2 app/comments/validation.py, commit S2
  session 3 (6 turns, ended by turn_budget): 3 reads, write S3 migrations/versions/c3a3_comment_index.py, write S3 tests/visible/test_comments.py, commit S3
  session 4 (5 turns, ended by claim_done): 3 reads, run visible tests, finish done
  PASS finished: 3 forced stops, finished in session 4
  PASS one_head: 1 heads: c3a3 (head)
...
Self-check: 28 of 28 checks pass.
```

The unit tests print `7 passed`. The class's own state layer, graded the same way, redoes step 1
in every session: it never tells the next session which steps are done
(`captured/grade-class-s2-layer.txt`).

## Evidence

| File | What it holds |
|---|---|
| `captured/check-solution.txt` | The self-check on this folder |
| `captured/check-starter.txt` | The self-check on the unchanged starter |
| `captured/grade-solution.txt` | The instructor's grade of this folder |
| `captured/grade-starter.txt` | The grade of the unchanged starter |
| `captured/grade-class-s2-layer.txt` | The grade of the class's state layer |

The grade comes from `make grade-assignment-2 SUBMISSION=section-2-state-lifecycle/assignment/solution`,
which only the instructor can run; the grader is not in this repository.

### Live run evidence

The live step ran with this folder's layer, as in
[SPEC.md, "Evidence to hand in"](../SPEC.md#evidence-to-hand-in). Its files are in [live/](live/):
the task, the command, the full output, the run summary, and both score records.

The harness arm ran four build sessions, and the state layer wrote and committed a handoff at every
stop. The referee found no continuity failure. Sessions 1 and 3 ended by their turn budget. Session
2 ended on its last turn with the agent's own `finish(claim="not_done")`, and the stop step still ran
for it. Under the live step's rule, that counts as a forced stop
([SPEC.md, "Evidence to hand in"](../SPEC.md#evidence-to-hand-in)).
[live/README.md](live/README.md) shows how each session ended.

The grade is 100 out of 100 (`captured/grade-solution.txt`): every scenario criterion passes, and
the live criterion gives its 10 points. Dates and run ids are on the
[evidence page](../../../docs/evidence/s2.md#s2-a2-solution).

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Using PLANS.md for multi-hour problem solving, <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
