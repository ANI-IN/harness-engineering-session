---
name: harness-setup
description: >
  Assess a repository's harness for coding agents (instructions, state, scope, verification, and
  session lifecycle) with a deterministic read-only script that writes an HTML report, then add the
  missing parts from source-based templates: an AGENTS.md map, ARCHITECTURE.md, SECURITY.md,
  feature_list.json with a schema, progress.md, session-handoff.md, an exec plan, a clean-state
  checklist, and init.sh. Use when preparing a repository for long-running or multi-session agent
  work, when agents ignore project rules or lose track between sessions, or when asked to audit or
  set up AGENTS.md and the files around it.
license: MIT
metadata:
  course: shipharness
  sources: the numbered Sources list at the end of this file
---

# Harness setup

The course calls the harness "the environment around the agent": what the agent can read, what it
remembers between sessions, what it may change, and what proves its work is done. The basis is [Harness engineering](https://openai.com/index/harness-engineering/):
engineers "design environments, specify intent, and build feedback loops". This skill checks a
repository for each part and fills the gaps from templates.

## When to use

- Before handing a repository to a coding agent for work that spans more than one session.
- When an agent breaks rules that are written down somewhere it does not look (Source 1: "anything it
  can’t access in-context while running effectively doesn’t exist").
- When a new session repeats or undoes the last session's work ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents): "each new session begins with
  no memory of what came before").

## Step 1: assess

```
python scripts/assess.py <repo> --out harness-assessment.html
```

The script reads files only. It makes no network or model calls, never runs code from the
repository, never follows links that leave it, and gives the same report for the same files. It
prints a summary per area and writes an HTML table with, for every check, its status (pass,
partial, fail), the evidence, the fix, and the source. Add `--json` to print the checks as JSON; only the JSON carries the check ids (`I1`, `S1`, and
so on) used in the table below and in the checklists.
Keyword checks (for example "does AGENTS.md mention init.sh") are heuristics and say so.

## Step 2: fill the gaps, area by area

Work through the failing checks in this order. Each area has a checklist with the reasons.

| Area | Checks | Add | Template (copy to) | Checklist |
|---|---|---|---|---|
| Instructions | `I1`-`I6` | A map, the architecture doc, the docs folder | `assets/templates/AGENTS.md` (root), `assets/templates/ARCHITECTURE.md` (root), `assets/templates/SECURITY.md` (`docs/SECURITY.md`) | [instructions](references/instructions.md) |
| State | `S1`-`S4` | Progress log, start script, exec plans, git | `assets/templates/progress.md` (root), `assets/templates/init.sh` (root), `assets/templates/exec-plan.md` (`docs/exec-plans/active/<feature>.md`) | [state](references/state.md) |
| Scope | `C1`-`C5` | The list of work and its schema, layering rules, a container | `assets/templates/feature_list.json` and `assets/templates/feature_list.schema.json` (root) | [scope](references/scope.md) |
| Verification | `V1`-`V5` | Tests, CI, lint, a definition of clean state, coverage | `assets/templates/clean-state-checklist.md` (`docs/clean-state-checklist.md`) | [verification](references/verification.md) |
| Session lifecycle | `L1`-`L5` | Start and end routines, the structured handoff | `assets/templates/session-handoff.md` (root); the routines are in the AGENTS.md template | [session lifecycle](references/session-lifecycle.md) |

Where the files go: [docs layout](references/docs-layout.md). What each part prevents:
[failure modes](references/failure-modes.md).

## Rules for filling the templates

1. Keep AGENTS.md a map. Source 1: "we treat it as the table of contents", "roughly 100 lines". Move each
   rule into the document it belongs to and point to it. Do not paste a long handbook into AGENTS.md
   (Source 1: "Too much guidance becomes non-guidance.").
2. Replace every `<placeholder>`. Delete a section that does not apply instead of leaving it empty.
3. Write facts that are true of this repository today. Run each command you put in AGENTS.md,
   init.sh, and the clean-state checklist before you commit it.
4. Keep the feature list in JSON (Source 2: the model is "less likely to inappropriately change or
   overwrite JSON files compared to Markdown files"). Every entry starts with `"passes": false`.
   Source 2 lets the agent change only the `passes` field. `evidence` and `testedAt` are shipharness
   additions; in shipharness only the harness sets them, after the checks pass.
5. Point AGENTS.md at the pattern to copy and mark legacy code as legacy in ARCHITECTURE.md (Source 1:
   agents replicate "patterns that already exist in the repository—even uneven or suboptimal
   ones").
6. Commit the harness files together in one commit so the history shows what was added (the
   initializer in Source 2 ends with "an initial git commit that shows what files were added").

## Step 3: assess again

Run the script again and compare the reports. Every pointer in AGENTS.md should resolve (check `I3`)
and every area should show no failures, or a written reason in `progress.md` for each one left.

## What this skill does not do

The templates write rules down; they do not enforce them. Enforcement is code: a layering contract,
a scope guard, tests, and a gate before "done" (Source 1: "When documentation falls short, we promote the
rule into code"). Use the house-rules skill to turn a rule into a check, and the assured-tests skill
to add tests that are kept only when they prove something.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 3: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 4: Autonomous Coding Agent Demo (README in claude-quickstarts),
  <https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding>, Anthropic,
  2025-11-26
- Source 5: Using PLANS.md for multi-hour problem solving,
  <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
- Source 6: Agent Skills Specification, <https://agentskills.io/specification>,
  Agent Skills project, n.d.
