# Module 1: Harness Engineering for Coding Agents - Demo 2 harness files

This folder holds the four files the state layer writes into the harness arm's workspace before
session 1 of the Section 2: State and sessions demo. They are the files the agent finds when it starts, byte for byte.
Open them to see what a fresh session can read.

> **Terms on this page**
>
> - **Harness layer**: One part of the harness: instructions, state, scope, or verification.
> - **Initializer step**: The harness code that writes these four files and commits them before session 1.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Exec plan**: A plan checked into the repository, with its progress and its decisions.
> - **House rules**: TeamTrack's seven rules for every endpoint, House rule 1: Tenant isolation to House rule 7:
>   Migrations.

Do not edit the files here. They were rendered the way the layer renders them, from the same
templates and the same ticket, Feature 2: Comments on issues, so they show what the agent gets. To
change what the agent gets, edit the templates in `platform/src/shipharness/harness/state/assets/`;
the next `make show-2` writes the new files into the harness arm's workspace.

## What is here

The file set follows Anthropic's long-running harness: "an init.sh script, a claude-progress.txt
file that keeps a log of what agents have done, and an initial git commit that shows what files were
added." ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents))
The course adds a structured handoff and an exec plan.

| Path | What it holds | Who writes it later |
|---|---|---|
| `init.sh` | Scratch database, `alembic heads`, one basic end-to-end test | Nobody; the agent runs it |
| `progress.md` | Current feature, Done, In progress, Next, Session log | The agent edits; the harness appends the log |
| `session-handoff.md` | Machine summary, then "Notes from the agent" | The harness rewrites the summary at each stop |
| `docs/exec-plans/active/F2.md` | Purpose, Progress, Decision Log, Validation | The agent, in its wrap-up turns |

## What changes during a run

- At every session stop the layer rewrites the "Machine summary" of `session-handoff.md`: commits,
  files changed, visible tests, open TODO markers, migration heads, and the documents read. It keeps
  the agent's notes as written.
- At every stop it appends one line under "Session log" in `progress.md`, then commits both files.
- In this demo the exec plan stays in `active/`. The layer moves it to `completed/` only when the
  scope layer marks the feature as passing, and the scope layer starts in Section 3: Scope and
  sandbox.

## What is not here

- The AGENTS.md map and its documents. The instructions layer places them; see the
  [Section 1: Instructions demo](../../../section-1-instructions/demo/README.md).
- `feature_list.json`. The scope layer writes it, from Section 3 on. The `progress.md` template still
  says to read it, so in this demo the agent finds no such file.
- The "Getting up to speed" steps and the wrap-up message. They are text the layer sends, not files;
  the [walkthrough](../walkthrough.md) shows where they come from.

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic),
  2025-11-26
