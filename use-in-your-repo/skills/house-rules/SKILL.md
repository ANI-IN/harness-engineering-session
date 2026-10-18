---
name: house-rules
description: >
  Turn a team convention into a house rule: a one-page rule document plus a mechanical check whose
  error message tells the agent how to fix the problem, and a test with a seeded violation the
  check must catch. Includes a rule template and a scaffolding script. Use when the same review
  comment keeps coming back, when agents copy a pattern that should not be copied, or when a rule
  written in the docs is still broken and needs to become code.
license: MIT
metadata:
  course: shipharness
  sources: the numbered Sources list at the end of this file
---

# House rules

"House rules" is the course's label for what [Harness engineering](https://openai.com/index/harness-engineering/) calls "golden principles" encoded in the repository
and "taste invariants" enforced "with custom lints" (Source 1). The idea in one line,
also from Source 1: "When documentation falls short, we promote the rule into code".

A house rule has three parts, and it is not done until all three exist:

1. A rule document that says the rule in one checkable sentence, why it exists, and what correct
   and incorrect code look like.
2. A check that finds violations and prints, on one line, what is wrong and how to fix it (Source 1:
   "we write the error messages to inject remediation instructions into agent context").
3. A test with a seeded violation the check must catch, and a clean case it must pass.

## When to use

- The same review comment appears on several changes.
- An agent copied a legacy pattern (Source 1: agents replicate "patterns that already exist in the
  repository—even uneven or suboptimal ones").
- A rule is in the docs, and agents still break it.

Do not use it for preferences a formatter already handles, or for one-off decisions. Source 1 enforces
invariants and leaves the rest to the agent: "By enforcing invariants, not micromanaging
implementations, we let agents ship fast without undermining the foundation".

## Steps

1. Pick an id and a short title. Run:

   ```
   python scripts/new_rule.py --id Example --title "Soft-deleted rows never appear" --root <repo>
   ```

   It writes `docs/rules/<id>-<slug>.md` from `assets/rule-template.md`, a check stub in `checks/`,
   and a test stub in `platform/tests/`. Use `--docs-dir`, `--checks-dir`, `--tests-dir`, or `--slug` to
   change where files go, `--dry-run` to see the plan, `--force` to overwrite.
2. Fill in the rule document. The Rule section is one sentence a reviewer can answer yes or no.
   Correct and Incorrect show the smallest examples, or point to the file to copy.
3. Write the seeded-violation test first. The stub fails on purpose; replace the `pytest.fail` line
   with a file that breaks the rule and an assertion that `check()` reports it. Run it and see it
   fail because the check finds nothing yet.
4. Write `check()` until the test passes. Pick the simplest check that is exact enough:
   a text search for a banned call, an `ast` walk for imports or calls, an import-linter contract
   for layering (Source 1 enforces layers "via custom linters ... and structural tests"), or a
   probe against the running app for behaviour such as tenant isolation.
5. Write the error message in `REMEDIATION`: what to do instead and which document to read. Keep the
   format `ERROR <id> <path>:<line>: <what is wrong>. Fix: <what to do>`, one line per violation,
   so grep finds it ([Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler): "write ERROR and put the reason on the same line so grep will find it").
6. Run the check on the whole repository. List existing violations in `BASELINE` so the rule
   applies to new code from today, and open a feature to remove each one.
7. Wire it in: add the check to CI and to the gate an agent must pass before "done", and add one
   line for the rule to the map an agent reads (AGENTS.md or the docs index it points to). Source 1
   checks its knowledge base with "linters and CI jobs".

## Writing the rule

- One rule per file, one sentence per rule. If it needs "and", it is two rules.
- Say why, with the failure it prevents. A rule without a reason gets deleted the first time it
  is inconvenient.
- Name the files the rule covers and what it deliberately does not cover.
- Give every exemption an owner and a reason, in the rule document and in the check.

## Checks before you finish

- [ ] The seeded-violation test failed before `check()` was written, and passes now.
- [ ] The clean-code test passes.
- [ ] Running the check on the repository prints only baseline violations, or none.
- [ ] Each ERROR line says how to fix the problem.
- [ ] The rule is linked from the map the agent reads, and the check runs in CI.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Building a C compiler with a team of parallel Claudes,
  <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic),
  2026-02-05
- Source 3: Agent Skills Specification, <https://agentskills.io/specification>,
  Agent Skills project, n.d.
