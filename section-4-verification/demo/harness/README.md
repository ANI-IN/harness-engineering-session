# Module 1: Harness Engineering for Coding Agents - Demo 4 harness files

This folder holds what the verify layer uses in the Section 4: Verification demo. The verify layer places no files
in the agent's workspace. It gives the agent text: one block in the first message of every session,
and the result of the gate when the agent claims done. The files here hold that text, and the two
lists the layer checks against: the test filters and the house rules. They are taken from the code
in `platform/src/shipharness/`.

> **Terms on this page**
>
> - **Harness layer**: One part of the harness: instructions, state, scope, or verification.
> - **Verify gate**: The checks that run in the agent's container when it claims done; a failure sends the claim back.
> - **Done claim**: The agent's call `finish(claim="done")`, which says the phase's work is complete.
> - **Clean state**: All work committed, ruff clean on changed files, one migration head, no debug output.
> - **Test filters**: Five checks a test from the test phase must pass to be kept.
> - **House rules**: TeamTrack's seven rules for every endpoint, House rule 1: Tenant isolation to House rule 7:
>   Migrations.

Do not edit the files here. They were written from the code, so they hold exactly what the layer
gives the agent. To change the text, change the code in `platform/src/shipharness/`; the next
`make show-4` gives the agent the new text.

## What is here

| File | What it holds | How the agent gets it |
|---|---|---|
| `context-prefix.txt` | The verify block: what the gate checks, and that test-phase tests must pass the filters | In the first message of every session |
| `gate-items-build.txt` | The gate's 11 items in a build phase, in order | Named in a refusal, such as a house rule and clean state |
| `gate-items-test.txt` | The gate's 2 items in a test phase | Named in a refusal |
| `test-filters.txt` | The five filters, in the order they run on each test-phase test | Not shown; only "the test filters" |
| `house-rules.txt` | House rules 1 to 7, the lines of `AGENTS.md` that state them | In `AGENTS.md` (Section 1: Instructions layer) |

The same item names are the gate pills on console screen 1. The filters come from `DEFAULT_FILTERS`
in `platform/src/shipharness/filters/filters.py`. They run after the test phase ends, and their
results go to the console, not to the agent. The gate checks the house rules with the checks in
`platform/src/shipharness/checks/`.

When the gate refuses a claim, `finish` returns "Not accepted.", then one line with how many items
failed and their names, then up to three failure lines, then "Fix these, commit your work, and call
finish again." The [walkthrough](../walkthrough.md) shows the code that builds it.

## What is not here

- The hidden tests and the referee mutants. They live outside the agent's workspace and are never
  named in anything the agent receives.
- The prompts both arms get (the core prompt and the phase prompts). They are not part of this
  layer.
- The other three layers. All four run in this demo; their files are in the demo folders of
  Sections 1 to 3.
