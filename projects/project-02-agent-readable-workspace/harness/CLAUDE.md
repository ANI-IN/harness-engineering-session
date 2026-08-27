# CLAUDE.md

Read `AGENTS.md` and follow it exactly; it is a router, so follow its
links rather than reading every doc up front. Specific to Claude Code:

- Treat `feature_list.json` as the source of truth for scope, even when
  the conversation suggests otherwise; surface the conflict instead of
  silently following the chat.
- Update `session-handoff.md` before the context window forces a summary,
  not after; `kb workspace-check --workspace .` grades the result.
