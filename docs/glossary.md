# Glossary

Every term and abbreviation this course uses, in plain words. Pages still spell out a term the
first time they use it; come here when a word is new or you forgot it. The course names
(sections, assignments, features, house rules, filters) come first, then every other term from A
to Z.

## Course names

Pages write a name in full the first time, such as "Feature 4: Version checks on issue edits", and
then the short form, "Feature 4". The short codes in the right-hand column appear only in code:
commands, file names, logs, console screens, and captured output.

### Sections and assignments

| Name | What it covers | Code |
|---|---|---|
| Section 1: Instructions | What the agent knows: a short map and focused documents | `S1` |
| Section 2: State and sessions | What survives a session stop: progress file, plan, handoff | `S2` |
| Section 3: Scope and sandbox | What the agent may change and reach: allowed paths, a container | `S3` |
| Section 4: Verification | What proves the work is done: the gate, test filters, hidden tests | `S4` |
| Assignment 1: Instructions | Turn an 899-line instruction file into a map, documents, and a skill | `A1` |
| Assignment 2: State and sessions | A state layer that survives three forced stops | `A2` |
| Assignment 3: Scope and sandbox | A diff-scope policy, a `passes` gate, a sandbox rule | `A3` |
| Assignment 4: Verification | A soft-delete check, a sixth test filter, a live run, a portfolio | `A4` |

`A1` to `A4` mean the assignments only in file and command names (`make check-assignment-1`). On
the evidence pages, `A1` to `A7` and `B1` to `B14` are ids of sources, not assignments.

### Features

The features of TeamTrack that a ticket asks the agent to build. Commands take the readable alias
or the code: `make demo-3 FEATURE=version-checks`.

| Name | Command alias | Code |
|---|---|---|
| Feature 1: Org-wide issue search | `org-search` | `F1` |
| Feature 2: Comments on issues | `comments` | `F2` |
| Feature 3: Safe retries for issue creation | `safe-retries` (or `idempotent-create`) | `F3` |
| Feature 4: Version checks on issue edits | `version-checks` | `F4` |
| Feature 5: Bulk close | `bulk-close` | `F5` |
| Feature 6: Watchers | `watchers` | `F6` |
| Feature 7: Labels | `labels` | `F7` |

Features 1 to 4 belong to Sections 1 to 4. The final project picks from Features 5 to 7.

### House rules

The rules TeamTrack wants every change to follow. Each has a check that prints how to fix a
violation.

| Name | What it says | Code |
|---|---|---|
| House rule 1: Tenant isolation | Another org's resource answers 404, never 403 | `R1` |
| House rule 2: Roles | Viewers cannot write; some writes are admin-only | `R2` |
| House rule 3: API conventions | List and error envelopes, and the right status codes | `R3` |
| House rule 4: Safe retries | A create honours the `Idempotency-Key` header | `R4` |
| House rule 5: Audit log | One audit row for every write | `R5` |
| House rule 6: Layering | The API layer never imports the database layer | `R6` |
| House rule 7: Migrations | One Alembic head; upgrades work on an empty database | `R7` |
| House rule 8: Deleted issues stay hidden | A soft-deleted issue never shows on any endpoint | `R8` |

House rule 8 is the check you write in Assignment 4.

### Test filters

A test the agent writes in the test phase is kept only if it passes every filter. Section 4 uses
Filters 1 to 5; Assignment 4 adds Filter 6: No duplicate tests.

| Name | A kept test must |
|---|---|
| Filter 1: Builds and collects | Import and be found by pytest |
| Filter 2: Passes five runs | Pass five runs in a row on the same code (not flaky) |
| Filter 3: Adds coverage or catches a mutant | Cover new lines, or fail on a planted bug |
| Filter 4: Real assertions | Assert something real, not `assert True` |
| Filter 5: No source changes | Leave the app's code alone; only tests change |
| Filter 6: No duplicate tests | Differ from every other kept test, not only in names |

## Terms A to Z

- **A/B**: Bare arm and harness arm on the same ticket, scored the same way.
- **Ablation**: Removing one harness layer and running again, to see what that layer was worth
  (`make demo-2 LAYERS=-state`).
- **Adapter**: The file that tells `shipharness check` where your app's routes, models, and rules
  live.
- **Agent Skill**: A folder with a `SKILL.md` recipe that the agent loads only when a task needs it.
- **Agent time limit**: The most time one arm's agent may work (`RUN_TIMEOUT_S`: 300 s, or 420 s in
  the class profile). An arm that reaches it ends as `ABORTED: timeout`.
- **Alembic head**: The newest migration in Alembic's chain of database migrations. A healthy
  history has exactly one; two heads block an upgrade.
