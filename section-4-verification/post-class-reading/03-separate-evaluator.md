# [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

Reading time: about 25 minutes.
Source: [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), Prithvi Rajasekaran (Anthropic), 2026-03-24 ([evidence](../../docs/evidence/s1.md#src-anthropic-harness-design)).

> **Terms on this page**
>
> - **Evaluator**: A separate agent or model that judges the work of the agent that did it.
> - **Grading criteria**: Written rules the judge scores against, each with a pass line.
> - **Reviewer**: The course's evaluator: a separate model that reads each final diff, with arm traces removed.

## Why it matters

Most teams let the agent that wrote the code also say whether it works. Anthropic's harness team
measured what that costs, and built a separate evaluator to fix it. The post also says when an
evaluator is not worth it. The gate and the reviewer of Section 4: Verification follow its main idea:
the agent that does the work is not the one that judges it.

## Three key ideas

1. **Agents praise their own work.** "When asked to evaluate work they've produced, agents tend to
   respond by confidently praising the work—even when, to a human observer, the quality is obviously
   mediocre." Asking the same agent to self-verify, as an earlier Anthropic harness did ("Self-verify
   all features",
   [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)),
   does not remove that bias.

2. **A separate judge, with criteria, is the lever.** "Separating the agent doing the work from the
   agent judging it proves to be a strong lever to address this issue." It works because "tuning a
   standalone evaluator to be skeptical turns out to be far more tractable than making a generator
   critical of its own work". The judge needs something concrete: "does this follow our principles
   for good design?" is gradable, and "Each criterion had a hard threshold".

3. **The judge is still lenient, and it has a cost.** "the evaluator is still an LLM that is inclined
   to be generous towards LLM-generated outputs." The post treats it as a cost decision: "It is worth
   the cost when the task sits beyond what the current model does reliably solo."

The course uses two judges, and neither is the agent. Code decides the primary measure: the gate, the
hidden tests, and the planted faults. A separate model reviews each final diff against grading
criteria from the harness documents, with every trace of the arm removed. Its verdict is a secondary
measure, because of the leniency above. It runs on both arms' final diffs, never inside the gate, so
the harness arm gets no feedback the bare arm cannot get.

## Apply it to your repo

1. If an agent reviews its own pull requests, add a separate review step: another call, with no
   access to the author's reasoning.
2. Write three to five grading criteria from your own documents, such as security rules and layering
   rules. Give each a clear fail line. Use the same text for every review.
3. Keep that reviewer's verdict below checks that run code: tests, lint, contract probes.
4. Each month, read ten reviews where the reviewer and your tests disagreed. Change the criteria, not
   the tests, when the reviewer was wrong.
5. Decide where it pays: add the reviewer to the tasks your agent gets wrong most, not to every task.

## Sources

- Source 1: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 2: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
