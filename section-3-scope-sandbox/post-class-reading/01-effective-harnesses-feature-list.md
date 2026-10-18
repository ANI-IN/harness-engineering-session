# [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

Reading time: about 10 minutes.
Source: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), Justin Young (Anthropic), 2025-11-26 ([evidence](../../docs/evidence/s1.md#src-anthropic-long-running)).

> **Terms on this page**
>
> - **Feature list**: `feature_list.json`, the one feature of the run and its `passes` field.
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.
> - **Harness arm**: The same run with the harness turned on.

## Why it matters

Anthropic's team ran a coding agent over many sessions to build a whole web app. Two failures came
up again and again: the agent tried to do everything at once, and a later session saw progress and
declared the job done. Their fix gave each session a small, fixed scope: one feature from a list, and
a field that says whether it works. Section 3: Scope and sandbox starts from that list. This page sums up the post's
"Feature list" and "Incremental progress" parts.

## Three key ideas

1. **The feature list is the outline of done.** An initializer agent wrote every feature into one
   file, and "These features were all initially marked as “failing” so that later coding agents
   would have a clear outline of what full functionality looked like." Each entry has a category, a
   description, steps, and `"passes": false`. Scope is no longer a feeling; it is a file.

2. **One feature at a time.** The coding agent "was then asked to work on only one feature at a
   time." A small scope keeps a session from running out of room halfway, and it gives the next
   session a clean place to start. Git helped too: "This allowed the model to use git to revert bad
   code changes and recover working states of the code base."

3. **Protect the list, and say why.** The agent could change the file "only by changing the status
   of a passes field", with a strong warning: "It is unacceptable to remove or edit tests because
   this could lead to missing or buggy functionality." Here "tests" means the list's entries. The
   team chose JSON because "the model is less likely to inappropriately change or overwrite JSON
   files compared to Markdown files." Less likely is not never, which is where Section 3 goes
   further.

What the course changes: the agent may not edit the file at all, and the harness sets `passes` from
its own test run. The post's own advice was "Only mark features as “passing” after careful testing",
which still leaves the judgement with the agent.

## Apply it to your repo

1. Write the next agent task as one feature entry: an id, a one-line description, the steps, and
   `"passes": false`. Keep it in JSON next to the code.
2. Add the files the feature may change, per phase. If you cannot list them, the task is too big for
   one session.
3. Decide who flips `passes`. If it is the agent, add a check that runs your tests first and refuses
   the flip when they fail.
4. Make the list itself off limits to the agent's file edits, for example with a pre-commit check
   that rejects changes to it from the agent's branch.
5. Compare with the course's version: open `section-3-scope-sandbox/demo/harness/feature_list.json` and
   `scope-rules.txt`. Which of the post's ideas made it into the scope text, word for word?

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
