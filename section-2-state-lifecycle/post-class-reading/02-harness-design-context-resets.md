# [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

Reading time: about 25 minutes.
Source: Prithvi Rajasekaran (Anthropic), [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), 2026-03-24 ([evidence](../../docs/evidence/s1.md#src-anthropic-harness-design)).

> **Terms on this page**
>
> - **Context reset**: Clearing the context and starting a fresh session, with a handoff.
> - **Compaction**: Squeezing an old context into a summary that the next session starts with.
> - **Structured handoff**: A file that carries the last session's state and the next steps to the next session.
> - **Context anxiety**: A model wrapping up its work early because it thinks its context is nearly full.

## Why it matters

This post is where the term "context reset" comes from, and it is honest about its price. Its
author built resets into one harness, measured their cost, and later took them out when a new model
no longer needed them. That arc is the lesson: a state mechanism is a bet about a model, and bets
should be checked.

## Three key ideas

1. **A reset is a clean slate plus a handoff.** "Context resets—clearing the context window entirely
   and starting a fresh agent, combined with a structured handoff that carries the previous agent's
   state and the next steps". Compaction keeps the thread but not a fresh start: "While compaction
   preserves continuity, it doesn't give the agent a clean slate, which means context anxiety can
   still persist."

2. **Resets cost something.** "This solves the core issue, but adds orchestration complexity, token
   overhead, and latency to each harness run." The course saw the same: harness arms with state
   files ran longer, and hit the agent time limit more often, than bare arms
   ([evidence](../../docs/evidence/s2.md#s2-posthoc)).

3. **Whether you need one depends on the model.** "Opus 4.5 largely removed that behavior on its
   own, so I was able to drop context resets from this harness entirely." What stayed was more
   general: "decomposing the build into tractable chunks, and using structured artifacts to hand off
   context between sessions." The post's rule for every piece of a harness: "every component in a
   harness encodes an assumption about what the model can't do on its own, and those assumptions are
   worth stress testing"

## Apply it to your repo

1. Write down why your agent's sessions end: a turn limit, a time limit, a context limit, or a
   person stopping it. If they never end mid-task, you may not need resets.
2. If they do, keep a handoff file with two parts: facts your tooling writes (commits, changed files,
   test status) and notes the agent writes.
3. Test the assumption the way the post does, "removing one component at a time and reviewing what
   impact it had on the final result." Run the same task with and without the handoff and compare.
4. Re-check when you change models. A mechanism that helped last quarter's model may only cost turns
   now.

## Sources

- Source 1: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
