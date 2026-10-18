# [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

Reading time: about 10 minutes.
Source: Justin Young (Anthropic), [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 2025-11-26 ([evidence](../../docs/evidence/s1.md#src-anthropic-long-running)).

> **Terms on this page**
>
> - **Session**: One run of the agent with one context window, from its first turn to its stop.
> - **Initializer agent**: The first session, which sets up the files every later session uses.
> - **Progress file**: A log of what each session did; Anthropic's is `claude-progress.txt`, the course's is `progress.md`.
> - **Compaction**: Squeezing an old context into a summary that the next session starts with.

## Why it matters

Any task longer than one session has this problem: the next session knows nothing about the last
one. Anthropic's team puts it as a picture: "Imagine a software project staffed by engineers working
in shifts, where each new engineer arrives with no memory of what happened on the previous shift."
Their post shows what they put in the repository so each shift can pick up the work. The course's
state layer follows it closely.

## Three key ideas

1. **One setup session, then many working sessions.** The harness has "an initializer agent that
   sets up the environment on the first run, and a coding agent that is tasked with making
   incremental progress in every session". The initializer writes "an init.sh script, a
   claude-progress.txt file that keeps a log of what agents have done, and an initial git commit".
   The two are one system with two first prompts. The course writes these files with plain code.

2. **The state is the progress file plus git.** A fresh session understands the work through "the
   claude-progress.txt file alongside the git history." Compaction alone did not do it: "However,
   compaction isn’t sufficient." Each session commits "with descriptive commit messages" and writes
   a progress summary, so git can also roll back a bad change.

3. **Every session starts and ends the same way.** Under the heading "Getting up to speed", the
   agent runs `pwd`, then: "Read the git logs and progress files to get up to speed on what was
   recently worked on." It runs `init.sh` and a basic end-to-end test first, because building on a
   broken app "would likely make the problem worse." At the end: "End the session by writing a git
   commit and progress update."

## Apply it to your repo

1. Write an `init.sh` that sets up your app and runs one fast end-to-end test. Time it: it runs at
   the start of every session.
2. Add a `progress.md` with four parts: current task, done, in progress, next. Ask your agent to
   update it at the end of each session.
3. Ask for one commit per finished step, with a message that names the step. The git log is then a
   second progress file that the agent cannot forget to write.
4. Put the "Getting up to speed" steps at the top of your agent instructions.
5. Before you add all of this, stop your agent in the middle of a task and start a fresh session.
   Watch its first five tool calls. If it finds the work with `git status`, you may need less.

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
