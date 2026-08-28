# Lectures

Each lecture defends **one claim** about why agents fail and what fixes the
failure, and proves it with a runnable demo. Lectures are short on ideology
and long on mechanism: every concept you read, you will run.

## How a lecture works

Every `lecture-NN-<slug>/` directory contains:

- **`README.md`**: the lecture itself, always in the same order: learning
  objectives, prerequisites, the problem (a concrete failure you can
  observe), concepts, architecture (with a diagram), the demo with real
  commands and real output in both tracks, implementation notes, key
  takeaways, exercises, further exploration.
- **`code/`**: the demo, a shared `SPEC.md` + fixtures + expected outputs,
  implemented in `python/` and `typescript/`, checked by `verify.sh`.
- **`exercises/`**: 2 for most lectures, 3 for lecture 11 (which absorbed
  the continuity material), and 1 each for lectures 12 and 13, whose
  mechanism is a single build. Each gives you starter code
  that runs but fails verification, and you modify it until
  `./verify.sh --stack=<your track>` exits 0. Committed solutions let you
  check your work.

Work in order; each lecture assumes the ones before it. Expect roughly 60-90
minutes per lecture including exercises.

## Curriculum

| # | Lecture | The claim it defends | Related project | In the session |
| --- | --- | --- | --- | --- |
| 01 | [Why capable agents still fail](./lecture-01-why-capable-agents-still-fail/) | Failures are harness defects, not capability defects | [Project 01](../projects/project-01-baseline-vs-minimal-harness/) | read |
| 02 | [What a harness actually is](./lecture-02-what-a-harness-actually-is/) | A harness is five subsystems working as one system | [Project 01](../projects/project-01-baseline-vs-minimal-harness/) | 15 min live |
| 03 | [Why the repository must become the system of record](./lecture-03-why-the-repository-must-become-the-system-of-record/) | What is not in the repository does not exist for the agent | [Project 02](../projects/project-02-agent-readable-workspace/) | read |
| 04 | [Why one giant instruction file fails](./lecture-04-why-one-giant-instruction-file-fails/) | Instructions must be a map, not a manual | [Project 02](../projects/project-02-agent-readable-workspace/) | 20 min live |
| 05 | [Why initialization needs its own phase](./lecture-05-why-initialization-needs-its-own-phase/) | Sessions that start by improvising end by guessing | [Project 03](../projects/project-03-multi-session-continuity/) | 10 min demo |
| 06 | [Why agents overreach and under-finish](./lecture-06-why-agents-overreach-and-under-finish/) | Overreach and under-finish are one budget seen from two sides | [Project 04](../projects/project-04-runtime-feedback-and-scope-control/) | 30 min live |
| 07 | [Why feature lists are harness primitives](./lecture-07-why-feature-lists-are-harness-primitives/) | A feature list is a data structure the harness executes against, not a memo | [Project 04](../projects/project-04-runtime-feedback-and-scope-control/) | 30 min live |
| 08 | [Why agents declare victory too early](./lecture-08-why-agents-declare-victory-too-early/) | A completion claim stands until something outside the session re-executes the checks | [Project 05](../projects/project-05-self-verification-and-role-separation/) | 40 min live |
| 09 | [Why end-to-end testing changes results](./lecture-09-why-end-to-end-testing-changes-results/) | Unit checks can all pass while the assembled path fails at a seam | [Project 05](../projects/project-05-self-verification-and-role-separation/) | 40 min live |
| 10 | [Why observability belongs inside the harness](./lecture-10-why-observability-belongs-inside-the-harness/) | A session can only resume work whose history something recorded | Closest: [Project 04](../projects/project-04-runtime-feedback-and-scope-control/) | 20 min live |
| 11 | [Why every session must leave a clean state](./lecture-11-why-every-session-must-leave-a-clean-state/) | What a session leaves behind decides what the next one can do | Closest: [Project 03](../projects/project-03-multi-session-continuity/), [Project 05](../projects/project-05-self-verification-and-role-separation/) | 20 min live |
| 12 | [Loop engineering](./lecture-12-loop-engineering/) | A loop is only as good as the signal its stopping condition reads | None | 15 min demo |
| 13 | [Graph engineering](./lecture-13-graph-engineering/) | Routing and rollback are structure you declare, not control flow you hope for | None | 15 min demo |

Blocks marked live or demo are the ones the four-hour session opens; see
the [session plan](../docs/session-plan.md). Everything else, and every
exercise, is self-study.

This index lists every lecture the module currently contains; the
[curriculum map](../docs/curriculum-map.md) shows how they connect.
