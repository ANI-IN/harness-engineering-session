# Section 1: Instructions. Session notes: what the agent knows

For learners, after class. Reading time: about 8 minutes.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Map**: A short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **Progressive disclosure**: A small entry point first; the details only when the task needs them.
> - **Context prefix**: The fixed text block sent at the start of every agent session.
> - **House rule 1: Tenant isolation**: another org's resource answers 404, never 403.
> - **Primary measure**: The one result, chosen before any run, that decides the comparison.

## What we showed

| Block | What happened | Read it again |
|---|---|---|
| Launch | `make show-1`, on the start slide: the harness arm alone on the org-wide issue search, live | [demo/README.md](demo/README.md) |
| Concepts | The problem, the map, progressive disclosure, what we measured | [concepts.md](concepts.md) |
| Walkthrough | The layer in 40 lines: copy the files, build the prefix, report reads | [demo/walkthrough.md](demo/walkthrough.md) |
| Demo | The finished run on screens 1, 3, 2, then the test-run results on screen 4 | [demo/README.md](demo/README.md) |

The class run's record stays on the instructor's machine. A captured run, with its screenshots, is in
[demo/expected/](demo/expected/README.md).

## Key ideas

1. **What is not in context does not exist for the agent.** "From the agent’s point of view, anything
   it can’t access in-context while running effectively doesn’t exist."
   ([OpenAI, Harness engineering](https://openai.com/index/harness-engineering/)) A rule in a file the agent
   never opens is not a rule for that run.
2. **Agents copy what they find.** "Codex replicates patterns that already exist in the
   repository—even uneven or suboptimal ones." TeamTrack's legacy `GET /v1/issues` lists every org's
   issues, next to the query the org-wide search must write.
3. **One big file is not the fix.** It crowds out the task, buries each rule among the others, goes
   stale, and cannot be checked by a script.
4. **AGENTS.md is a map.** About 100 lines, always in context, pointing to one focused document per
   topic in `docs/`. TeamTrack's map is 94 lines.
5. **Progressive disclosure, for docs and skills.** The map and the skill descriptions are always
   there. Documents and skill bodies load only when the task needs them
   ([Agent Skills Specification](https://agentskills.io/specification)).
6. **The prefix is fixed.** shipharness builds it from the course's copy, not the agent's workspace,
   so the agent cannot change what it is told.
7. **Reorganise, never add.** Every rule in the harness docs is also in the handbook both arms have.
   A unit test checks it, so the comparison stays fair.
8. **Every harness piece is a bet.** "every component in a harness encodes an assumption about what
   the model can't do on its own, and those assumptions are worth stress testing."
   ([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)) The map bets that
   the model will not apply a rule it was not pointed to.

## What the result showed

Before class, the course ran both arms on the same ticket, with the legacy query in the repository.
The primary measure: a run fails if it adds at least one new violation of the tenant isolation rule.
Runs failing, per arm:

| Setting | Bare arm | Harness arm |
|---|---|---|
| Medium effort | 0 of 3 | 0 of 3 |
| Low effort | 0 of 3 | 0 of 3 |
| Low effort, fast tier (class settings) | 0 of 1 | 0 of 1 |

Model gpt-6-luna. Effort is the model's reasoning effort (how long it thinks before it answers); the
fast tier is OpenAI's quicker, higher-priced service tier. Every arm passed 52 of 52 hidden tests
(tests the agent never sees) ([evidence](../docs/evidence/s1.md#section-1)).

No measurable difference on this task with this model. The map's bet did not pay off here because the
model did not need it: in the run with class settings, the bare arm did not open the handbook in its first
nine tool calls and still wrote an org-scoped query.

Measures chosen after the results, so they describe and do not test: over 10 runs per arm on this feature, harness
arms claimed done in 5 and bare arms in 9, with no false claim in either. Harness arms cost a little
more per run (median $0.0122 against $0.0103) ([post hoc measures](../docs/evidence/s1.md#s1-posthoc)).

## Questions from class

**The harness did not win. Was the map useless?**
On this model and this ticket it changed nothing the referee measures. That is a result about one
bet, not a verdict on maps. The test runs did not measure the maintenance reasons: one big file goes stale
and cannot be checked by a script. Keep a map where a measure on your model shows it helps, or for
those maintenance reasons, and say which.

**Is the harness arm not just given more information?**
No. The harness may change how knowledge is organised and delivered, never add facts. Both arms get
the same ticket, model, tools, turn budget (the most model turns a run may take), cost cap, and
sandbox (the container the agent works in).

**Why not paste the whole handbook into the prompt?**
A giant instruction file crowds out the task and the code. In OpenAI's words: "Too much guidance
becomes non-guidance." ([OpenAI, Harness engineering](https://openai.com/index/harness-engineering/))

**What does the agent see of a skill at the start?**
One catalogue line: its name, its description, and the path to `SKILL.md`. The body loads when the
agent opens it.

**Does the files-read list on screen 3 prove the harness worked?**
No. It shows which files the agent opened with `read_file`, which helps explain a result. The score is
what the referee finds in the shipped code.

**Why counts and not percentages?**
Every run is a dot. With 1 or 3 runs per arm, a percentage hides how few runs there are.

## What to try next

1. Start [Assignment 1: Instructions](assignment/README.md). Run `make check-assignment-1` first; on the unchanged
   starter it fails by design, and each FAIL line says what to fix.
2. Open `platform/teamtrack/docs/HANDBOOK.md` and `platform/teamtrack/harness/instructions/AGENTS.md`
   side by side. How many lines does an agent read before it reaches the tenant isolation rule in
   each?
3. Validate the course skill:
   `uv run shipharness skills validate platform/teamtrack/harness/instructions/.agents/skills`.
4. Read the [post-class readings](post-class-reading/README.md), about 15 minutes in total.
5. In your own repository, count the lines of your agent instruction file and list the three rules
   your agent breaks most often. Where does each live, and does anything point to it before the agent
   writes code?

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Agent Skills Specification, <https://agentskills.io/specification>, Agent Skills project, n.d.
- Source 3: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
