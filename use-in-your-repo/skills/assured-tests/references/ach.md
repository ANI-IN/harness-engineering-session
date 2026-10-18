# Mutation-guided test generation at Meta, in short

Foster, Gulati, Harman, Harper, Mao, Ritchey, Robert, Sengupta (Meta).
[Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862). arXiv
2501.12862, 2025-01-22; submitted to the FSE 2025 Industry Track. The paper calls its tool
[ACH](https://arxiv.org/abs/2501.12862).

Summary in our own words; quotes are marked. Sources are listed at the end of this page.

## What it does

[ACH](https://arxiv.org/abs/2501.12862) starts from a concern written in plain text, for example a kind of privacy fault seen before.
A language model writes mutants: small changes to the code that simulate that fault. A second
model, used as a judge, removes mutants that behave the same as the original (equivalent mutants).
A modified [TestGen-LLM](https://arxiv.org/abs/2402.09171) then writes tests
that pass on the original code and fail on the mutant.

The target is mutants that are "relevant to the issue of concern and also currently not caught
(unkilled) by any existing test case". A kept test therefore catches a fault that no
existing test catches: [ACH](https://arxiv.org/abs/2501.12862) calls this "Hardening".

## Results reported

| Measure | Value | Where |
|---|---|---|
| Scale | 10,795 classes; 31,677 mutants generated, 9,095 that build and pass; 4,660 judged not equivalent; 571 tests | Source 1 Table 2 |
| Acceptance | engineers accepted 73% of the tests | Source 1 §4.2 |
| Equivalence judge | precision 0.95 and recall 0.96 with simple rule-based pre-processing; 0.79 and 0.47 for the model alone | Source 1 §5.3 |
| Mutation versus coverage | 49% of tests that uniquely kill a mutant add no line coverage | Source 1 §6 |

## Limits the authors state

The current code is the regression oracle (the reference for correct behaviour), so [ACH](https://arxiv.org/abs/2501.12862) "cannot detect existing faults residing in the
code base". It protects against future regressions of the concern.

## What the course takes from it

- The second branch of Filter 3: Adds coverage or catches a mutant: a test that kills a mutant no existing test kills is kept even when it
  adds no coverage, because coverage alone would discard about half of such tests.
- Targeted mutants on risky lines, written by hand for the course rather than by a model, and
  validated so each one is killed by at least one existing test.
- Mutants split into a filter set and a referee set (mutants held back to judge the kept tests), so the tests are never judged with the
  mutants that selected them.

## Sources

- Source 1: Mutation-Guided LLM-based Test Generation at Meta (ACH),
  <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta), 2025-01-22
- Source 2: Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM),
  <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
