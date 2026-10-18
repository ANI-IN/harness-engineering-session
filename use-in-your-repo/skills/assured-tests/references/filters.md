# Why each filter exists

Sources are listed at the end of this page: [TestGen-LLM](https://arxiv.org/abs/2402.09171) and
[ACH](https://arxiv.org/abs/2501.12862) are the two Meta papers. Filters 1 to 3 come from the
papers; Filters 4 and 5 are the course's own, with no direct source, and are presented as such.

## Filter 1: Builds and collects

- Rule: pytest collects the test and runs it without a collection or import error.
- Source: the first filter in [Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171) "simply checks that the candidate code is fully buildable within the
  existing infrastructure of the app under test". Python has no build step, so the course
  reads "buildable" as "collected and run by pytest".
- Catches: hallucinated imports, wrong fixture names, syntax errors.
- Misses: everything about what the test checks.

## Filter 2: Passes five runs

- Rule: the test passes on its first run and on each of five runs.
- Source: Source 1 discards "any test case that does not pass on first execution", because without an
  automated oracle a failing test cannot tell a bug from a wrong test, and "a test that does not
  pass on every one of five executions is deemed flaky".
- Catches: tests that fail on correct code, and most flaky tests.
- Misses: flakiness that shows up less often than one run in five; tests that pass by checking
  nothing.
- Note: the number five is [TestGen-LLM](https://arxiv.org/abs/2402.09171)'s. [ACH](https://arxiv.org/abs/2501.12862) asks for tests that "pass and do so consistently"
  without restating a count, so do not attribute "five runs" to [ACH](https://arxiv.org/abs/2501.12862).

## Filter 3: Adds coverage or catches a mutant

- Rule: the test covers at least one line the existing suite does not, or it kills a filter-set
  mutant (a copy of the code with one small bug planted on purpose) that no existing test kills.
- Source, coverage branch: Source 1 discards "Any test that does not improve coverage". Source 1
  measures line coverage only.
- Source, mutant branch: [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862) builds mutants "that denote faults that are both relevant to the issue
  of concern and also currently not caught (unkilled) by any existing test case", and keeps tests
  that catch them: "Hardening: The new tests catch faults that no existing test can catch".
- Why both: in Source 2, 49% of the tests that uniquely kill a mutant add no line coverage. A
  coverage-only filter would throw those tests away.
- Course detail: mutants are split into a filter set, which this filter uses, and a referee set (mutants
  kept apart to judge the kept tests). A test is never judged by the same mutants that selected it.
- Misses: faults that no mutant simulates, in lines that are already covered.

## Filter 4: Real assertions

- Rule: the test contains at least one assertion that can fail, and it does not replace the
  function or class it tests with a mock. Checked on the test's syntax tree.
- Source: none in Source 1 or Source 2. This is a course filter. It exists because a test
  with `assert True`, or one that mocks the code it claims to test, can pass filters 1-3: it runs,
  passes reliably, and executes new lines.
- Misses: weak assertions that are technically able to fail.

## Filter 5: No source changes

- Rule: the hash of every source file at the end of the test phase equals its hash at the start.
- Source: a composite of two statements. Source 1 keeps every existing test and only adds,
  "guaranteeing there will be no regression, by construction". [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) tells agents "It is
  unacceptable to remove or edit tests because this could lead to missing or buggy functionality".
  The course applies the same protection in the other direction: in the test phase the
  code under test is fixed.
- Catches: an agent that edits the code to make its own test pass.

## What "assured" means here

Source 1 calls its approach Assured LLM-based Software Engineering: a kept test comes with guarantees
that were checked, not claimed. In this skill the guarantees are exactly the five filters
above, no more. A kept test still needs a human review of whether it tests the right behaviour; Source 1
describes [TestGen-LLM](https://arxiv.org/abs/2402.09171) as a recommender "that leaves the software engineer in ultimate control".

## Sources

- Source 1: Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM),
  <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
- Source 2: Mutation-Guided LLM-based Test Generation at Meta (ACH),
  <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta), 2025-01-22
- Source 3: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
