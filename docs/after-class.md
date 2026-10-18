# After class

> **Terms on this page**
>
> - **Bare arm**: an agent run with the ticket and the repository, and no harness.
> - **Harness arm**: the same run with the harness turned on.
> - **A/B**: bare arm and harness arm on the same ticket, scored the same way.
> - **Referee**: the program that scores each run after the agent stops.
> - **Primary measure**: the one result each section is judged on, fixed before any run.
> - **Trace**: the record of one run's steps (each model call and tool call), stored in LangSmith.
> - **Gate**: a pass mark set before the runs; here, the result the test runs had to reach before
>   the course would pay for larger batches.
> - **Replay**: a recorded run played back on the console, with no model calls.

This page covers the days between the live class and the review session: keep your results, read
them again, run things yourself, do the four assignments, read further, and point the tools at your
own repository.

## Keep what you have

- Your `.shipharness/runs/` and `exports/` folders are git-ignored and exist only on your machine.
  Every run counts as one result, aborted ones included, so do not delete runs you want to report.
- LangSmith keeps an ordinary trace for 14 days: "Base traces have the base retention and are
  short-lived (14 days)" ([LangSmith billing](https://docs.langchain.com/langsmith/billing), read
  2026-10-17). Copy the trace links you need. The score records in `exports/scores/` stay on disk
  and hold the links (`trace_url`, `referee_trace_url`).

## Read the results again, slowly

In class, [Section 1: Instructions](../section-1-instructions/README.md),
[Section 2: State and sessions](../section-2-state-lifecycle/README.md), and
[Section 4: Verification](../section-4-verification/README.md) of Module 1 showed the harness arm
alone, live (`make show-N`). [Section 3: Scope and sandbox](../section-3-scope-sandbox/README.md)
and the final each ran a live A/B. One run is one result: read it next to the
course's test runs, never alone, because model output varies between runs. The test runs found no
measurable difference on this model in any section's primary measure, except the Section 3
confirmation, where the harness arm kept inside its allowed paths in 3 of 3 runs and the bare arm in
0 of 3 ([evidence](evidence/general.md#s3-confirmation)).

Write every recorded run into one report:

```bash
uv run shipharness report
```

It reads only `exports/` and writes `exports/report.json` and `exports/report.html`, with one dot per
run for every feature that has a primary measure (the four section features, Features 1 to 4:
Feature 1: Org-wide issue search, Feature 2: Comments on issues, Feature 3: Safe retries for issue
creation, and Feature 4: Version checks on issue edits). It makes no model calls. Replays are
left out unless you add `--include-recorded`. How to read one result, field by field, is in the
[final project](../final-project/README.md#what-the-result-means).

## Run a demo yourself

You can repeat any section's run on your own machine. Each one calls OpenAI live and costs real
money, within the caps in `.env.example`:

| Command | What it runs | At most |
|---|---|---|
| `make show-1 PURPOSE=assignment` | The harness arm alone, as in class | $0.24 |
| `make demo-1 PURPOSE=assignment` | An A/B: both arms, both scored | $0.48 |
| `make demo-3 FEATURE=version-checks PURPOSE=assignment` | The Section 3 A/B from class, on Feature 4 | $0.48 |

`PURPOSE=assignment` traces to `shipharness-assignments` with its own cost session. Without it, the
command runs as a class command and needs `SHIPHARNESS_CLASS_DATE` in `.env`. The make targets use the
class profile; add `PROFILE=standard` to use the settings in your `.env` instead. Watch the run with
`make console` in a second terminal. What to watch for each section is in its demo page:
[Section 1](../section-1-instructions/demo/README.md), [Section 2](../section-2-state-lifecycle/demo/README.md),
[Section 3](../section-3-scope-sandbox/demo/README.md), [Section 4](../section-4-verification/demo/README.md).

To see what one layer adds, remove it. `make demo-2 LAYERS=-state` runs the Section 2 A/B with the
harness arm keeping only the instructions layer. This is the method Anthropic describes: "removing
one component at a time and reviewing what impact it had on the final result"
([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).
The course planned a larger batch of such runs but did not run it, because its gate did not pass
([evidence](evidence/general.md#gate)). A few runs of yours are a small version of it.

`make replay RUN=<id>` replays a run you recorded, with RECORDING on every screen. `make swap-N`
re-scores your latest A/B of that section with the labels swapped, at no cost. In both commands the
id comes from the console's run list.

## Do the assignments

Each assignment has grading criteria (100 points), a starter folder, an offline self-check, and one
live step. Work in the order of the sections.

| Assignment | Page | Self-check |
|---|---|---|
| Assignment 1: Instructions | [README](../section-1-instructions/assignment/README.md) | `make check-assignment-1` |
| Assignment 2: State and sessions | [README](../section-2-state-lifecycle/assignment/README.md) | `make check-assignment-2` |
| Assignment 3: Scope and sandbox | [README](../section-3-scope-sandbox/assignment/README.md) | `make check-assignment-3` |
| Assignment 4: Verification | [README](../section-4-verification/assignment/README.md) | `make check-assignment-4` |

The course's budget for the four together is $6 of OpenAI usage and 400 LangSmith traces, a course
policy for the class and the assignments, and no single command may spend more than $2.50 (`MAX_BATCH_COST_USD` in `.env.example`). Each assignment
page gives the cost of its live step.

On a fresh clone every self-check fails, with FAIL lines that name what to fix. That is the starting
point. Try each assignment yourself first; the full solution is in its `solution/` folder, next to
the starter.

## Read further

Start with each section's session notes, then its reading list:

| Section | Session notes | Reading list |
|---|---|---|
| Section 1 | [notes](../section-1-instructions/session-notes.md) | [reading](../section-1-instructions/post-class-reading/README.md) |
| Section 2 | [notes](../section-2-state-lifecycle/session-notes.md) | [reading](../section-2-state-lifecycle/post-class-reading/README.md) |
| Section 3 | [notes](../section-3-scope-sandbox/session-notes.md) | [reading](../section-3-scope-sandbox/post-class-reading/README.md) |
| Section 4 | [notes](../section-4-verification/session-notes.md) | [reading](../section-4-verification/post-class-reading/README.md) |

Every source this page names is linked in the Sources list at the end. Anthropic's advice to anyone
who builds a harness is to "read its traces on realistic problems" (Source 2); your LangSmith
project from class is a good place to start.

## Apply it to your own repository

[Use it in your repo](../use-in-your-repo/README.md) has the starter kit, four skills, and a
step-by-step guide. The quickest start copies the kit, with no model calls:

```bash
uv run shipharness init --target ~/my-repo
```

Here `~/my-repo` stands for the path to a repository of yours. The
[final project](../final-project/README.md#use-it-on-your-own-repository) shows the other commands
and how to read their output.

## The review session

The review session goes through the four assignments: the expected approach, the reference solution,
common mistakes, and discussion. Bring your self-check output and one question per assignment.

## Sources

- Source 1: LangSmith billing, <https://docs.langchain.com/langsmith/billing>,
  LangChain (LangSmith docs), n.d.
- Source 2: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
