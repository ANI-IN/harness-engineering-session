---
name: testgen-evidence
description: >
  Run filtered test generation (shipharness testgen) on one module of a Python repository with a
  pytest suite, run the duplicate-test filter over the kept tests, and write a one-page evidence
  report with the exact commands, a results table, every discard reason, and the limits. Use when
  someone asks for generated tests they can trust, or for proof that generated tests add something
  the existing suite does not already check.
license: MIT
metadata:
  course: shipharness
  assignment: "Assignment 4: Verification"
  sources: see the Sources list at the end
---

# Testgen evidence

Generated tests are worth keeping only if they survive filters, and a reader should be able to
check that claim. Meta's test generator applies "a series of progressively demanding semantic
filters" to candidate tests, and the survivors "are thus guaranteed to improve the existing test
class, and to provide reliable regression test signal"
([Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171)).
This skill runs those filters through `shipharness testgen`, adds a duplicate-test filter (the
same authors later added "an extra filter to remove previously seen test cases"), and writes the
result down.

## When to use

- "Generate tests for this module", "are these generated tests any good", "show me evidence".
- Before merging tests an agent wrote: keep only the ones that pass the filters, with reasons.
- Not for writing the code under test, and not for a repository without a passing pytest suite:
  Filter 3: Adds coverage or catches a mutant compares against the existing suite, so fix the suite
  first.

## Steps

1. Pick the target. For a course library target, fetch the pinned libraries once, from the
   shipharness repository root: `uv run python platform/scripts/fetch_testgen_libs.py`. For your own
   repository, note the module path and the existing test files for it.
2. Run testgen (one model-backed command; it prints its cost at exit):

   ```
   uv run shipharness testgen --target TG-boltons-listutils --max-tests 10 --out runs/evidence
   uv run shipharness testgen --repo <repo> --module <pkg/mod.py> --tests <tests/test_mod.py> \
       --max-tests 10 --out runs/evidence
   ```

   Without `--image`, generated tests run on this machine (the command prints an UNSANDBOXED
   warning). With a prepared container image, add `--sandbox docker --image <image>`.
3. Check the output before going on: the last lines list `+` kept tests, `-` discarded tests with
   `filter N: reason`, and the folder with `testgen-report.json`. If the status is not done, read
   the `x` line and fix that first; do not write a report on a failed run.
4. Run the duplicate filter over the kept tests (no model call; it only reads source):

   ```
   uv run python -m a4_verification.apply_filter --repo <repo> --kept runs/evidence \
       --existing <tests/test_mod.py>
   ```

5. Turn the report into the results table:
   `python scripts/summarize_report.py runs/evidence/testgen-report.json`.
6. Write the evidence report with these sections: Target, Commands (copied exactly), Results (the
   table from step 5), a section on Filter 6: No duplicate tests titled "Filter 6 on the kept
   tests" (the step 4 output), Limits. Quote numbers only
   from the run's own output.

## Checks before you finish

- [ ] Every command in the report was run as written; the report holds its real output.
- [ ] Each discarded test is listed with its filter number and reason.
- [ ] The Limits section says what the filters cannot prove: a kept test passed five runs and
      added line coverage (Source 1) or killed a mutant, a copy of the code with one planted
      fault, that no existing test kills
      ([Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)). That
      does not make it a good specification. Anthropic's compiler team warns that "it is easy to see
      tests pass and assume the job is done, when this is rarely the case"
      ([Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler)).

## Sources

- Source 1: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>,
  Alshahwan et al. (Meta), 2024-02-14
- Source 2: Mutation-Guided LLM-based Test Generation at Meta, <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta),
  2025-01-22
- Source 3: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
