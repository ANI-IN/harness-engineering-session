# Module 1: Harness Engineering for Coding Agents - Reading list for Section 2: State and sessions

Three short readings that go past the 50 minutes of class. Each one sums up a primary source in plain
words and shows how to apply it to your own repository. Each page takes about five minutes; the
reading time in the table is for the full source, at 200 words a minute.

> **Terms on this page**
>
> - **Session**: One run of the agent with one context window, from its first turn to its stop.
> - **Context reset**: Clearing the context and starting a fresh session, with a handoff.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Exec plan**: A plan checked into the repository, with its progress and its decisions.

## Readings

| Reading | Reading time | Why read it |
|---|---|---|
| [01 Working in shifts](01-effective-harnesses-for-long-running-agents.md) | 10 minutes | The files and routines that carry work from one session to the next |
| [02 Harness design: context resets](02-harness-design-context-resets.md) | 25 minutes | Resets against compaction, and why the choice depends on the model |
| [03 Using PLANS.md](03-exec-plans.md) | 15 minutes | A plan the next session can restart from |

## How to use these

- Read them in order. The first sets up the files; the second asks when you need a reset at all; the
  third makes the plan good enough to restart from.
- After each reading, do the first step of its "Apply it to your repo" list on a repository you work
  on. It takes a few minutes and makes the idea stick.
- Then read the primary sources. Start with the "Getting up to speed" part of
  [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents),
  then the context reset part of
  [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps).
- The class recap is in [session-notes.md](../session-notes.md).

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
