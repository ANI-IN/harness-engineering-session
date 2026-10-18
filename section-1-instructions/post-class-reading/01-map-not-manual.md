# [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)

Reading time: about 15 minutes.
Source: Ryan Lopopolo (OpenAI), [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/), 2026-02-11 ([evidence](../../docs/evidence/s1.md#src-openai-harness)).

> **Terms on this page**
>
> - **Map**: A short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **System of record**: The one place where a fact is kept and kept true; here, the `docs/` folder.
> - **Progressive disclosure**: A small entry point first; the details only when the task needs them.

## Why it matters

Every team that uses a coding agent writes instructions for it. Most start with one file and keep
adding to it. OpenAI's harness team did the same, watched it fail, and replaced it with a short map
and a checked `docs/` folder. This page sums up the two sections of their post that explain why:
"Agent legibility is the goal" and "We made repository knowledge the system of record".

## Three key ideas

1. **On disk is not in context.** "From the agent’s point of view, anything it can’t access in-context
   while running effectively doesn’t exist." A rule works only if it is in the repository and also
   reaches the agent's context while it works. TeamTrack's handbook meets the first condition for both
   arms; the map is there for the second.

2. **One big file fails in four ways.** It crowds out the task: "A giant instruction file crowds out
   the task, the code, and the relevant docs." Each rule loses weight among the others: "Too much
   guidance becomes non-guidance." It goes stale ("It rots instantly"), and no script can check it:
   "A single blob doesn’t lend itself to mechanical checks".

3. **A table of contents, with checks.** "So instead of treating AGENTS.md as the encyclopedia, we
   treat it as the table of contents." The map is short, always in context, and points into `docs/`,
   "treated as the system of record". Then comes the part teams skip: "Dedicated linters and CI jobs
   validate that the knowledge base is up to date, cross-linked, and structured correctly."

One limit to keep in mind: the post describes one team's internal product, and its results "should
not be assumed to generalize without similar investment—at least, not yet." The course takes the
structure, then measures it.

## Apply it to your repo

1. Count the lines of your agent instruction file. Find your three most important rules and note the
   line where each starts.
2. Write a map keyed by task, not by topic: "add or change an endpoint" leads to one file.
3. Move each rule to one focused document, and leave a pointer in the map.
4. Before you split anything, add one check for dead links and missing rules. [Assignment 1: Instructions](../assignment/)
   builds exactly this.
5. Read your tickets. If they all say "see the handbook", people are doing the map's job, and it
   stops the day someone forgets the line.
6. Compare `platform/teamtrack/docs/HANDBOOK.md` with `platform/teamtrack/harness/instructions/AGENTS.md`.
   In the handbook, the legacy warning starts at line 136 of 150. Where does the map put it?

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
