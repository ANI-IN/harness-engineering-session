# Section 2: State and sessions. Concepts: what the agent remembers

Reading time: about 15 minutes.

## The problem

**Illustrative scenario.** Marco's team runs TeamTrack, a multi-tenant issue tracker. He asks a
coding agent to add comments to issues: a `comments` table, three endpoints, and a panel on the
board. The work is too big for one session, which ends at its turn limit.

Session 1 writes the migration for the `comments` table and half of the endpoint. It does not
commit, and it leaves no note. Session 2 starts with an empty context and the same ticket. It sees
no working endpoint, so it starts again: it writes a new migration from the old head and rewrites
half of the endpoint.

Now the repository has two migration heads; the deploy stops. A reviewer untangles two
versions of one change, and Marco pays for the same work twice. The second session did not know
what the first one had done.

![A migration chain with one head, next to a fork where two migrations share one parent](diagrams/alembic-heads.svg)

*Two migrations with the same down_revision make two heads, and the migrations rule needs exactly one.*

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Harness layer**: One part of the harness: instructions, state, scope, or verification.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Session**: One run of the agent with one context window.
> - **Session turn budget**: The fixed number of turns a session gets before the runner stops it.
> - **Context reset**: Clearing the context and starting a fresh session, with a handoff.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Exec plan**: A plan checked into the repository, with its progress and its decisions.
> - **House rules**: TeamTrack's seven rules for every endpoint, from tenant isolation to migrations.
> - **Migrations rule**: House rule 7: Migrations. Exactly one Alembic head, and a fresh upgrade works.
> - **Alembic head**: The newest migration in TeamTrack's Alembic migration chain.
> - **Compaction**: Squeezing an old context into a short summary for the next session.
> - **Fast tier**: OpenAI's quicker, higher-priced service tier, used in class.
> - **Hidden tests**: Tests the referee runs that the agent never sees.
> - **Continuity failure**: Two migration heads, a table created twice, or 30% or more of session 1's lines redone in session 2.
>
> All terms: [glossary](../docs/glossary.md).

## The idea in one sentence

Keep what each session did and what comes next in files and git, write the facts from the
repository at every stop, and start every session by reading them.

## How it works

Anthropic's harness team states the problem of long tasks: "each new session begins with no memory
of what came before." The next session then has to guess at what happened
([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)).

