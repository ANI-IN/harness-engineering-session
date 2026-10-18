# Common failure modes and the harness part that addresses each

Each row is a failure the sources report, in our words, with the sources listed at the end of this page. The last column names the part of the harness
and the template from this skill that address it.

| Failure | What you see | Source | Harness part |
|---|---|---|---|
| The agent cannot follow a rule it cannot see | A rule from the team wiki is broken in every session | [Harness engineering](https://openai.com/index/harness-engineering/) | Instructions: AGENTS.md map and docs/ |
| One giant instruction file | The file is long, stale, and partly contradictory; the agent follows some of it | Source 1 | Instructions: short map, one doc per topic |
| Copying the nearest pattern, including bad ones | New code repeats a legacy handler's mistakes | Source 1 | Instructions: ARCHITECTURE.md "patterns to copy" and "legacy" tables; a house rule with a check |
| Trying to do everything at once | The session runs out of context mid-feature and leaves it half-done and undocumented | [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Scope: feature_list.json, one feature per session |
| Declaring the job done early | A later session sees progress and stops | Source 2 | Scope: every feature starts with `passes: false`; Verification: a gate before done |
| Marking a feature done without testing it end to end | Unit tests pass, the feature does not work for a user | Source 2 | Verification: end-to-end check, clean-state checklist |
| Time spent working out how to run the app | Each session rediscovers the start command | Source 2 | State: init.sh |
| The next session guesses what happened | Work is redone or undone | Source 2 | State: progress.md and git history; Lifecycle: session-handoff.md |
| Self-evaluation skews positive | The agent praises mediocre work | [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Verification: a separate evaluator with grading criteria |
| Visible tests pass, the job is not done | Held-out tests (tests the agent never sees) that combine features fail | [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler); [SpecBench](https://arxiv.org/abs/2605.21384) | Verification: held-out tests, mutant-guided tests (assured-tests skill) |
| Hard-to-undo actions | An agent kills its own process or deletes files | Source 4; [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | Scope: container, no network, allowlisted commands |
| Context window pollution | Test runs print thousands of lines and push the task out of context | Source 4 | Verification: short, grep-friendly output; logs in files (init.sh template) |
| Time blindness | The agent runs the full slow suite again and again | Source 4 | Verification: a fast sample mode |
| Docs drift from the code | The map points to files that moved | Source 1 | Instructions: mechanical checks on docs (assessment check I3 is a small version) |

## How to use this table

When an agent run goes wrong, find the row that matches what you saw, then check the harness part
in the last column first. The advice in Source 1 for every such case: ask "what capability is missing, and how
do we make it both legible and enforceable for the agent?".

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 3: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 4: Building a C compiler with a team of parallel Claudes,
  <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic),
  2026-02-05
- Source 5: SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents,
  <https://arxiv.org/abs/2605.21384>, Zhao, Srikanth, Wu, Jiang (Weco AI), 2026-09-09
- Source 6: Prompting best practices,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>,
  Anthropic (Claude docs), n.d.
