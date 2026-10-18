# Section 3: Scope and sandbox. Session notes: what the agent may change and reach

For learners, after class. Reading time: about 8 minutes.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **A/B**: Bare arm and harness arm on the same ticket, scored the same way.
> - **Referee**: The program that scores each run after the agent stops.
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.
> - **Out-of-scope file**: A file in the shipped diff that matches none of the allowed paths.
> - **Feature list**: `feature_list.json`, the one feature of the run and its `passes` field.
> - **Sandbox**: The container every tool command runs in, the same for both arms.
> - **Primary measure**: The one result, chosen before any run, that decides the comparison.
> - **Hidden tests**: Tests the referee runs that the agent never sees.
> - **Mutant**: A copy of the code with one small bug planted on purpose; good tests catch (kill) it.

## What we showed

| Block | What happened | Read it again |
|---|---|---|
| Launch | `make demo-3 FEATURE=version-checks`, on the start slide: both arms on the version checks ticket, live | [demo/README.md](demo/README.md) |
| Concepts | The problem, the four scope rules, the sandbox, what we measured | [concepts.md](concepts.md) |
| Walkthrough | The layer in 34 lines: decide a path, block, revert, count | [demo/walkthrough.md](demo/walkthrough.md) |
| Demo | The finished A/B on screens 1, 3, 5, 2, then the dots on screen 4 | [demo/README.md](demo/README.md) |

The class run's record stays on the instructor's machine. A captured A/B, with its screenshots, is
in [demo/expected/](demo/expected/README.md).

## Key ideas

1. **Scope in a ticket is a request.** The bare arm reads the same allowed paths as text. Nothing
   checks them, so the agent's judgement decides, and the handbook even points to the shared errors
   module.
2. **Strong words make a bad edit rarer, not impossible.** Anthropic's harness wrote "It is
   unacceptable to remove or edit tests" and chose JSON because the model is "less likely" to
   overwrite it ([Anthropic, Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)).
3. **Enforce the boundary, leave the method free.** In OpenAI's words: "enforce boundaries
   centrally, allow autonomy locally." ([OpenAI, Harness engineering](https://openai.com/index/harness-engineering/))
   The agent chose where to put its new error class; the harness only refused the shared file.
4. **Check before a patch and after a command.** A patch is checked path by path before it applies.
   A command can write anything, so a byte snapshot restores stray files after it runs.
5. **The harness owns `passes`.** The agent may not edit `feature_list.json` at all. It calls
   `finish`, and the harness sets `passes` from its own test run.
6. **The sandbox limits what any command can reach.** No network, a read-only root, and caps on
   memory, CPU, processes, and time, the same for both arms. It refuses with `sandbox_denied`; the
   scope layer refuses with `blocked`.
7. **Every harness piece is a bet.** "every component in a harness encodes an assumption about what
   the model can't do on its own, and those assumptions are worth stress testing."
   ([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)) The scope layer bets
   that the agent will leave the list unless code stops it.

## What the result showed

Before class, the course ran the class demo's A/B, on Feature 4: Version checks on issue edits,
three times with the class settings. It also ran Feature 3: Safe retries for issue creation ten
times. A run fails when its shipped diff has at least one out-of-scope file.

| Ticket | Bare arm: runs failing | Harness arm: runs failing |
|---|---|---|
| Version checks (the class demo) | 3 of 3 | 0 of 3 |
| Safe retries (retried creates never duplicate), all settings | 0 of 10 | 0 of 10 |

Model gpt-6-luna. On version checks the harness arm was ahead. Every bare arm changed the shared
`app/services/errors.py`; the scope layer blocked every harness arm on that same file, and each one
put the new error class in a file it was allowed to change
([evidence](../docs/evidence/s3.md#s3-confirmation)). On safe retries neither arm ever left the
list, so there was no measurable difference ([evidence](../docs/evidence/s3.md#s3-pilot)).

What the version checks result does not show: existing tests kept passing in every arm, so the stray
file broke nothing that was tested. No arm met the feature's own measure (every hidden test and every
mutant). Harness
arms passed fewer hidden tests in two of three runs, and every harness arm ended on the harness's own
120 s limit for harness work.

In scope is not the same as correct. In a `make demo-3` run on 2026-10-18 the harness arm stayed
in scope but shipped a board bug: every board save returned HTTP 500, because it added the
`version` form field to `create_issue` instead of `edit_issue`
([evidence](../docs/evidence/s3.md#s3-two-tab-check)). Its API-level hidden tests missed it, and
this section's harness has no verification layer. In Section 4: Verification, the gate, which
includes the board check, is what would catch it.

## Questions from class

**If the harness arm scores zero by construction, why run an A/B?**
For the bare arm. Its count shows how often the same agent, with the same ticket, leaves the list
when nothing checks it. On version checks that was every run.

**Was the bare arm's change wrong?**
Not by itself. Adding a 412 error class to the shared module follows the handbook's pattern, and the
existing tests kept passing. It was outside what the ticket allowed, so a reviewer of a shared module
never saw it. The count measures scope, not correctness.

**What does the verdict pill measure in this demo?**
Since 2026-10-18 the pill, the screen 4 dots, and the terminal line use the measure pre-registered for
the Section 3 confirmation: files changed outside the allowed paths, where 1 or more fails. The
version checks feature's own counts (hidden tests, referee mutants) follow as secondary results; no
arm met that bar in the test runs. Screen 3's diff map shows which file left the allowed paths.

**Why did the harness arm end `ABORTED: timeout` in the test runs?**
It hit `HARNESS_TIMEOUT_S`, the 120 s limit on the harness's own work per run, during session-end
work. The visible-test run that sets `passes` counts toward it. The agent's 420 s limit was not the
cause. The arm still shipped a change, and the referee scored it. Since 2026-10-18 the class profile
gives harness work 900 s, so in class the harness arm completes
([evidence](../docs/evidence/general.md#class-harness-limit)).

**What if the agent edits a stray file with `sed` instead of a patch?**
The scope layer compares the workspace with a snapshot after each command, restores files outside the
list, deletes new ones, and the tool result ends with `REVERTED`.

**Did the sandbox refuse anything?**
No command in any test run. The container is the same for both arms, so no run measures whether it
helps. The course keeps it on the sources' advice, for the run that goes wrong
([Anthropic, C compiler](https://www.anthropic.com/engineering/building-c-compiler)).

**Why counts and not percentages?**
Every run is a dot. With 3 runs per arm, a percentage hides how few runs there are.

## What to try next

1. Start [Assignment 3: Scope and sandbox](assignment/README.md). Run `make check-assignment-3` first; on the unchanged
   starter it fails by design, and each FAIL row says what to fix.
2. Open [demo/harness/scope-rules.txt](demo/harness/scope-rules.txt): the exact scope text the
   harness arm got. Which line would have stopped the bare arm's change, if code enforced it?
3. Print the class sandbox policy, with no model call and no container:
   `uv run python -c 'from shipharness.config import Settings; from shipharness.config.profiles import apply_profile; from shipharness.sandbox import default_policy, render_policy; print(render_policy(default_policy(apply_profile(Settings(), "class"))))'`.
4. Read the [post-class readings](post-class-reading/README.md), about 15 minutes in total.
5. In your own repository, write the allowed paths for your next agent task as globs. After the run,
   compare them with `git diff --name-only` and count the files outside the list.

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 3: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 4: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
