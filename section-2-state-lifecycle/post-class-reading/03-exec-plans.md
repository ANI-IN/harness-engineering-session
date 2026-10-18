# [Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans)

Reading time: about 15 minutes.
Source: Aaron Friel (OpenAI Cookbook), [Using PLANS.md for multi-hour problem solving](https://cookbook.openai.com/articles/codex_exec_plans), 2025-10-07, archived ([evidence](../../docs/evidence/s2.md#src-openai-exec-plans)).

> **Terms on this page**
>
> - **Exec plan**: A plan checked into the repository, with its progress and its decisions.
> - **PLANS.md**: The file that tells the agent how to write and keep an exec plan.
> - **Living document**: A file the agent updates as it works, not once at the start.

## Why it matters

A progress file says what happened. A plan says what the work is, why it is shaped that way, and what
is left. OpenAI's harness team keeps "execution plans with progress and decision logs that are
checked into the repository" ([Harness engineering](https://openai.com/index/harness-engineering/)),
and this recipe is the one they link for how to write them. The course's exec plan template is built
from it.

## Three key ideas

1. **A plan you can restart from.** The bar is high: "it should always be possible to restart from
   _only_ the ExecPlan and no other work." A new session should not need the chat, the old context,
   or a person to explain the task.

2. **Self-contained, written for a newcomer.** "Every ExecPlan must be fully self-contained.
   Self-contained means that in its current form it contains all knowledge and instructions needed
   for a novice to succeed." A fresh session is that novice: it knows the repository only through
   what it reads.

3. **Four living sections.** "ExecPlans must contain and maintain a `Progress` section, a
   `Surprises & Discoveries` section, a `Decision Log`, and an `Outcomes & Retrospective` section."
   Progress says where the work stands; the decision log says why, so the next session does not undo
   a choice it does not understand. The agent learns when to use the plan from its map: OpenAI starts
   by "updating AGENTS.md to describe when to use PLANS.md".

## Apply it to your repo

1. Open the course's template, `section-2-state-lifecycle/demo/harness/docs/exec-plans/active/F2.md`, and
   compare its sections with the four above.
2. For your next multi-session task, write a plan in `docs/exec-plans/active/` before the first
   session. Keep the purpose and the steps short.
3. Add one line to your agent's map: when a task takes more than one session, read and update the
   plan.
4. Test the bar: start a fresh session with only the plan and the repository. If it asks questions
   the plan should answer, add the answers to the plan.
5. When the work is done, move the plan to `docs/exec-plans/completed/` with its outcome. Old plans
   explain old decisions.

## Sources

- Source 1: Using PLANS.md for multi-hour problem solving, <https://cookbook.openai.com/articles/codex_exec_plans>, Aaron Friel (OpenAI Cookbook), 2025-10-07
- Source 2: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
