# Section 4: Verification. Session notes: what proves the work is done

For learners, after class. Reading time: about 8 minutes.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Done claim**: The agent's call `finish(claim="done")`, which says the phase's work is complete.
> - **Verify gate**: The checks that run in the agent's container when it claims done; a failure sends the claim back.
> - **Test filters**: Five checks a test from the test phase must pass to be kept.
> - **Hidden tests**: Held-out tests: the agent never sees them; the referee runs them after the agent stops.
> - **Mutant**: A copy of the code with one small planted fault; a test that fails on it catches it.
> - **Referee mutants**: Planted faults the agent never sees; the referee counts how many the shipped tests catch.
> - **Primary measure**: The one result, chosen before any run, that decides the comparison.
> - **Reward hacking**: Passing the checks without doing the task they stand for.

## What we showed

| Block | What happened | Read it again |
|---|---|---|
| Poll | 2:55 to 2:57, the only poll of the class: it picks the final feature | [final-project/](../final-project/README.md) |
| Launch | 2:57, `make show-4`: harness arm alone on Feature 4: Version checks on issue edits | [demo/README.md](demo/README.md) |
| Final launch | 2:57, right after the poll: `make final` with the poll's winner, read in the final block | [final-project/](../final-project/README.md) |
| Concepts | The problem, the gate, the filters, held-out checks, what we measured | [concepts.md](concepts.md) |
| Walkthrough | The gate in 38 lines: pending pills, items in the container, the verdict | [demo/walkthrough.md](demo/walkthrough.md) |
| Demo | The finished run on screens 1, 3, 2, then the test-run results on screen 4 | [demo/README.md](demo/README.md) |

The class run's record stays on the instructor's machine. A captured run, with its screenshots, is in
[demo/expected/](demo/expected/README.md).

## Key ideas

1. **The agent's "done" is a claim.** "agents reliably skew positive when grading their own work."
   ([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps))
   Treat a done claim as the start of a check, not the end of the work.
2. **Separate the doer from the judge.** "Separating the agent doing the work from the agent judging
   it proves to be a strong lever to address this issue." In shipharness, the gate decides whether a
   claim stands, and only the harness sets `passes`.
3. **The verifier must be strict.** "it’s important that the task verifier is nearly perfect,
   otherwise Claude will solve the wrong problem."
   ([Anthropic, C compiler](https://www.anthropic.com/engineering/building-c-compiler)) One failed
   gate item fails the claim.
4. **Visible tests miss what held-out tests catch.** "while every frontier agent saturates the visible
   suite, reward hacking persists" ([SpecBench](https://arxiv.org/abs/2605.21384)). Most of the gap
   is features that pass alone and fail together.
5. **Keep tests that prove something.** Five filters, cheapest first: runs, passes five times, adds
   coverage or catches a mutant, has real assertions, and leaves the source alone
   ([Meta, TestGen-LLM](https://arxiv.org/abs/2402.09171)). Filters 4 and 5 are the course's own.
6. **Filters trust the current code.** A failing test is discarded, even when the test is right. ACH's
   limit: it "cannot detect existing faults residing in the code base"
   ([Meta, ACH](https://arxiv.org/abs/2501.12862)).
7. **Score with what the agent never sees.** The gate leaves out the hidden tests and the referee
   mutants, so they still measure held-out behaviour.
8. **A model reviewer is useful but lenient.** "the evaluator is still an LLM that is inclined to be
   generous towards LLM-generated outputs." Its verdict is a secondary measure.

## What the result showed

Before class, the course ran both arms on the version checks ticket. The primary measure: a run passes only with all 69
hidden tests passed and all 4 referee mutants caught. Runs failing, per arm:

| Setting | Bare arm | Harness arm |
|---|---|---|
| Medium effort, first round | 3 of 3 | 3 of 3 |
| Medium effort, second round | 3 of 3 | 3 of 3 |
| Low effort, fast tier (class settings) | 1 of 1 | 1 of 1 |

Model gpt-6-luna. The reviewer rejected all 14 arms and agreed with the referee each time
([evidence](../docs/evidence.md#section-4)).

No measurable difference on this task with this model. The gate was not tested in these runs: no
harness arm claimed done on that ticket. Six used all their build turns, and one stopped with `not_done`. Two
bare arms claimed done, and the referee failed both ([done claims](../docs/evidence/s4.md#s4-claims)).

The captured demo run filled that gap once. The harness arm claimed done, and the gate passed all 11
items on the first try. The referee then failed the run: 68 of 69 hidden tests, 0 of 4 mutants. The
failing hidden test checks a stale `If-Match` with an invalid body. The agent had written a test for
that very case; it failed with "assert 422 == 412", and Filter 2: Passes five runs discarded it.

Measures chosen after the results, so they describe and do not test: over 34 runs per arm across all
sections, harness arms claimed done in 10 and bare arms in 19. Harness arms shipped fewer tests
(median 2.5 against 7.5; on version checks, 0 against 15.5)
([post hoc measures](../docs/evidence/s4.md#s4-posthoc)).

## Questions from class

**The harness did not win. Was verification useless?**
On the version checks ticket the runs barely tested it: the gate never ran in an A/B, and the
filters saw few tests. That is a result about this task and this model. A separate judge "is worth the cost when the task sits
beyond what the current model does reliably solo."
([Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps))

**The bare arm caught more mutants. Does that mean the filters hurt?**
The bare arm shipped more tests. A test nobody writes cannot catch a mutant, and the filters judge
only the tests the test phase proposes.

**Why does the gate not run the hidden tests?**
They would stop being held out. Once the agent gets feedback from a check, the check becomes a
target.

**The gate and the referee both run the seven house rules. Is that fair?**
It is a disclosed overlap. The harness arm is expected to do better on those rules by construction, so
the primary measure uses hidden tests and mutants, which the gate never runs.

**Why does a broken test not count as catching a mutant?**
The referee counts a catch only with shipped tests that pass on the unmutated build. A test that
fails everywhere "catches" every mutant and proves nothing.

**Why are filters 4 and 5 not from a paper?**
No source states them. They guard against risks a coding agent adds: a test that mocks the code it
claims to test, and a test phase that edits the code until its test passes.

## What to try next

1. Start [Assignment 4: Verification](assignment/README.md). Run `make check-assignment-4` first; on the unchanged
   starter it fails by design, and each FAIL line names what to build.
2. Read the gate with `uv run python platform/scripts/anchors.py extract S4:gate`, then the filters
   with `S4:filters`.
3. Look at the options of filtered test generation with `uv run shipharness testgen --help`.
4. Read the [post-class readings](post-class-reading/README.md), about 20 minutes in total.
5. In your own repository, write one planted fault for the riskiest line, as an original line and a
   replacement. Apply it by hand and run your suite. If nothing fails, you have found a test to write.

## Sources

- Source 1: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 2: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
- Source 3: SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents, <https://arxiv.org/abs/2605.21384>, Zhao, Srikanth, Wu, and Jiang (Weco AI), 2026-05-20
- Source 4: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
- Source 5: Mutation-Guided LLM-based Test Generation at Meta, <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta), 2025-01-22