- **Allowed paths**: The file patterns a ticket lists for each phase: the files the agent may change
  then.
- **Arm**: One agent run in an A/B. The bare arm has no harness; the harness arm has it.
- **Audit log**: A table with one row per write that says who changed what.
- **Bare arm**: An agent run with the ticket and the repository, and no harness.
- **Baseline**: The results on the unchanged app, recorded once, so later checks count only new
  problems.
- **Blinded reviewer**: A separate model that reads a diff without knowing which arm wrote it.
- **Block**: A patch the scope layer refuses before anything is written; the agent sees `BLOCKED`.
- **Build phase**: The first phase of a run, in which the agent writes the feature.
- **Build tier**: The first paid OpenAI usage tier, reached with $5 of credit; the agent model needs
  it.
- **bwrap and seccomp**: Linux tools that limit which files and system calls a process may use.
- **Cap**: The most money a run, a review, a session, or this machine may spend on model calls. A
  call that would cross a cap is refused (see [costs](costs.md)).
- **Checkpoint tag**: A git tag such as `m1-s1-start` that marks the repository state at the start
  of a section.
- **Class date**: The class day in `.env` (`SHIPHARNESS_CLASS_DATE`). It names the LangSmith project
  and keys the session cap.
- **Class profile**: The settings the live class runs use, the same for both arms: low reasoning
  effort, the Fast tier, 2 CPUs per container, a 420 s agent time limit, and a 900 s harness work
  limit.
- **Clean state**: All work committed, ruff clean on changed files, one migration head, no debug
  output.
- **Compaction**: Squeezing an old context into a short summary so the session can go on.
- **Console**: The browser page that shows a run live, on five screens (`make console`).
- **Constructed example**: A run driven by scripted steps instead of a model; it costs nothing and
  never counts as a result (`make example-N`).
- **Context prefix**: The fixed text block sent at the start of every agent session.
- **Context reset**: Ending a session and starting a fresh one that reads its state from files.
- **Continuity failure**: Two migration heads, a table created twice, or 30% or more of the first
  session's lines redone by the next one.
- **Cost line**: The `Cost:` line every live command prints at the end: this command, the session,
  and the build total.
- **Doctest**: An example in a docstring that runs as a test.
- **Done claim**: The agent's call `finish(claim="done")`, which says the phase's work is complete.
- **Embeddings**: Number vectors that stand for a text's meaning, so similar texts can be found.
- **ETag**: A response header that names the version of a record, for example `"1"`. Feature 4
  adds it to issues.
- **Exec plan**: A living plan file for one long change, with its steps, decisions, and progress.
- **Experiment export**: The JSON file a run writes for each arm, listing its runs and scores.
- **Fast tier**: OpenAI's quicker, higher-priced service tier, used in the class profile.
- **Feature list**: `feature_list.json`, which lists each feature with a `passes` field; the
  harness, not the agent, sets it.
- **Flaky test**: A test that sometimes passes and sometimes fails on the same code. The referee
  runs each shipped test five times to find one.
- **Full verdict**: The primary verdict plus every other check: hidden tests, mutants, and review.
- **Gate**: The checks that run when the agent says done; the agent does not control them, and a
  failure sends the claim back. Also called the verify gate. On the evidence pages, "gate" also
  means the pass mark the test runs had to reach before larger batches would run.
- **Glob**: A path pattern; `**` spans folders.
- **Harness**: The files and code around the agent that decide what it sees and what it may do.
- **Harness arm**: The same run as the bare arm, with the harness turned on.
- **Harness in action**: The harness arm alone, live, scored by the referee (`make show-N`). It is
  not an A/B, so it stays out of every comparison.
- **Harness layer**: One part of the harness: instructions, state, scope, or verification.
- **Harness note**: A line a layer adds to console screen 1, such as "agent read ARCHITECTURE.md".
- **Harness work limit**: The most time the harness's own work may take in one arm: handoff test
  runs, gates, and test filters (`HARNESS_TIMEOUT_S`: 120 s, or 900 s in the class profile).
- **Held-out tests**: Another name for hidden tests.
- **Hidden tests**: Tests the agent never sees; the referee runs them after the agent stops.
- **Idempotency**: Sending the same request twice has the same effect as sending it once.
- **Idempotency key**: An id the client sends with a create request, so a retried request does not
  create a duplicate (House rule 4).
- **If-Match**: A request header that carries the ETag the client read. The server refuses the edit
  with 412 if the record changed since.
- **Import-linter**: A tool that fails when code imports across a forbidden layer boundary.
- **k**: The number of tries per arm and task; k=1 is one try.
- **LangSmith**: The tracing service that records every model call of a run. Its ordinary traces
  expire after 14 days, so copy the links you need.
