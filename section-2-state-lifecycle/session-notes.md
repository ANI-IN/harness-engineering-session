# Section 2: State and sessions. Session notes: what the agent remembers

For learners, after class. Reading time: about 8 minutes.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Session turn budget**: The fixed number of turns a session gets before the runner stops it.
> - **Context reset**: Clearing the context and starting a fresh session, with a handoff.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Continuity failure**: Two migration heads, a table created twice, or 30% or more of session 1's lines redone in session 2.
> - **Primary measure**: The one result, chosen before any run, that decides the comparison.
> - **Compaction**: Squeezing an old context into a short summary for the next session.
> - **Exec plan**: A plan file the agent keeps up to date as it works, with steps, decisions, and progress.
> - **Fast tier**: OpenAI's quicker, higher-priced service tier, used in the class profile.
> - **Hidden tests**: Tests the referee runs that the agent never sees.

## What we showed

| Block | What happened | Read it again |
|---|---|---|
| Launch | `make show-2 SESSION_BUDGET=12,38`, on the start slide: the harness arm alone on comments, live | [demo/README.md](demo/README.md) |
| Concepts | The problem, the files, the two routines, what we measured | [concepts.md](concepts.md) |
| Walkthrough | The layer in 40 lines: write the files, stop, merge the handoff, resume | [demo/walkthrough.md](demo/walkthrough.md) |
| Demo | The finished run on screens 1, 3, 5, 2, then the test-run results on screen 4 | [demo/README.md](demo/README.md) |

The class run's record stays on the instructor's machine. A captured run, with its screenshots, is in
[demo/expected/](demo/expected/README.md).

## Key ideas

1. **Every session starts with no memory.** "each new session begins with no memory of what came
   before." ([Anthropic, Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) What a
   session did exists for the next one only if it is in the repository.
2. **Compaction is not enough.** "However, compaction isn’t sufficient." A clean session plus a
   handoff is the alternative: a context reset
   ([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)).
3. **The state lives in a few files and git.** `init.sh`, `progress.md`, the exec plan, the
   handoff, and the commits. Each has one job.
4. **Two routines.** Getting up to speed at the start: read the git log and the progress file, run
   `init.sh` and a basic test. A commit and a progress update at the end.
5. **The harness writes the facts.** At every stop the state layer reads commits, changed files,
   tests, and migration heads from the repository. It works even when the agent wrote nothing.
6. **Two owners per handoff.** The harness owns the machine summary; the agent owns its notes.
   `merge` keeps both.
7. **The stop is a course mechanism.** A session turn budget makes the reset happen at turn 12, the
   same for both arms. Anthropic's team dropped resets for a later model, so treat the stop as a test
   setup, not a rule.
8. **State files cost turns.** "every component in a harness encodes an assumption about what the
   model can't do on its own, and those assumptions are worth stress testing."
   ([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps))

## What the result showed

Before class, the course ran both arms on the comments ticket with a 12-turn first session. The
primary measure: a run fails if it has a continuity failure. Runs failing, per arm:

| Setting | Bare arm | Harness arm |
|---|---|---|
| Medium effort | 0 of 3 | 0 of 3 |
| Low effort | 0 of 3 | 0 of 3 |
| Low effort, fast tier (class settings) | 0 of 1 | 0 of 1 |

Model gpt-6-luna ([evidence](../docs/evidence/s2.md#section-2)).

No measurable difference on this task with this model. Two things stand next to that result. In six
of the twelve arm runs at medium and low effort the agent built nothing, so there was nothing to
redo, and the measure passed. And those six runs exposed a runner bug: `finish(claim="not_done")` at
the end of session 1 ended the whole build phase. The fix applies to both arms, and the captured demo
run shows it working: session 1 ended that way, and session 2 still ran
([evidence](../docs/evidence/s2.md#s2-runner-fix)).

Measures chosen after the results, so they describe and do not test: over 9 runs per arm, harness
arms hit the agent time limit in 4 and bare arms in 0. Median arm wall time was 361 s against 232 s
([post hoc measures](../docs/evidence/s2.md#s2-posthoc)).

## Questions from class

**The harness did not win. Are state files useless?**
On this model and this ticket they changed nothing the referee measures, and they cost time. That is
a result about one bet. It does not cover longer tasks, other models, or people picking up the work.

**How did the bare arm cope without any files?**
In one test run its session 2 ran `git status`, found session 1's uncommitted migration, read it,
and carried on. The repository itself was enough state for that model.

**Is the harness arm not just given more information?**
No. Both arms get the same ticket, the same stop, the same wrap-up sentence, and the same resume
sentence. The harness arm gets files and text that organise what is already in the repository.

**Why does the harness write the summary, and not the agent?**
The agent writes notes in its last turns, and a session can end before those turns come. Commits,
changed files, and migration heads can be read at the stop, whatever the agent did.

**Does a PASS mean the feature works?**
No. It means session 2 did not break or redo session 1's work. Read the hidden-test count next to
it.

**Why counts and not percentages?**
Every run is a dot. With 1 or 3 runs per arm, a percentage hides how few runs there are.

## What to try next

1. Start [Assignment 2: State and sessions](assignment/README.md). Run `make check-assignment-2` first; on the unchanged
   starter it fails by design, and session 2 of scenario V1 redoes step 1.
2. Open the four files in [demo/harness/](demo/harness/README.md). Which line would have stopped
   the second migration in the opening story?
3. Read the agent's real notes in [demo/expected/session-1-notes.txt](demo/expected/session-1-notes.txt).
   What did it write down that a fresh session could not see in the code?
4. Read the [post-class readings](post-class-reading/README.md), about 15 minutes in total.
5. In your own repository, stop your agent in the middle of a task and start a fresh session. Watch
   its first five tool calls: does it find what the last session did?

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
