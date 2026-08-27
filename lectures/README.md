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
- **`exercises/`**: 2 exercises per lecture. Each gives you starter code
  that runs but fails verification, and you modify it until
  `./verify.sh --stack=<your track>` exits 0. Committed solutions let you
  check your work.

Work in order; each lecture assumes the ones before it. Expect roughly 60-90
minutes per lecture including exercises.

## First-pass curriculum (lectures 01-06)

| # | Lecture | The claim it defends | Related project |
| --- | --- | --- | --- |
| 01 | [Why capable agents still fail](./lecture-01-why-capable-agents-still-fail/) | Failures are harness defects, not capability defects | [Project 01](../projects/project-01-baseline-vs-minimal-harness/) |
| 02 | [What a harness actually is](./lecture-02-what-a-harness-actually-is/) | A harness is five subsystems working as one system | [Project 01](../projects/project-01-baseline-vs-minimal-harness/) |
| 03 | [Why the repository must become the system of record](./lecture-03-why-the-repository-must-become-the-system-of-record/) | What's not in the repo doesn't exist for the agent | Project 02 |
| 04 | [Why one giant instruction file fails](./lecture-04-why-one-giant-instruction-file-fails/) | Instructions must be a map, not a manual | Project 02 |
| 05 | [Why long-running tasks lose continuity](./lecture-05-why-long-running-tasks-lose-continuity/) | Continuity comes from externalized state, not context windows | [Project 03](../projects/project-03-multi-session-continuity/) |
| 06 | [Why initialization needs its own phase](./lecture-06-why-initialization-needs-its-own-phase/) | Sessions that start by improvising end by guessing | [Project 03](../projects/project-03-multi-session-continuity/) |

Lectures 07-14 (scope control, feature lists, evidence-based completion,
end-to-end verification, observability, clean state, loop engineering, graph
engineering) follow in the next release, in the same format.
