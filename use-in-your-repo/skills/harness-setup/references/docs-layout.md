# Docs layout

Where each harness file lives. Sources are listed at the end of this page, and the tree
names them by number. The tree
follows the figure "In-repository knowledge store layout" in [Harness engineering](https://openai.com/index/harness-engineering/) and adds the state and scope
files from [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), and [Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans).

```
AGENTS.md                      map, roughly 100 lines (Source 1)
ARCHITECTURE.md                domains and package layering (Source 1)
init.sh                        start the app, run a smoke test (Source 2)
progress.md                    log of what agents have done (Source 2: claude-progress.txt)
session-handoff.md             structured handoff between sessions (Source 3)
feature_list.json              list of work, passes per feature (Source 2; Source 5)
feature_list.schema.json       schema for the list (course addition)
docs/
  SECURITY.md                  security rules (name from Source 1)
  RELIABILITY.md               reliability rules (name from Source 1)
  QUALITY_SCORE.md             grade per domain and layer (Source 1)
  PLANS.md                     how to write an exec plan (Source 1; Source 4)
  clean-state-checklist.md     definition of clean state (Source 2; course file)
  design-docs/
    index.md                   design decisions, verification status, core beliefs (Source 1)
  exec-plans/
    active/<feature>.md        living plans for work in progress (Source 1; Source 4)
    completed/<feature>.md     finished plans (Source 1)
    tech-debt-tracker.md       known technical debt (Source 1)
  generated/
    db-schema.md               generated from the code, never edited by hand (Source 1)
  product-specs/
    index.md                   what the product does (Source 1)
  references/
    <library>-llms.txt         notes on a library, written for agents (name pattern from Source 1)
.agents/skills/<name>/SKILL.md skills for Codex and Cursor (Source 6; Source 8; Source 9)
.claude/skills/<name>/SKILL.md skills for Claude Code and Cursor (Source 7; Source 9)
```

## What each source says about the layout

| File or folder | What the source says | Source |
|---|---|---|
| AGENTS.md | Injected into context, "serves primarily as a map, with pointers to deeper sources of truth elsewhere." | Source 1 |
| ARCHITECTURE.md | At the root; "a top-level map of domains and package layering." | Source 1 |
| docs/ | "treated as the system of record." | Source 1 |
| design-docs/ | "catalogued and indexed, including verification status and a set of core beliefs". | Source 1 |
| QUALITY_SCORE.md | "grades each product domain and architectural layer, tracking gaps over time." | Source 1 |
| exec-plans/ | Plans "with progress and decision logs that are checked into the repository". | Source 1 |
| SECURITY.md, RELIABILITY.md, PLANS.md, product-specs/, references/ | Names only, from the layout figure. Source 1 does not describe their contents. | Source 1 |
| init.sh, progress file, feature list | Created by the initializer agent in Source 2 before the first coding session. | Source 2 |
| session-handoff.md | The "structured handoff" in Source 3. The file name is the course's. | Source 3 |

## Rules for the layout

- Keep AGENTS.md and ARCHITECTURE.md at the root; everything else under docs/ (Source 1).
- Prefer a short file per topic over one long file. Agents load what they need, when they need it
  (Source 1: "agents start with a small, stable entry point and are taught where to look next").
- Generated files say so at the top and are rebuilt by a script, not edited by agents.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 3: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 4: Using PLANS.md for multi-hour problem solving,
  <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
- Source 5: Autonomous Coding Agent Demo (README in claude-quickstarts),
  <https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding>, Anthropic,
  2025-11-26
- Source 6: How to add skills support to your agent,
  <https://agentskills.io/client-implementation/adding-skills-support.md>, Agent Skills project,
  n.d.
- Source 7: Extend Claude with skills, <https://code.claude.com/docs/en/skills>,
  Anthropic (Claude Code docs), n.d.
- Source 8: Build skills, <https://learn.chatgpt.com/docs/build-skills>, OpenAI (Codex docs), n.d.
- Source 9: Agent Skills (Cursor docs), <https://cursor.com/docs/skills>, Cursor, n.d.
