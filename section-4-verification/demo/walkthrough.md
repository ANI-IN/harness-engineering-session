# Demo 4 walkthrough: the verify gate

> **Terms on this page**
>
> - **Verify gate**: The checks that run in the agent's container when it claims done; a failure sends the claim back.
> - **Done claim**: The agent's call `finish(claim="done")`, which says the phase's work is complete.
> - **Gate item**: One check of the gate, shown as one pill on console screen 1.
> - **Clean state**: All work committed, ruff clean on changed files, one migration head (a single latest migration), no debug output.
> - **Referee**: The program that scores each run after the agent stops.
> - **Hidden tests**: Held-out tests: the agent never sees them; the referee runs them after the agent stops.
> - **Referee mutants**: Planted faults the agent never sees; the referee counts how many the shipped tests catch.
> - **Workspace**: The harness arm's copy of TeamTrack, inside its container.

## What this code does

When the agent calls `finish(claim="done")`, the verify layer runs the gate before the phase may end.
The gate copies the workspace, runs each item inside the arm's own container, and returns a verdict.
If any item fails, the agent gets the failures and keeps working. If all pass, the claim stands and
the scope layer sets `passes` to true. Four short excerpts from
`platform/src/shipharness/harness/verify/gate.py`, 38 lines in all, show it in the order it runs.

```mermaid
sequenceDiagram
  participant A as Agent
  participant R as Runner
  participant G as Gate
  participant C as Arm container
  A->>R: finish(claim="done")
  R->>G: run_gate (build or test phase)
  G-->>R: items pending (console pills)
  G->>C: visible tests, house rules and more, clean state
  C-->>G: pass or fail per item
  alt an item failed
    G-->>R: feedback: summary and first three failures
    R-->>A: "Not accepted." plus the feedback
  else all passed
    G-->>R: gate passed; the phase ends
  end
```

## The code, explained

### gate.py, lines 34-44

This tuple is what the gate's check runner may run.

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

- Seven house rules, the existing tests (`regression`), and a board smoke check.
- What is missing matters most: no hidden tests and no referee mutants. Those stay with the referee,
  so they are still held out when it scores the run.
- The referee runs the same seven house rule checks. That overlap is disclosed: a harness arm is
  expected to do better on those rules by construction, so Section 4: Verification scores hidden tests and mutants
  instead.

### gate.py, lines 156-163

The start of `run_gate`. It announces the items, then copies the work.

```python
# platform/src/shipharness/harness/verify/gate.py (lines 156-163)
    root = f"/tmp/shipharness-gate-{_SAFE.sub('_', gate_id)}"
    names = ["visible tests", *(_ITEM_ORDER if phase == "build" else []), "clean state"]
    if on_update:  # pending pills first, so the console shows the gate running
        pending = [GateItem(name=n, status="pending") for n in names]
        on_update(GateResult(gate_id=gate_id, items=pending, passed=False, feedback=""))
    sandbox.exec(
        f"rm -rf {root} && mkdir -p {root}/build && cp -a ./. {root}/build/", cfg.limit(300)
    )
```

- A build-phase gate has 11 items; a test-phase gate has only the visible tests and clean state.
  The exact lists, the five test filters, and the house rules are in [harness/](harness/README.md).
- The pending pills go out before any command runs. That is the row of waiting pills at minute 3 of
  the demo.
- The checks run on a copy in `/tmp`, so they cannot change the agent's files.
- `cfg.limit` caps each command by the harness time left, so a slow gate cannot run past the run's
  limits.

### gate.py, lines 164-176

Each item runs inside the arm's container.

```python
# platform/src/shipharness/harness/verify/gate.py (lines 164-176)
    visible, lines = _visible_tests(sandbox, f"{root}/build", cfg)
    items = [visible]
    if phase == "build":
        check_items, check_lines = _check_items(sandbox, cfg, root, on_progress)
        items += sorted(check_items, key=_order)
        lines += check_lines
    clean = clean_state_check(
        sandbox, base_sha, cfg.limit(120), migrations=cfg.migrations, ruff_select=cfg.ruff_select
    )
    items.append(clean)
    if clean.status == "fail":
        lines.append(f"FAIL clean state: {clean.detail}")
    sandbox.exec(f"rm -rf {root}", cfg.limit(60))
```

- `_check_items` runs the house rules, the existing tests, and the board check, and counts only new
  violations against the checkpoint's own baseline.
- The clean-state item runs on the workspace itself, against `base_sha`, the commit before the
  agent's first change. It follows Anthropic's definition: code "that would be appropriate for
  merging to a main branch"
  ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)).
- `lines` collects one failure line per problem, each with its reason on the same line.

### gate.py, lines 177-182

The verdict.

```python
# platform/src/shipharness/harness/verify/gate.py (lines 177-182)
    passed = not any(i.status == "fail" for i in items)
    feedback = "" if passed else _feedback(gate_id, items, lines)
    result = GateResult(gate_id=gate_id, items=items, passed=passed, feedback=feedback)
    if on_update:
        on_update(result)
    return result
```

- One failed item fails the gate. Anthropic's compiler team says why the bar is that high: "it’s
  important that the task verifier is nearly perfect, otherwise Claude will solve the wrong
  problem." ([Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler))
- `_feedback` (lines 192-202) writes `Gate <id>: <n> of <m> items failed (<names>).`, the first three
  failure lines, and "Fix these, commit your work, and call finish again." The same team asks for a
  few lines of output, with the reason "on the same line" as the error.
- The runner turns a failed gate into the `finish` result "Not accepted." plus that text, and the
  phase goes on (`platform/src/shipharness/runner/loop.py`, lines 291-300).
- A passed gate is stored in the run's state. The scope layer reads it and only then sets `passes`
  (`platform/src/shipharness/harness/scope/status.py`).

In the captured demo run, all 11 items passed on the first claim, with 190 visible tests. The
referee then failed the run on one hidden test and 0 of 4 mutants. The gate did its job; its job
does not include the held-out checks.

## If you copy this into your repo

- Run your checks when the agent says done, not only in CI after a pull request. Return the
  failures as the answer to "done", so the agent fixes them while it still has the context.
- Run the checks somewhere the agent cannot edit: a copy, a container, or a CI job.
- Keep a few checks the agent never sees, and score with them. A gate the agent can see becomes a
  target; the held-out checks tell you whether the work is right.
- Cap the feedback: a summary, the first few failures, and what to do next. Anthropic's compiler team
  warns against printing "thousands of useless bytes" into the agent's context.

## Sources

- Source 1: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 2: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
