# Automated unit test improvement at Meta, in short

Alshahwan, Chheda, Finegenova, Gokkaya, Harman, Harper, Marginean, Sengupta, Wang (Meta).
[Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171).
FSE '24. arXiv 2402.09171, 2024-02-14.

Summary in our own words; quotes are marked. Sources are listed at the end of this page.

## What it does

[TestGen-LLM](https://arxiv.org/abs/2402.09171) takes an existing Kotlin test class at Meta, asks a language model for extra test
cases, and keeps only the candidates that survive a series of filters. The surviving tests are
added to the class; existing tests are never changed, so there can be no regression "by
construction".

## The filters

1. Builds: the candidate compiles in the app's existing build.
2. Passes: it passes on first execution, and on "every one of five executions"; otherwise it is
   discarded as failing or flaky.
3. Improves coverage: it adds line coverage to the class; tests that do not are discarded.

Later versions added a filter that removes test cases seen before. The guarantees were
first per test class and were extended to each test case after engineers asked for them.

## Results reported

| Measure | Value | Where |
|---|---|---|
| Evaluation on 86 test classes (Instagram Reels and Stories) | 75% of classes had a new test that builds, 57% one that also passes reliably, 25% one that also adds line coverage | Source 1 §3.3 |
| Deployment | about 10% of the test classes it was applied to were improved (the abstract says 11.5%); 73% of improvements were accepted by engineers | Source 1 §4 |
| Success rate per trial | about 4-5%; a trial succeeds only if the test builds, passes, and adds coverage | Source 1 §4, Table 3 |

The 75/57/25% figures are per test class, not per generated test (Source 1 §3.3).

## What the course takes from it

- The filter pipeline: cheap checks first, and a test is kept only when it passes every filter.
- Five runs as the flakiness check.
- Line coverage as the measure of "adds something".
- The word "assured": survivors carry checked guarantees.
- The engineer stays in control; the tool recommends.

## Sources

- Source 1: Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM),
  <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
