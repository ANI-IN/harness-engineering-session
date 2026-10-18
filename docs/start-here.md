# Start here

This page is the learning path through Module 1: Harness Engineering for Coding Agents, in order.
Follow it top to bottom: set up once, then work through Section 1: Instructions to Section 4:
Verification, then the final project, then your own repository. New words are in the
[glossary](glossary.md); money questions are on the [costs page](costs.md); common questions are in
the [FAQ](faq.md).

## How the times were set

Each step gives a time, so you can plan your week. Every time on this page is one of two kinds:

- **Reading time**: the page's word count divided by 200, rounded up to 5 minutes, the course's rule
  for reading times. Where a page prints its own reading time at the top, this page uses that one.
- **Run time**: how long the command took on the course machine, from the
  [evidence page](evidence/general.md#timings) and the
  [live runs of 2026-10-18](evidence/general.md#guide-runs-2026-10-18).

The course has not timed the hands-on work: installing the tools, or writing the code of an
assignment. Those rows give the reading time of the pages and say that the work is extra.

A live run's time is mostly waiting. Read the next page while it runs.

To follow the five live demos step by step, use the [Live Demo Guide](../guide/README.md)
([PDF](../guide/Harness%20Engineering%20Demo%20Guide.pdf)).

## The path at a glance

| Step | What you do | Reading and run time |
|---|---|---|
| 1. Setup | Accounts, tools, keys, `make doctor`, a first live run | 45 minutes, plus the installs |
| 2. Section 1: Instructions | README, concepts, demo, assignment, reading | 2 h 55 min, plus the assignment work |
| 3. Section 2: State and sessions | README, concepts, demo, assignment, reading | 2 h, plus the assignment work |
| 4. Section 3: Scope and sandbox | README, concepts, demo, assignment, reading | 2 h, plus the assignment work |
| 5. Section 4: Verification | README, concepts, demo, assignment, reading | 4 h 20 min, plus the assignment work |
| 6. Final project | One A/B on a new feature, then read the result | 45 minutes |
| 7. Use it in your repo | Copy the kit, write a map, add checks | 25 minutes, plus the work in your repository |

Each total adds up the rows of its table below, taking the longer end of a range, rounded up to 5 minutes.
Run times are the range over three runs of each command, measured 2026-10-18 with the class
profile, from launch to the full verdict; the command ends a few seconds later.

## Step 1: Setup

Start at [setup](../setup/README.md). It takes a machine with nothing installed to a first live run,
on Windows (through WSL2), Linux, or macOS.

| Part | Page | Time |
|---|---|---|
| Accounts, tools, clone, `.env` | [setup](../setup/README.md) and your system's page | 20 to 25 minutes of reading, plus the installs |
| Build both images | `make setup` | 145 s on the course machine (run time) |
| First live run | `make show-1` | 3:37 to 4:45 (two runs, 2026-10-18, each alone; earlier: 7:23 to 10:58) |
| Before a live class | [pre-class checklist](../setup/pre-class.md) | 5 minutes (reading) |

`make doctor` must end with `result: + ready` before you go on.

## Steps 2 to 5: the four sections

Every section has the same parts, in the same order. Work through them in this order:

1. The section README: the problem, why it happens, and how the layer fixes it.
2. `concepts.md`: the idea, how it works, and what the course measured.
3. The demo: run it, watch the console, then read the demo page and the code walkthrough.
4. The assignment: build the layer yourself, run its self-check, then its one live step.
5. The post-class reading and the session notes.

### Section 1: Instructions

| Part | Page | Time |
|---|---|---|
| README | [Section 1](../section-1-instructions/README.md) | 5 minutes (reading) |
| Concepts | [concepts.md](../section-1-instructions/concepts.md) | 15 minutes (reading) |
| Demo run | `make show-1` | 7:23 to 10:58 (run time) |
| Demo page and walkthrough | [demo](../section-1-instructions/demo/README.md) | 15 minutes (reading) |
| Assignment 1: Instructions | [assignment](../section-1-instructions/assignment/README.md) | 25 minutes (reading the README and the spec), plus the work |
| Reading | [three readings](../section-1-instructions/post-class-reading/README.md) | 100 minutes (reading) |

Assignment 1 has eight steps; its live step runs 8 tasks with 3 runs per arm, so start it early.

### Section 2: State and sessions

| Part | Page | Time |
|---|---|---|
| README | [Section 2](../section-2-state-lifecycle/README.md) | 5 minutes (reading) |
| Concepts | [concepts.md](../section-2-state-lifecycle/concepts.md) | 15 minutes (reading) |
| Demo run | `make show-2 SESSION_BUDGET=12,38` | 5:10 to 6:59 (run time) |
| Demo page and walkthrough | [demo](../section-2-state-lifecycle/demo/README.md) | 20 minutes (reading) |
| Assignment 2: State and sessions | [assignment](../section-2-state-lifecycle/assignment/README.md) | 20 minutes (reading the README and the spec), plus the work |
| Reading | [three readings](../section-2-state-lifecycle/post-class-reading/README.md) | 50 minutes (reading) |

### Section 3: Scope and sandbox

| Part | Page | Time |
|---|---|---|
| README | [Section 3](../section-3-scope-sandbox/README.md) | 5 minutes (reading) |
| Concepts | [concepts.md](../section-3-scope-sandbox/concepts.md) | 15 minutes (reading) |
| Demo run | `make demo-3 FEATURE=version-checks` | 7:31 to 9:43 (run time) |
| Demo page and walkthrough | [demo](../section-3-scope-sandbox/demo/README.md) | 20 minutes (reading) |
| Assignment 3: Scope and sandbox | [assignment](../section-3-scope-sandbox/assignment/README.md) | 25 minutes (reading the README and the spec), plus the work |
| Reading | [three readings](../section-3-scope-sandbox/post-class-reading/README.md) | 45 minutes (reading) |

### Section 4: Verification

| Part | Page | Time |
|---|---|---|
| README | [Section 4](../section-4-verification/README.md) | 5 minutes (reading) |
| Concepts | [concepts.md](../section-4-verification/concepts.md) | 15 minutes (reading) |
| Demo run | `make show-4` | 5:32 to 8:02 (two runs, 2026-10-18, each alone) |
| Demo page and walkthrough | [demo](../section-4-verification/demo/README.md) | 20 minutes (reading) |
| Assignment 4: Verification | [assignment](../section-4-verification/assignment/README.md) | 20 minutes (reading the README and the spec), plus the work |
| Reading | [four readings](../section-4-verification/post-class-reading/README.md) | 190 minutes (reading) |

Assignment 4 has ten steps, two of them live (a test-generation run and one A/B), plus a portfolio.

## Step 6: Final project

The [final project](../final-project/README.md) runs the whole harness on a new feature, one of
Feature 5: Bulk close, Feature 6: Watchers, or Feature 7: Labels, as one A/B. Three bulk close runs,
measured 2026-10-18, took 8:41 to 15:22 from launch to the harness arm's full verdict (run time). Reading the project page takes 15
minutes and its [code walkthrough](../final-project/walkthrough.md) 10 minutes. Its
[checklist](../final-project/CHECKLIST.md) lists what to hand in.

## Step 7: Use it in your repo

[Use it in your repo](../use-in-your-repo/README.md) has the starter kit, four skills, and a
step-by-step guide. Copying the kit makes no model calls:

```bash
uv run shipharness init --target ~/my-repo
```

Here `~/my-repo` stands for the path to a repository of yours. The overview and the step-by-step
guide take 25 minutes to read; the map, the house-rule checks, and one A/B on a ticket of your own
are work in your repository that the course has not timed.

## After class

[After class](after-class.md) covers the days up to the review session: keep your runs and trace
links, re-run a demo, and do the assignments. Bring your self-check output and one question per
assignment to the review session.