Compressing the old context is not enough: "compaction isn’t sufficient." The same team's later
harness uses context resets instead: a fresh agent, "combined with a structured handoff that carries
the previous agent's state and the next steps"
([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).

The state lives in a few files, each with one job:

| Piece | What it holds | Source |
|---|---|---|
| `init.sh` | How to set up the app and run a basic test | Source 1 |
| `progress.md` | What each session did, and what is next | Source 1 |
| Git history | The changes, with messages | Source 1 |
| Exec plan | The plan, its progress, its decisions | Sources 3 and 4 |
| `session-handoff.md` | The last session's state and the next steps | Source 2 |

The exec plan comes from OpenAI ([Harness engineering](https://openai.com/index/harness-engineering/)).
Its recipe sets a high bar: "it should always be possible to restart from _only_ the ExecPlan and no
other work."
([Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans))

Two routines wrap the files. At the start, "Getting up to speed": read the git log and the progress
files, then run `init.sh` and a basic test, because a new feature on a broken app "would likely make
the problem worse." At the end: "End the session by writing a git commit and progress update."

![Session 1 stops at its turn budget, the harness writes the handoff, session 2 reads it first](diagrams/session-lifecycle.svg)

*Session 2 starts with an empty context; what it knows comes from the handoff, progress.md, and git.*

The course needs the stop at a known point in every run, so it uses a **session turn budget**: the
same fixed number of turns per session in both arms. It is the course's own mechanism; the context
reset happens at turn 12.

### Before and after

**Before: nothing to read.** Session 2 of the bare arm gets the ticket and one sentence from the
runner: "A previous session worked on this ticket and was stopped." The rest it must find itself.

**After: a handoff with two owners.** The harness arm finds `session-handoff.md`. The harness writes
its "Machine summary" at the stop: commits, files changed, visible tests, open TODO markers, and the
migration heads, with `there must be exactly one (House rule 7: Migrations)` when there are
two. The agent writes "Notes from the agent" in its wrap-up turns. These are real notes from a class-settings run, cut where
marked `...` (`F2` is the course's code for Feature 2: Comments on issues):

![session-handoff.md with a machine summary from the harness and notes from the agent](diagrams/handoff-contents.svg)

*The harness writes the facts from the repository; the agent's notes stay as written.*

> Your output will differ: run times, ids, and the agent's wording change on every run.

```text
## Notes from the agent

- What I was doing: Started F2 comments. Read `docs/features/f2.md`, relevant handbook rules in `docs/HANDBOOK.md`, and `.agents/skills/add-endpoint/SKILL.md`. `bash init.sh` passed (one head `0001_initial`, 16 tests).
- What is left: Implement comments table plus one migration, scoped repository/service/router (POST/GET nested on issues and DELETE by comment), idempotency and audit, seed four specified comments, board panel plus write form, and tests. ...
- What to watch out for: API/web must not import `app.db`; all customer queries must filter org. ...
```

Session 2 of that run read this file, `progress.md`, and the git log first, and wrote one migration.

## How shipharness does it

The state layer writes the four files before session 1, asks the agent to wrap up near the end of
each session, writes the facts at each stop, and sends the machine summary to the next session.

This is the code that runs at every stop:

```python
# platform/src/shipharness/harness/state/lifecycle.py (lines 100-111)
    ws: Path = ctx.workspace
    summary, tests = machine_summary(ctx, result, files_changed, timeout_s)
    template = (ASSETS / HANDOFF).read_text(encoding="utf-8")
    write_file(ws, HANDOFF, handoff.merge(read_text(ws, HANDOFF), template, summary).encode())
    log = read_text(ws, PROGRESS) or (ASSETS / PROGRESS).read_text(encoding="utf-8")
    entry = progress.session_entry(result, len(files_changed), tests, claim)
    write_file(ws, PROGRESS, progress.append_session_entry(log, entry).encode())
    commit_paths(
        ctx.sandbox,
        [HANDOFF, PROGRESS],
        f"harness: session {result.index} handoff for {ctx.spec.feature_id}",
    )
```

Two details matter. The summary comes from the repository, not from what the agent says, so it
exists even when the agent ran out of turns before writing notes. And `merge` replaces only the
harness's part of the handoff; the agent's notes stay as written. The
[walkthrough](demo/walkthrough.md) reads the rest of the layer.

One fairness rule applies: both arms get the same ticket, the same stop, the same "This session is
ending soon." message, and the same resume sentence. Only the files and the extra text differ.

## What we measured

Before class, the course ran both arms on the comments ticket with a 12-turn first session. The
primary measure: a run fails if it has a continuity failure.

| Setting | Bare arm: runs failing | Harness arm: runs failing |
|---|---|---|
| Medium effort | 0 of 3 | 0 of 3 |
| Low effort | 0 of 3 | 0 of 3 |
| Low effort, fast tier (class settings) | 0 of 1 | 0 of 1 |

![Dot chart for the comments ticket: every run of both arms passed](diagrams/results-s2.svg)

*One dot per run: all 7 runs of each arm passed, so there is no measurable difference.*

No measurable difference on this task with this model
([evidence](../docs/evidence/s2.md#section-2)), with two limits. First, a pass does
not mean the feature was built: in six of the twelve arm runs at medium and low effort, the agent
built nothing, and the measure cannot fail when session 1 leaves no code to redo. Second, those six
runs exposed a bug in the runner, not in the harness. A `finish(claim="not_done")` at the end of
session 1 ended the whole build phase, so session 2 never ran. The fix applies to both arms.

Measures chosen after the results, so they describe and do not test: harness arms hit the agent
time limit in 4 of 9 runs, bare arms in 0 of 9. The state files cost turns
([post hoc measures](../docs/evidence/s2.md#s2-posthoc)).

## When it helps, and when it does not

It helps when:

- A task is longer than one session, and sessions end before the work is done.
- The work leaves traces that are hard to find again, such as a decision.
- Several agents or people share a task.

It does not help, or helps less, when:

- The model already finds its own state. In one test run the bare arm ran `git status` and read the
  uncommitted migration before it wrote anything.
- The task fits in one session. The files then only cost turns.
- The stop never comes. If the agent finishes in session 1, there is nothing to hand off.
- The model changes. Anthropic's team dropped resets because "Opus 4.5 largely removed that
  behavior on its own" (Source 2).

The same source gives the test to apply: "every component in a harness encodes an assumption about
what the model can't do on its own, and those assumptions are worth stress testing." The state files
assume a fresh session cannot resume from the repository alone.

## Key takeaways

- Every session starts with no memory. If a session can end before the work is done, the next one
  must be able to pick up from files and git.
- Write the facts from the repository at every stop, and let the agent add notes. A handoff that
  depends only on the agent is empty exactly when the agent ran out of turns.
- State files cost turns. Check with a measure, such as the referee's continuity check, whether they
  pay off on your model and your tasks.

## Check your understanding

1. Session 2 of the bare arm has the whole repository. Why can it still write a second migration?

   <details>
   <summary>Answer</summary>

   Being in the repository is not being noticed. If session 2 does not run `git status` or read
   the migrations folder first, it works from the ticket alone and starts from the old head.

   </details>

2. Why does the harness write the machine summary itself, instead of asking the agent for it?

   <details>
   <summary>Answer</summary>

   A session can end before the agent's wrap-up turns come. Commits, changed files, and migration
   heads can be read from the repository at the stop, whatever the agent did.

   </details>

3. A run passes the continuity check with 3 of 56 hidden tests. What does the pass tell you?

   <details>
   <summary>Answer</summary>

   Only that session 2 did not break or redo session 1's work. Here session 1 left almost no code,
   so there was nothing to redo. The hidden-test count says the feature was not built.

   </details>

## Further reading

- [Working in shifts](post-class-reading/01-effective-harnesses-for-long-running-agents.md):
  the initializer, the progress file, and the session routine.
- [Harness design: context resets and handoffs](post-class-reading/02-harness-design-context-resets.md):
  resets against compaction, and why they depend on the model.
- [Exec plans](post-class-reading/03-exec-plans.md): a plan the next session can restart from.

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 3: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 4: Using PLANS.md for multi-hour problem solving, <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
