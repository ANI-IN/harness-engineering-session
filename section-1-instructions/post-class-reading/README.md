# Module 1: Harness Engineering for Coding Agents - Reading list for Section 1: Instructions

Three short readings that go past the 50 minutes of class. Each one sums up a primary source in plain
words and shows how to apply it to your own repository. Each page takes about five minutes; the
reading time in the table is for the full source, at 200 words a minute.

> **Terms on this page**
>
> - **Map**: A short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **Progressive disclosure**: A small entry point first; the details only when the task needs them.
> - **Agent Skill**: A folder with a `SKILL.md` recipe that the agent loads only when a task needs it.

## Readings

| Reading | Reading time | Why read it |
|---|---|---|
| [01 A map, not a manual](01-map-not-manual.md) | 15 minutes | Why one big instruction file fails, and what replaces it |
| [02 Progressive disclosure in Agent Skills](02-progressive-disclosure-in-agent-skills.md) | 5 minutes | How a skill is built and what loads when |
| [03 Skills in other agents](03-instructions-in-other-agents.md) | 80 minutes | Where Claude Code, Codex, and Cursor look for skills |

## How to use these

- Read them in order. Each one builds on the one before.
- After each reading, do the first step of its "Apply it to your repo" list on a repository you work
  on. It takes a few minutes and makes the idea stick.
- Then read the primary sources. Start with the section "We made repository knowledge the system of
  record" in [Harness engineering](https://openai.com/index/harness-engineering/), then the
  progressive disclosure part of the
  [Agent Skills Specification](https://agentskills.io/specification).
- The class recap is in [session-notes.md](../session-notes.md).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Agent Skills Specification, <https://agentskills.io/specification>, Agent Skills project, n.d.
