# CLAUDE.md

Read `AGENTS.md` and follow it exactly: startup workflow, scope,
verification rules, and definition of done all live there. Specific to
Claude Code:

- Treat `feature_list.json` as the source of truth for scope, even when
  the conversation suggests otherwise; surface the conflict instead of
  silently following the chat.
- Record evidence immediately after each verification run, not in a batch
  at the end.
