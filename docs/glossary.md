# Glossary

Every term used across the curriculum, defined once. Other documents link here
instead of re-defining. One term per concept; synonyms are treated as drift
and removed.

## Core model

**Module**: this repository, and the unit of teaching it is. A module
covers one subject to a defined depth and can be taught in one sitting; a
course is a sequence of modules. Everything here is one module on harness
engineering, so its own prose says "this module", never "this course". The
only place "course" is correct is a reference to the external reference
course this module was modeled on.

**Harness**: the execution system built around a model so that its capability
becomes reliable execution: the instructions, tools, environment, state, and
feedback an agent works inside. A harness does not make the model smarter; it
makes the model's work verifiable, resumable, and bounded.

**The five subsystems**: the decomposition this module uses for every
harness:

1. **Instructions**: what the agent is told: entry files (`AGENTS.md`,
   `CLAUDE.md`), topic documents, specs.
2. **Tools**: what the agent can do: commands, scripts, permissions.
3. **Environment**: where work happens: the repository, runtimes,
   dependencies, initialization.
4. **State**: what persists across steps and sessions: `feature_list.json`,
   `claude-progress.md`, `session-handoff.md`, git history.
5. **Feedback**: how the agent finds out whether it worked: tests, checks,
   logs, verification commands.

**Agent**: a model plus a harness executing multi-step work. In this
curriculum's runnable units, model calls are replaced by the
**deterministic fake agent** (below) so everything runs offline.

**Deterministic fake agent**: a scripted stand-in for a model that replays
recorded decisions or applies fixed rules, so demos and projects are
reproducible, offline, and CI-safe. Every unit that uses one documents the
plug point where a real agent plugs in.

## Harness artifacts

**`AGENTS.md`**: the agent-facing entry file: a short router stating what the
system is, the startup workflow, hard rules, verification commands, and the
definition of done, linking to topic docs for depth. Kept deliberately short.
An entry file of roughly 100 lines is this module's working heuristic; the
split rule matters more than the number.

**`CLAUDE.md`**: the same contract voiced for Claude Code, which loads this
file automatically. One contract, two entry files.

**`init.sh`**: the initialization script run at session start. It installs
dependencies, verifies the environment, and prints the next command.
Initialization is a phase of its own, not something mixed into feature work.

**`feature_list.json`**: the machine-readable scope and state of the work:
one entry per feature with behavior, verification command, status, and
evidence. Validated by `feature_list.schema.json`. It is a harness
*primitive*: schedulers, verifiers, and handoff reports all read it.

**Feature status**: exactly four values, a fixed state machine:
`not-started` to `in-progress` to `passing`, with `blocked` reachable from
`in-progress`. `passing` requires evidence; there is no plain "done".

**`claude-progress.md`**: the session progress log: current verified state
plus one entry per session. The first thing a fresh session reads.

**`session-handoff.md`**: the compact end-of-session note: verified now,
changed, broken or unverified, next best step, commands.

**`clean-state-checklist.md`**: the exit gate a session must satisfy before
it may end: build passes, tests pass, progress recorded, no stray artifacts,
startup path works.

**`evaluator-rubric.md`**: the scorecard a checker fills in about a maker's
work, with per-category questions and an accept/revise/block verdict.

## Working discipline

**Evidence-based completion**: a task counts as done only when an executable
check passed and the evidence (command plus result) is recorded. An agent's
claim of completion is an input to verification, never a substitute for it.

**Maker/checker split**: the role separation in which the entity that builds
(maker) is never the entity that decides the work is acceptable (checker).
The checker needs independent signals such as tests, logs, and rubrics, not
the maker's self-report.

**WIP=1**: at most one feature `in-progress` at a time. Scope control is
enforced by the feature list, not by asking the agent to focus.

**Scope surface**: the externalized statement of what a task may touch:
which features, which files. Work outside it is overreach by definition.

**Evidence**: the recorded command and observable result that justifies a
status claim (for example, `verify.sh exited 0 on 2026-08-27`). Prose about
the code is not evidence.

**Clean state**: the property that a session's end leaves the repository
runnable, verified, recorded, and free of debris, so the next session starts
from knowledge instead of archaeology.

**Session**: one contiguous run of an agent with one context window. Long
tasks span sessions; continuity comes from externalized state, not memory.

**Controlled-variable ablation**: evaluating a harness component by removing
exactly one component, re-running a fixed task set, and comparing results.
The module's method both for proving a component earns its place and for
simplifying harnesses over time.

