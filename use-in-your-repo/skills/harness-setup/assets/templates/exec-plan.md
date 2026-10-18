# Exec plan: <feature id> <short title>

<!-- A living plan for one feature, kept in docs/exec-plans/active/ and moved to
docs/exec-plans/completed/ when the feature passes ([Harness engineering](https://openai.com/index/harness-engineering/): plans "with progress and decision logs that
are checked into the repository"). Section names follow the ExecPlan in [Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans) (https://cookbook.openai.com/articles/codex_exec_plans); the wording is ours. Write it
so a new session with no memory can restart from this file alone ([Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans)). Update it as you work, not at
the end. -->

## Purpose

<What a user can do after this change that they could not do before, and how to see it working.>

## Progress

- [ ] (<YYYY-MM-DD HH:MM>) <step>
- [ ] (<YYYY-MM-DD HH:MM>) <step>

## Surprises & Discoveries

- <Something that behaved differently than expected, with the evidence (command and output).>

## Decision Log

- Decision: <what was decided>
  Rationale: <why, and which alternative was rejected>
  Date: <YYYY-MM-DD>

## Outcomes & Retrospective

<Filled in when the feature passes: what was delivered, what is left, what to do differently.>

## Validation

Commands that prove the feature works, with the result you expect from each:

```
<test command for this feature>      expected: all pass
./init.sh                            expected: init: ok
<manual check, for example a curl>   expected: <status and body>
```

### Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Using PLANS.md for multi-hour problem solving,
  <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
