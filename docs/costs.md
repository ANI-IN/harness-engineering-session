# Costs

This page says what each course command and each assignment costs you, in two numbers: the most it
can cost at the caps, and what it cost when the course ran it. It then lists the caps and shows
three ways to check what you have spent. Terms are in the [glossary](glossary.md).

Every number comes from a file in this repository: the caps from `.env.example`, the prices from
`platform/config/prices.toml`, and the measured costs from the
[evidence pages](evidence/general.md#timings), the [instructor guide](instructor-guide.md), and the
reference solutions of the assignments.

## What you pay for

Two accounts, and only one of them bills you:

| Account | What it costs | Notes |
|---|---|---|
| OpenAI API, Build tier | $5 of credit to reach the tier | Every live command spends from it |
| LangSmith, Developer plan | $0, with no card | Do not add a card |

On the free plan, "Personal organizations are limited to 5,000 traces per month until a credit card
is added" ([LangSmith billing](https://docs.langchain.com/langsmith/billing)). If the program emailed
you an OpenAI key, use it instead of creating your own; the [FAQ](faq.md) explains both ways.

## Commands

At the caps, one arm costs at most $0.20, one blinded review at most $0.04, and one final arm at
most $0.25. So one arm with its review is at most $0.24, and an A/B is at most $0.48.

Two measurements of the class commands, both on 2026-10-18 with the class profile: two runs of
each that ran alone, the demo guide's run ([runs](evidence/general.md#guide-runs-2026-10-18)) and a
reviewer's run on a fresh clone, and the range over three earlier runs of each
([runs](evidence/general.md#demo-runs-after-the-speed-up)).

| Command | At most, at the caps | Two runs, each alone | Three earlier runs |
|---|---|---|---|
| `make setup`, `doctor`, `warm`, `console`, `up` | $0 (no model calls) | $0 | $0 |
| `make show-1` | $0.24 | $0.020 to $0.021 | $0.021 to $0.023 |
| `make show-2 SESSION_BUDGET=12,38` | $0.24 | $0.036 to $0.044 | $0.036 to $0.038 |
| `make show-3` | $0.24 | not run | $0.0172 (one run, 2026-10-17) |
| `make show-4` | $0.24 | $0.026 to $0.028 | $0.023 to $0.033 |
| `make demo-3 FEATURE=version-checks` (an A/B) | $0.48 | $0.050 to $0.056 | $0.037 to $0.053 |
| `make final`, per feature | $0.58 | $0.038 to $0.042 (Feature 5: Bulk close) | $0.044 to $0.048 |
| `uv run shipharness testgen ...` | $0.20 | not run | $0.0033 in Assignment 4: Verification |
| `make replay`, `make swap-N`, `make example-N` | $0 (no model calls) | $0 (`make replay`) | $0 |
| `make check-assignment-N`, `uv run shipharness report` | $0 (no model calls) | not run | $0 |
| `uv run shipharness init`, `uv run shipharness check` | $0 (no model calls) | not run | $0 |

The whole live class plan (three `make show-N` runs, one `make demo-3`, two final features) needs at
most $2.36 at the caps, under the $2.50 session cap. At the high end of each measured range it cost
about $0.25; the five live runs of 2026-10-18 (one final feature) cost $0.183679 together.

## Assignments

Each assignment has one live step; everything else runs offline at $0.

| Assignment | Live step | At most | Measured, reference solution |
|---|---|---|---|
| Assignment 1: Instructions | An experiment: 8 tasks, 3 runs per arm | $2.50 (the command stops there) | $0.5453 |
| Assignment 2: State and sessions | Three forced stops on one task | $0.40 | $0.0270 |
| Assignment 3: Scope and sandbox | One A/B on Feature 3: Safe retries for issue creation | $0.48 | $0.0217 |
| Assignment 4: Verification | One testgen run and one A/B on Feature 4: Version checks on issue edits | $0.68 | $0.0454 |

The course's budget for the four together is $6 of OpenAI usage and 400 LangSmith traces: course
policy for the class and the assignments, not a measured figure. Run each
live step once, after your offline work passes its self-check: the evidence must match the code you
hand in.

## The caps

The cost tracker checks every model call against these caps before it sends it. A call that would
cross a cap is refused, and the run ends as `ABORTED: cap`; the referee still scores it. Commands
running at the same time share the caps.

| Cap (in `.env.example`) | Value | What it covers |
|---|---|---|
| `MAX_RUN_COST_USD` | $0.20 | One arm of one run; also one `testgen` run |
| `MAX_FINAL_RUN_COST_USD` | $0.25 | One arm of one `make final` run |
| `MAX_REVIEW_COST_USD` | $0.04 | One blinded review |
| `MAX_SESSION_COST_USD` | $2.50 | Every command under one class date or one purpose |
| `MAX_BATCH_COST_USD` | $2.50 | Any single command |
| `MAX_EXPERIMENT_TOTAL_USD` | $25.00 | All `shipharness experiments` batches |
| `MAX_BUILD_TOTAL_USD` | $15.00 | Every model call in this machine's cost ledger |

The session is picked by `PURPOSE`: `class` (one session per class date), `pilot`, or `assignment`.
Run your own demos with `PURPOSE=assignment`, so they do not use up a class date's session.

Prices per 1M tokens, from `platform/config/prices.toml`:

| Model and tier | Input | Cached input | Output |
|---|---|---|---|
| gpt-6-luna (agent), Standard | $0.10 | $0.01 | $0.50 |
| gpt-6-luna (agent), Fast | $0.20 | $0.02 | $1.00 |
| gpt-5.6-luna (reviewer), Standard | $0.20 | $0.02 | $1.20 |

## Check what you spent

### The cost line

Every live command ends with a `Cost:` line. This one is from the course's own final project run:

> Your output will differ: run times, ids, and the agent's wording change on every run.

```text
Cost: $0.038253 (this command: gpt-5.6-luna $0.004675, gpt-6-luna $0.033578; session $0.060114 of $2.50; build $0.060114 of $15.00 ($14.939886 left))
```

Read it left to right: what this command cost, split by model; what the session has spent of its
$2.50 cap; and what every command on this machine has spent of the $15.00 build cap, with what is
left.

### The ledger

`.shipharness/ledger.jsonl` holds one line per model call: the model, the service tier the response
reported, and the cost. It is git-ignored and stays on your machine. The build total on the cost
line is the sum of this file.

### The OpenAI usage page

The [OpenAI usage page](https://platform.openai.com/usage) shows what your API key really spent, by
day and by model. Compare it with your cost lines after your first live run. The billing page shows
your credit balance.

## Traces expire

LangSmith keeps an ordinary trace for 14 days: "Base traces have the base retention and are
short-lived (14 days)" ([LangSmith billing](https://docs.langchain.com/langsmith/billing)). Copy the
trace links you need for a report or a portfolio before then. The score records in `exports/scores/`
stay on disk and keep the links (`trace_url`, `referee_trace_url`), but a link stops working once
its trace has expired.

## Sources

- Source 1: LangSmith billing, <https://docs.langchain.com/langsmith/billing>, LangChain (LangSmith docs), n.d.
