# Session plan: four hours

Four hours is not enough to cover thirteen lectures and five projects, so
this plan does not try. It spends the time where harness engineering adds
something this audience does not already have, and says plainly what is
left for afterwards.

The audience is experienced engineers already fluent in agentic AI. They
have built agents with LangChain, LangGraph, MCP, A2A, Google ADK and
LangSmith. Orchestration is not new to them. What is new is the execution
system around the agent: the repository as the system of record, scope
enforced by the workspace, completion that only a re-executed check can
declare, and a session that leaves the next one somewhere to stand.

That is why loop and graph engineering get the least time in the room and
the verification block gets the most.

## The four hours

| Block | Minutes | Units | Mode |
| --- | --- | --- | --- |
| Why the harness, not the model | 15 | Lectures [01](../lectures/lecture-01-why-capable-agents-still-fail/), [02](../lectures/lecture-02-what-a-harness-actually-is/) | Live, one demo |
| The repository as the system of record | 20 | Lectures [03](../lectures/lecture-03-why-the-repository-must-become-the-system-of-record/), [04](../lectures/lecture-04-why-one-giant-instruction-file-fails/) | Live, one demo |
| Starting from a known state | 10 | Lecture [05](../lectures/lecture-05-why-initialization-needs-its-own-phase/) | Demo only |
| Scope the workspace enforces | 30 | Lectures [06](../lectures/lecture-06-why-agents-overreach-and-under-finish/), [07](../lectures/lecture-07-why-feature-lists-are-harness-primitives/) | Live, both demos |
| Verification: the claim and the check | 40 | Lectures [08](../lectures/lecture-08-why-agents-declare-victory-too-early/), [09](../lectures/lecture-09-why-end-to-end-testing-changes-results/) | Live, both demos |
| What the harness records | 20 | Lecture [10](../lectures/lecture-10-why-observability-belongs-inside-the-harness/) | Live, one demo |
| What a session owes the next one | 20 | Lecture [11](../lectures/lecture-11-why-every-session-must-leave-a-clean-state/) | Live, one demo |
| Loops and graphs, briefly | 15 | Lectures [12](../lectures/lecture-12-loop-engineering/), [13](../lectures/lecture-13-graph-engineering/) | Demo only |
| The controlled experiment | 20 | [Project 01](../projects/project-01-baseline-vs-minimal-harness/) | Live walkthrough |
| Who checks the work | 15 | [Project 05](../projects/project-05-self-verification-and-role-separation/) | Demo only |
| Questions and buffer | 35 | | |
| **Total** | **240** | | |

## What each mode means

**Live** means the mechanism is taught and its demo is run in the room,
both exit codes shown. These are the blocks where the idea is not obvious
to someone who already builds agents.

**Demo only** means the demo is run and the result discussed, without
working through the mechanism. Enough to know the unit exists and what it
proves, not enough to build it from memory.

**Self-study** means the unit is not opened in the session at all.

## What the four hours do not cover

Said plainly, because the cut is the plan:

- **Every exercise.** All twenty-five are self-study. They are the part
  that turns watching into building, and they are the first thing to do
  afterwards.
- **Projects 02, 03 and 04** entirely. They compose the mechanisms into a
  working application across four versions, which is a day of work, not a
  block in an afternoon.
- **Lecture 01 and lecture 03** are read rather than taught: their claims
  land in a sentence each for this audience, and the time goes to the
  blocks where it does not.
- **Loop and graph engineering** get fifteen minutes between them. This
  audience has built both. What the module adds is the harness around
  them, which the earlier blocks already covered.

## Doing it afterwards

The order that matters: the exercises for the blocks that were taught
live, then project 01 (the controlled experiment that makes the whole
argument measurable), then projects 02 through 05 in order, since each
one's starter is the previous one's solution.

Everything runs offline in both tracks. Pick one track and stay in it;
[choosing your track](./choosing-your-track.md) covers what differs.
