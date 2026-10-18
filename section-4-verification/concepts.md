# Section 4: Verification. Concepts: what proves the work is done

Reading time: about 15 minutes.

## The problem

**Illustrative scenario.** Sam's team runs TeamTrack, a multi-tenant issue tracker. Sam asks a coding
agent for optimistic concurrency (refusing an edit made from a stale copy) on issue edits: `GET`
returns an `ETag`, and a write with a stale `If-Match` header is refused and changes nothing.

The agent adds the header check, writes a test for the happy path, and runs the suite. Every test
passes, because none of them sends a stale header. The agent reports: "Done, the full suite passes."
The reviewer sees a green build and a confident summary, and approves. After release, two people who
edit one issue still overwrite each other.

Nobody lied. The agent checked what it could see, and what it could see was not the feature.

> **Terms on this page**
>
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Done claim**: The agent's call `finish(claim="done")`, which says the phase's work is complete.
> - **Verify gate**: The checks that run in the agent's container when it claims done; a failure sends the claim back.
> - **Clean state**: All work committed, ruff clean on changed files, one migration head (a single latest migration), no debug output.
> - **Test phase**: A short second phase in which the agent writes tests for the feature it built.
> - **Test filters**: Five checks a test from the test phase must pass to be kept.
> - **Hidden tests**: Held-out tests: the agent never sees them; the referee runs them after the agent stops.
> - **Mutant**: A copy of the code with one small planted fault; a test that fails on it catches it.
> - **Referee mutants**: Planted faults the agent never sees; the referee counts how many the shipped tests catch.
> - **House rules**: TeamTrack's seven rules for every endpoint: tenant isolation, roles, API conventions, safe retries, audit log, layering, migrations.
> - **Reward hacking**: Passing the checks without doing the task they stand for.
> - **Primary measure**: The one result, chosen before any run, that decides the comparison.
>
> All terms: [glossary](../docs/glossary.md).

## The idea in one sentence

Do not let the agent decide when it is done: check its claim with code it does not control, keep
only tests that prove something, and score the result with tests and faults it never sees.

## How it works

