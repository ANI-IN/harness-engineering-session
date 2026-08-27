<!--
  Template: CLAUDE.md, Claude Code's entry file, pointing at the one contract.
  Use when: the repo uses Claude Code and already has AGENTS.md.
  Don't use when: there is no AGENTS.md; put the contract there first.
  Motivated by: Lecture 04 (Why one giant instruction file fails): one
  contract in one place; a second full copy would drift.
-->

# CLAUDE.md

Read `AGENTS.md` and follow it exactly: startup workflow, working rules,
verification commands, definition of done, and end-of-session steps all live
there. This file adds only what is specific to Claude Code:

- Prefer the built-in file tools over shell `cat`/`sed` for reading and editing.
- When a task will span sessions, write the handoff (`session-handoff.md`)
  *before* the context window forces a summary, not after.
- Treat `feature_list.json` as the source of truth for scope, even when the
  conversation suggests otherwise; surface the conflict instead of silently
  following the chat.
