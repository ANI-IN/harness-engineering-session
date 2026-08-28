# Library

The copy-ready pack: the harness artifacts this course teaches, in the form
you drop into your own repository. Everything here is language-neutral: the
same files serve a Python, TypeScript, or any other codebase, and every file
is valid in its own format (JSON parses and validates against its schema,
shell scripts pass shellcheck, checklists are complete).

This library is the **single source of truth** for these artifacts across the
whole course: the projects instantiate them, and the `harness-creator` skill
emits them. There are no second copies to drift out of sync.

## The minimal pack

Start with four files. They are enough to make most agent workflows
noticeably more stable:

| File | What it gives the agent |
| --- | --- |
| [`templates/AGENTS.md`](./templates/AGENTS.md) | An entry point: what this system is, how to start, what "done" means |
| [`templates/feature_list.json`](./templates/feature_list.json) | Machine-readable scope and state, validated by [`feature_list.schema.json`](./templates/feature_list.schema.json) |
| [`templates/claude-progress.md`](./templates/claude-progress.md) | Session-to-session memory: what is verified, what happened, what's next |
| [`templates/init.sh`](./templates/init.sh) | A working start: install, verify, print the next command |

If your agent is Claude Code, add [`templates/CLAUDE.md`](./templates/CLAUDE.md),
a thin pointer that keeps one contract in one place.

## The upgrade path

Add the next tier when you observe the failure it addresses, not before.
Harness components must earn their place (each template's header names the
failure mode it exists for):

| Add | When you observe |
| --- | --- |
| [`templates/session-handoff.md`](./templates/session-handoff.md) | New sessions spend their first minutes re-deriving what the last one did |
| [`templates/clean-state-checklist.md`](./templates/clean-state-checklist.md) | Sessions end "green" but leave broken builds, stray files, or unrecorded state |
| [`templates/evaluator-rubric.md`](./templates/evaluator-rubric.md) | The agent approves its own questionable work; you need a checker role |

Signals that you have outgrown this pack entirely (many domains, several
agents, long-running work) point to the advanced pack (fuller repository
skeleton with routing docs and plan lifecycle), which arrives with the second
half of the course alongside the reference notes (startup flow, failure-mode
map, audit checklist).

## Rules that keep the pack working

- **One contract, one file.** `CLAUDE.md` points at `AGENTS.md` rather than
  restating it; duplicated contracts drift.
- **Evidence or it didn't happen.** A feature reaches `passing` only with a
  recorded command and observed result; the schema enforces it.
- **Templates are exemplars.** Every file ships filled in with a realistic
  example, so you can see the intended shape before you overwrite it with
  your own content.