Two causes sit behind the scenario. The first is self-grading. Anthropic's harness team found that
"agents reliably skew positive when grading their own work." Their fix is structural: separate "the
agent doing the work from the agent judging it"
([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).

The second is that green tests are not a finished feature. Anthropic's compiler team: "it is easy to
see tests pass and assume the job is done, when this is rarely the case."
([Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler))

[SpecBench](https://arxiv.org/abs/2605.21384) measured the gap: "while every frontier agent saturates the visible suite, reward hacking
persists". Deliberate cheating was rare; "compositional failures account for a much larger fraction"
([SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents](https://arxiv.org/abs/2605.21384)).
Feature 4: Version checks on issue edits has that shape. The
`ETag`, the header check, and the edit form each work alone. The lost update appears only when two writers meet.

The verification layer answers with four checks, each owned by someone other than the agent:

| Check | When | What it asks |
|---|---|---|
| Verify gate | When the agent claims done | Do the visible tests, existing tests, house rules, board, and clean state pass? |
| Test filters | After the test phase | Does each new test run, pass five times, and add something? |
| Hidden tests | After the agent stops | Does the feature work as the spec says, in combination? |
| Referee mutants | After the agent stops | Would the shipped tests catch the faults we fear? |

![The done claim goes to the verify gate, then the test phase, the five filters, the referee, and the verdict](diagrams/verification-pipeline.svg)

*The agent's claim starts the checks; it never ends them.*

The filters come from Meta's [TestGen-LLM](https://arxiv.org/abs/2402.09171), which keeps a generated test only after "a series of
progressively demanding semantic filters"
([Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171)).
The course runs five, cheapest first:

| Filter | What it checks | Source |
|---|---|---|
| Filter 1: Builds and collects | Pytest collects it, with no errors | [TestGen-LLM](https://arxiv.org/abs/2402.09171) |
| Filter 2: Passes five runs | It passes 5 runs in a row | [TestGen-LLM](https://arxiv.org/abs/2402.09171): "every one of five executions" |
| Filter 3: Adds coverage or catches a mutant | It adds line coverage, or catches a mutant no existing test catches | [TestGen-LLM](https://arxiv.org/abs/2402.09171) and [ACH](https://arxiv.org/abs/2501.12862) |
| Filter 4: Real assertions | It has real assertions and does not mock the code under test | Course filter |
| Filter 5: No source changes | No source file changed during the test phase | Course filter |

Filter 3 has a mutant branch because Meta's [ACH](https://arxiv.org/abs/2501.12862) found that "49%" of tests that catch a new mutant
"do not also add line coverage" ([Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)).
Filters 4 and 5 are the course's own.

![Original code, a mutant, a test that fails on the mutant, and a test that passes on it](diagrams/mutation-testing.svg)

*Test B passes on the broken code, so it would not catch a lost update; test A would.*

### Before and after

**Before: the agent's word.** In the bare arm, `finish(claim="done")` ends the phase. In one test run
before class, a bare arm ended its build with "Verified the complete visible suite (191 passing)".
The referee then found a hidden test failing ([evidence](../docs/evidence/s4.md#s4-claims)).

**After: a gate on the claim.** In the harness arm, the same call starts the gate. A failure comes
back as the result of `finish`: "Not accepted.", one line that names the failed items, up to three
failure lines, and "Fix these, commit your work, and call finish again." The phase continues, and
the agent fixes what failed. Only a passed gate lets the scope layer set `passes` to true.

## How shipharness does it

The gate's check list is short, and what it leaves out is the point:

```python
# platform/src/shipharness/harness/verify/gate.py (lines 34-44)
GATE_CHECKS: tuple[str, ...] = (
    "r1_tenant",
    "r2_roles",
    "r3_conventions",
    "r4_idempotency",
    "r5_audit",
    "r6_layering",
    "r7_migrations",
    "regression",
    "board",
)
```

The gate runs these, plus the visible tests and clean state, in the arm's own container. The hidden
tests and the referee mutants are not in the list, nor in the arm's workspace, so they stay held out.
The mutants come in two sets that share no mutation: a filter set for Filter 3, and a referee set
for scoring. The referee also runs the seven house rules; that overlap is disclosed, so Section 4 scores hidden
tests and mutants instead. The [walkthrough](demo/walkthrough.md) reads the gate line by line.

A separate model also reviews each final diff. Its verdict is secondary, because "the evaluator is
still an LLM that is inclined to be generous towards LLM-generated outputs." (Source 1)

## What we measured

Before class, the course ran both arms on the ticket for Feature 4. The primary measure: a run passes only with all 69
hidden tests passed and all 4 referee mutants caught.

| Setting | Bare arm: runs failing | Harness arm: runs failing |
|---|---|---|
| Medium effort, first round | 3 of 3 | 3 of 3 |
| Medium effort, second round | 3 of 3 | 3 of 3 |
| Low effort, fast tier (class settings) | 1 of 1 | 1 of 1 |

![Dot chart for the version checks ticket: every run of both arms failed](diagrams/results-s4.svg)

*One dot per run: both arms failed all 7 runs, so there is no measurable difference.*

No measurable difference on this task with this model; both arms failed every run
([evidence](../docs/evidence.md#section-4)). The gate never ran in these runs: no harness arm claimed
done on that ticket. In the captured demo run, the
gate passed every item on the first claim, and the referee still failed the run on one hidden test
and 0 of 4 mutants.

## When it helps, and when it does not

It helps when:

- The agent can claim done before the work is done.
- Some checks stay out of the agent's reach, so a green gate is not the last word.
- The agent writes tests you will keep. Filters stop flaky or empty ones.

It does not help, or helps less, when:

- The agent never claims done. A gate on the claim never runs; in the test runs it did not.
- The bug is in the code and the test is right. Filter 2 keeps only passing tests, so it discards
  the test that found the bug. ACH: it "cannot detect existing faults residing in the code base".
- The checks are wrong. A strict gate on the wrong checks makes the agent solve the wrong problem.

Anthropic's harness team gives the test to apply: "every component in a harness encodes an assumption
about what the model can't do on its own, and those assumptions are worth stress testing." The
verification layer assumes the agent's "done" and its own tests cannot be trusted (Source 1).

## Key takeaways

- The agent's "done" is a claim, not a result. Check it with code that runs where the agent cannot
  edit it.
- Keep some checks held out. Hidden tests and planted faults tell you whether the work is right; a
  gate the agent can see tells you only whether it passed the gate.
- Filters keep tests that prove something new, and treat the current code as correct. Read every
  discard reason: a failing test may be the one that found the bug.

## Check your understanding

1. The bare arm's visible suite passed 191 tests. Why was its done claim still wrong?
2. Why does the gate not run the hidden tests, when they would catch more bugs?
3. In the demo run, Filter 2 discarded a test that failed with "assert 422 == 412". Was the test
   wrong?
4. Filter 3 keeps a test that catches a mutant even if it adds no coverage. Why?

<details>
<summary>Answers</summary>

1. The hidden test that failed combines an invalid body with a stale version. The visible suite did
   not check that case.
2. A check the agent gets feedback from becomes a target.
3. No. It expected 412, the spec's answer, and the code returned 422. Filter 2 assumes the code is
   correct, so it discards a failing test.
4. Coverage says a line ran, not that a test would notice it going wrong. About half of the
   mutant-catching tests in Source 5 added no coverage.

</details>

## Further reading

- [Filters for generated tests](post-class-reading/01-testgen-llm-filters.md)
- [Mutation-guided tests](post-class-reading/02-mutation-guided-tests-ach.md)
- [Separate evaluators](post-class-reading/03-separate-evaluator.md)
- [Held-out tests](post-class-reading/04-held-out-tests-specbench.md)

## Sources

- Source 1: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 2: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
- Source 3: SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents, <https://arxiv.org/abs/2605.21384>,
  Zhao, Srikanth, Wu, and Jiang (Weco AI), 2026-05-20
- Source 4: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>,
  Alshahwan et al. (Meta), 2024-02-14
- Source 5: Mutation-Guided LLM-based Test Generation at Meta, <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta),
  2025-01-22
