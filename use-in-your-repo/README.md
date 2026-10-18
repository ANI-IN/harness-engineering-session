# Module 1: Harness Engineering for Coding Agents - Use it in your repository

## The problem

**Illustrative scenario.** Your team starts handing tickets in your own repository to a coding
agent. The conventions live in a wiki and in reviewers' heads. The agent copies the oldest handler
it finds, including a pattern your team stopped using. The next session redoes yesterday's
half-finished change. A small fix edits shared configuration. The agent reports done on work its
own tests barely touch. You decide you need a harness, but you start from an empty folder, and you
cannot tell which pieces will be worth keeping.

The cost: review time on every agent change, incidents the reviews miss, and harness work that may
or may not pay for itself.

> **Terms on this page**
>
> - **Harness**: the files and code around the agent that decide what it sees and may do.
> - **Harness layer**: one part of the harness: instructions, state, scope, or verification.
> - **Map**: a short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **House rule**: a team convention written as one checkable sentence, with a check that finds violations.
> - **Agent Skill**: a folder with a `SKILL.md` recipe that the agent loads only when a task needs it.
> - **REPLACE marker**: a line in a kit template that says what to write in place of the example value.

## Why it happens

- A rule the agent cannot see does not exist for it: "From the agent’s point of view, anything it
  can’t access in-context while running effectively doesn’t exist."
  ([Harness engineering](https://openai.com/index/harness-engineering/))
- Sessions do not remember each other: "each new session begins with no memory of what came
  before." ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents))
- Agents grade themselves kindly: "agents reliably skew positive when grading their own work."
  ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps))

## How this section fixes it

This folder replaces the empty folder with the harness you saw on TeamTrack, ready to copy:

- **The starter kit**: the map and the docs it points to, the session files, the feature list and
  its schema, house-rule checks, a sandbox policy, and a CI workflow. `shipharness init` copies it
  with no model calls. Every template holds TeamTrack's real values, with a REPLACE marker next to
  each one.
- **Four Agent Skills**: harness-setup, assured-tests, house-rules, and skill-template, for Claude
  Code, Codex, and Cursor.
- **The guide**: seven steps from install to deciding which layers earn their place, worked through
  on a small real library with captured output.

Measure before you keep a piece. On TeamTrack, the course found no measurable difference for the
instructions, state, and verification layers on their primary measures. With the scope layer on,
the agent kept to the allowed files in 3 of 3 runs of one ticket; without the harness, it did in 0
of 3 ([evidence](../docs/evidence/final.md#use-in-your-repository)). Your repository and your model
may differ. The source behind the map says the same of its own results: they "should not be assumed
to generalize without similar investment—at least, not yet"
(Source 1).

## How to work through this section

Work in this order. Steps 1 to 4 of the guide make no model calls.

| Part | What it gives you | Model calls |
|---|---|---|
| [apply-to-your-repo.md](apply-to-your-repo.md) | The guide: install, copy, fill, check, run, read, decide | Only step 5 |
| [kit/](kit/README.md) | The templates, where each comes from, and the REPLACE markers | None |
| [kit/examples/boltons-queueutils/](kit/examples/boltons-queueutils/README.md) | The worked example after filling | None |
| [skills/harness-setup/](skills/harness-setup/README.md) | Assess a repository's harness; fill the gaps | Your agent's |
| [skills/house-rules/](skills/house-rules/README.md) | Turn a convention into a rule, a check, and a test | Your agent's |
| [skills/assured-tests/](skills/assured-tests/README.md) | Generate tests; keep only those that pass Filters 1 to 5 | Your agent's, plus testgen |
| [skills/skill-template/](skills/skill-template/README.md) | Start a skill of your own | Your agent's |

The quickest start, from your shipharness checkout, copies the kit into your repository and lists
what is left to fill. Replace `~/my-repo` with your repository's path:

```bash
uv run shipharness init --target ~/my-repo
uv run shipharness init --check ~/my-repo
```

## Where next

- New to the course? Run the TeamTrack demos first, starting with
  [Section 1: Instructions](../section-1-instructions/README.md) of Module 1.
- Ready for your own code? Follow [apply-to-your-repo.md](apply-to-your-repo.md) from step 1.
- Building your portfolio? The [final project](../final-project/README.md) shows how the kit feeds
  Assignment 4: Verification.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 3: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
