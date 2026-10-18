# Security

<!-- Place this file at docs/SECURITY.md (the layout in [Harness engineering](https://openai.com/index/harness-engineering/), https://openai.com/index/harness-engineering/). That article names the file but does not describe its
contents; the structure below is the course's: every rule says why it exists, how it is checked, and
which code shows the correct pattern. Reviewers use these rules as grading criteria (the term in [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), https://www.anthropic.com/engineering/harness-design-long-running-apps), and
any violation fails the review. Replace every <placeholder>; delete rules that do not apply. -->

## How to read this file

Each rule has an ID. Tests, checks, and review comments cite the ID, so a failure message points
back here.

## Rules

### SEC-1 Every query is scoped to the caller

- Rule: <every read and write filters by the caller's organisation or owner>.
- Why: <one user must never see or change another tenant's data>.
- Checked by: `<test file or check command>`.
- Copy this: `<path::function>`.

### SEC-2 Writes check the caller's role

- Rule: <roles that may only read get 403 on every write endpoint>.
- Why: <least privilege>.
- Checked by: `<test file or check command>`.
- Copy this: `<path::function>`.

### SEC-3 Secrets stay out of code, logs, and commits

- Rule: keys and passwords come from the environment or a secret store. Never print, log, or
  commit them. `.env` files are not committed.
- Why: a leaked key gives anyone the same access you have.
- Checked by: `<secret scanner or test>`.

### SEC-4 Input is validated at the boundary

- Rule: <request bodies and parameters are parsed into typed models before any business logic>.
- Why: <invalid input is rejected with a clear error instead of reaching the database>.
- Checked by: `<test file or check command>`.

### SEC-<n> <Your rule>

- Rule:
- Why:
- Checked by:
- Copy this:

## When you find a problem outside your feature

Do not fix it in the same change. Add it under "Next" in `progress.md` with the rule ID and the
file, so it gets its own feature and its own review.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