- **Least privilege**: Only the access the task needs.
- **Ledger**: `.shipharness/ledger.jsonl`, one line per model call with its model, tier, and cost.
- **Lost update**: One edit silently overwriting another made at the same time.
- **Map**: A short `AGENTS.md` that says where each rule lives, instead of holding every rule.
- **Migration head**: Another name for the Alembic head.
- **Mutant**: A copy of the code with one small bug planted on purpose; a good test fails on it
  (it "kills" the mutant).
- **Optimistic concurrency**: An edit carries the version it read, and the server refuses it if
  the record changed since.
- **Org**: One customer organisation in TeamTrack; also called a tenant.
- **Out-of-scope file**: A file in the shipped diff that matches none of the allowed paths.
- **pass^k**: Passing on all k tries of the same task, not just on one.
- **Phase**: One stage of a run: build (write the feature), then test (add tests only).
- **Pill**: A status badge on console screen 1, such as the primary verdict or one gate check.
- **Post hoc**: Chosen after the results were known. A post hoc number is a real count, but it can only describe what happened, not confirm a prediction.
- **Primary measure**: The one question a section's A/B answers, fixed in writing before any run.
- **Preview container**: The container that runs an arm's app so console screen 2 can show its
  board, with a new screenshot every 5 s.
- **Primary verdict**: The referee's answer to the primary measure for one arm: PASS or FAIL.
- **Probe**: A request the referee sends to test one house rule on one endpoint.
- **Progressive disclosure**: The agent first sees a short description and opens the full
  instructions only when it needs them.
- **Purpose**: The make variable that picks the LangSmith project and the cost session: `class`,
  `pilot`, or `assignment`.
- **Reasoning effort**: How long the model thinks before it answers (low, medium, high).
- **Recording**: A run shown again by `make replay`; every screen carries a `RECORDING` badge.
- **Referee**: The program that scores each run after the agent stops.
- **Referee mutants**: Mutants the agent never sees; the referee counts how many the shipped tests
  catch.
- **Referee set**: Mutants held back from test generation and used only to judge the kept tests.
- **Registered**: Fixed in writing before any run, so the result cannot shape the question.
- **Regression oracle**: The reference for correct behaviour: the current code's results, which new
  tests must match.
- **Regression tests**: Tests that guard the behaviour the code has today.
- **Replay**: Showing a recorded run again and judging it again, with no model calls.
- **Revert**: The scope layer undoing a command's changes outside the allowed paths; the agent sees
  `REVERTED`.
- **Reward hacking**: Passing the visible checks without doing the task they stand for.
- **Sandbox**: The container the agent's commands run in, with no network and only the files it may
  use. It is the same for both arms.
- **Session**: One stretch of agent work that starts with a fresh context; a long task spans several
  sessions.
- **Session cap**: The most all commands under one class date or one purpose may spend together
  (`MAX_SESSION_COST_USD`, $2.50).
- **Session turn budget**: The fixed number of turns a session gets before the runner stops it
  (`SESSION_BUDGET=12,38`).
- **Service tier**: OpenAI's speed and price level for a request; this course uses Standard and
  Fast.
- **Skill**: See Agent Skill.
- **Soft delete**: Marking a row as deleted (a `deleted_at` time) instead of removing it.
- **Standard tier**: OpenAI's ordinary service tier, at the base price; the reviewer never asks for Fast.
- **Stopwords**: Common words such as "the" that a text comparison ignores.
- **Structured handoff**: A file that carries the last session's state and the next steps to the
  next session.
- **Swap test**: Scoring a recorded A/B again with the arm labels swapped; the scores must not
  change (`make swap-N`).
- **Tenant**: One customer organisation (org) in an app that serves many; tenant isolation keeps
  each org's data apart.
- **Test filters**: The checks a test from the test phase must pass to be kept (table above).
- **Test phase**: A short second phase in which the agent writes tests for the feature it built.
- **Ticket**: The task the agent gets, written like a work ticket.
- **Trace**: The recorded steps of a run, each model call and tool call, in LangSmith.
- **Turn**: One model reply, with the tool calls it makes.
- **Turn budget**: The most turns a session may use before the runner stops it.
- **UNSANDBOXED**: The label on a run whose commands ran on your machine instead of in the sandbox;
  its results are not official.
- **Verify gate**: See gate.
- **Walkthrough anchor**: A marker such as `S4:gate` in the code that a walkthrough page points to.
- **WSL2**: Windows Subsystem for Linux: Ubuntu running inside Windows, where every course command
  runs on a Windows machine.
