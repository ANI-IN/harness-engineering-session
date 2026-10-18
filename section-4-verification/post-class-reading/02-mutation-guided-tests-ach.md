# [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)

Reading time: about 60 minutes.
Source: [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862), Foster et al. (Meta), submitted to FSE 2025 Industry Track, 2025-01-22 ([evidence](../../docs/evidence/s4.md#src-ach)).

> **Terms on this page**
>
> - **Mutant**: A copy of the code with one small planted fault; a test that fails on it catches it.
> - **Referee**: The program that scores each run after the agent stops.
> - **Referee mutants**: Planted faults the agent never sees; the referee counts how many the shipped tests catch.
> - **Filter set**: Planted faults that Filter 3: Adds coverage or catches a mutant may use while the agent works; they never repeat a referee mutant.

## Why it matters

Coverage tells you that a test ran a line. It does not tell you whether the test would notice that
line going wrong in the way you fear. Meta's [ACH](https://arxiv.org/abs/2501.12862) starts from the fault instead: describe a bug you
care about, plant it, and keep a test only if it catches the bug. Section 4: Verification scores
every run this way, with planted faults on the riskiest lines of each feature.

## Three key ideas

1. **Start from the fault you fear.** [ACH](https://arxiv.org/abs/2501.12862) asks for faults "that are both relevant to the issue of
   concern and also currently not caught (unkilled) by any existing test case". Then it asks for
   "extra test cases that will fail on the mutant version of the class, but would pass on the correct
   version." The concern in the paper is privacy; in TeamTrack it is a lost update or a tenant leak.

2. **Catching a fault is a different signal from coverage.** "a large proportion (49%) of test cases
   that uniquely additionally kill a mutant, do not also add line coverage." A coverage-only filter
   would have dropped all of them. That is why the course's Filter 3 keeps a test that adds coverage
   or catches a planted fault.

3. **The current code is the oracle.** [ACH](https://arxiv.org/abs/2501.12862) says of its tests: "This allows us to protect against
   future regressions, but it cannot detect existing faults residing in the code base." A generated
   test that fails on today's code is not kept, even when today's code is the one that is wrong.

The course keeps the idea and changes the machinery. Its mutants are written by hand, one record per
fault, so they can target chosen lines. One record for Feature 4: Version checks on issue edits turns
`issue.version += 1` into `+= 0`, so
"stale If-Match values still match (lost update)". The faults are split into a filter set and a
referee set that share no mutation. The referee then judges the shipped tests with faults they were
never written against.

## Apply it to your repo

1. Pick the line in your service whose failure would hurt a customer most: a permission check, a
   version bump, a tenant filter.
2. Write the fault as two lines: the original and the replacement. Apply it by hand on a branch.
3. Run your suite. If nothing fails, no test protects that line. Write the test that fails on the
   fault and passes on the real code.
4. Keep the fault in a file next to your tests, and re-apply it in CI now and then.
5. If you use faults to steer an agent's tests, keep a second set it never sees, and judge with that
   one.

## Sources

- Source 1: Mutation-Guided LLM-based Test Generation at Meta (ACH), <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta),
  2025-01-22
