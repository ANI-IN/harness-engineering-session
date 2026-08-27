# CLAUDE.md

Read [AGENTS.md](AGENTS.md) and follow it exactly: startup workflow, working
rules, verification commands, definition of done, and end-of-session steps
all live there. Claude Code specifics:

- Use the built-in file tools rather than shell `cat`/`sed` for reading and
  editing.
- Run curriculum code through the root toolchains:
  `uv run python <unit>/python/main.py` and
  `pnpm exec tsx <unit>/typescript/main.ts`; unit directories have no
  manifests of their own by design (see docs/conventions.md, "Workspace
  shape").
- When editing an exercise, re-run all four acceptance runs before claiming
  it works; paste real output, not summaries.
