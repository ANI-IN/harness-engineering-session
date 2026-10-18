# Module 1: Harness Engineering for Coding Agents - Reading list for Section 3: Scope and sandbox

Three short readings that go past the 50 minutes of class. Each one sums up a primary source in plain
words and shows how to apply it to your own repository. Each page takes about five minutes; the
reading time in the table is for the full source, at 200 words a minute.

> **Terms on this page**
>
> - **Feature list**: `feature_list.json`, the one feature of the run and its `passes` field.
> - **Sandbox**: The container every tool command runs in, the same for both arms.
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.

## Readings

| Reading | Reading time | Why read it |
|---|---|---|
| [01 Anthropic's long-running harness](01-effective-harnesses-feature-list.md) | 10 minutes | Where the feature list, one feature at a time, and `passes` come from |
| [02 Building a C compiler with parallel Claudes](02-c-compiler-containers.md) | 15 minutes | Why unattended agents run in a container with no internet |
| [03 Codex: agent approvals and security](03-codex-sandbox-and-approvals.md) | 20 minutes | How another coding agent sets its sandbox, and what it leaves to you |

## How to use these

- Read them in order. The first is about files in scope, the second about what the machine allows,
  the third puts both next to an agent you may already use.
- After each reading, do the first step of its "Apply it to your repo" list on a repository you work
  on. It takes a few minutes and makes the idea stick.
- Then read the primary sources. Start with the "Feature list" part of
  [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  (Source 1), then the sections on running agents in parallel in
  [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
  (Source 2), then Codex's
  [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security) page.
- The class recap is in [session-notes.md](../session-notes.md).

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
- Source 3: Agent approvals & security, <https://developers.openai.com/codex/agent-approvals-security>, OpenAI (Codex documentation), n.d.