**Progressive disclosure**: structuring instructions as a short entry point
that links to depth on demand, instead of one giant file. "Map, not manual."

**System of record**: the repository as the single authoritative source of
decisions, constraints, state, and verification standards. Anything not in
the repo does not exist for the agent.

## Verification machinery (this repository's own)

**Track**: one of the two implementation languages, Python or TypeScript.
Every runnable unit ships both; a learner follows one.

**Unit**: a directory with a `SPEC.md` contract and the standard shape
(fixtures, expected, two tracks, `verify.sh`): a lecture demo, an exercise,
or a project. See [conventions](./conventions.md).

**SPEC.md**: the shared contract both tracks implement: CLI surface, exit
codes, files read/written, expected output.

**Conformance**: the three-way diff (python vs `expected/`, typescript vs
`expected/`, python vs typescript) run by `tools/conformance/runner.py` over
every unit's `cases.json`. Divergence is a failing build.

**Normalization**: the defined transformation
(`tools/conformance/normalize.py`) after which "byte-identical" is measured:
LF endings, stripped trailing whitespace, canonical JSON, POSIX paths.

**Starter / solution**: the two committed states of every exercise and
project. The starter runs but fails `verify.sh` for the intended reason; the
solution passes. Both exist in both tracks, always.

**Doctor**: a readiness tool that checks substance, not existence, and
delivers its verdict through its exit code. Instances at three scales:
`make doctor` (toolchain pins), lecture 05's init-check (repository
readiness), and `kb workspace-check` (workspace readability). "The
doctor" in a unit's prose means that unit's instance.

**Workspace**: the directory an agent session works in, together with its
harness artifacts (router `AGENTS.md`, state files, docs). The committed
`harness/` directories are workspace seeds; project 02's
`kb workspace-check` grades a workspace's readability. Workspace is the
canonical term everywhere, including the harness artifact headers.

**Seam**: the boundary between two adjacent components in an assembled
path, where one component's output becomes the next one's input. A unit
check exercises one component and therefore crosses no seam, which is the
whole of its blind spot.

**Plug point**: the place in a runnable unit where a real model, shell, or
filesystem would sit and a deterministic stand-in sits instead, so the unit
runs offline. Every unit that uses a deterministic fake agent names its plug
point.

**Check layer**: an ordered group of checks that runs as one stage, where a
run stops at the first failing layer and reports the rest as not reached.
Lectures 08 and 09 both use it: static, then tests, then system. Distinct
from a component's **tier**.

**Tier**: a component's architectural position (ui, service, io), which says
where it sits in an application, not when it is checked.

**Seeded defect**: a bug placed in a fixture on purpose, whose exact symptom
and catching stage are declared in SPEC.md so both tracks fail identically.

## Loop and graph vocabulary

**Loop**: an agent invocation wrapped in automation: a goal, a verification
step, a stopping condition, and externalized loop state, repeated without a
human issuing each prompt.

**Maker-checker loop**: a loop whose iteration is maker work followed by an
independent checker verdict; only a checker pass advances or stops the loop.

**Graph**: the generalization of loops for multi-role work: nodes (agents or
deterministic steps), edges (including conditional routing and rollback
edges), shared state, and routing rules made explicit.

**Stopping condition**: the rule that decides whether a loop runs another
round, and the signal it reads. A condition wired to the maker's own report
stops when the maker says so; wired to the checker's verdict it stops when
the work is verified. The signal, not the rule, is what decides the outcome.

**Loop state**: the file a loop carries from round to round recording what
has been attempted and what it produced. It is what makes a loop different
from N independent retries: without it every round starts from the same
place and repeats the same work.

**Node**: one step in a graph, an agent or a deterministic function, that
reads a declared view of the shared state and returns the state it produced.
A node sees only the keys its declaration grants it, so it cannot depend on
another node's work by accident.

**Edge**: a declared transition from one node to the next. An unconditional
edge always fires; a conditional edge fires when the router's key holds a
particular value.

**Shared state**: the single structure passed along a graph's edges, which
every node reads a declared view of and writes back. It is the graph's only
channel: nodes do not call each other.

**Router**: the function that reads one declared key of the shared state and
returns which edge to take next. Keying a router on a field written by the
node it is judging is the defect a graph's structure cannot see, because the
graph is complete and every count is satisfied.

**Rollback edge**: the edge taken when a check fails, leading to a node that
undoes what the run wrote rather than continuing forward. Without one a
failed run stops mid-flight and leaves the work half applied.
