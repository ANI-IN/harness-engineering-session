# Module 1: Harness Engineering for Coding Agents - Starter for Assignment 2: State and sessions

Your starting point for [Assignment 2](../README.md). The requirements are in [SPEC.md](../SPEC.md).

> **Terms on this page**
>
> - **Initializer step**: The harness code that writes `init.sh`, `progress.md`, `session-handoff.md`, and the exec plan before session 1.
> - **Getting up to speed**: The routine every session starts with: read the git log and the state files, then run `init.sh`.

`a2_state/` is a state layer that runs without errors. The initializer step writes `init.sh`,
`progress.md`, `session-handoff.md`, and the exec plan, and every session gets the Getting up to
speed routine. Nothing is written at a session stop, so the self-check fails until you fill in the
TODOs.

| File | What to edit |
|---|---|
| `a2_state/ledger.py` | TODO 1a `parse_steps`, 1b `derive_ledger`, 1c `render_ledger` |
| `a2_state/layer.py` | TODO 1-5 `on_session_end`, 6 `on_session_start`, 7 `on_phase_end` |
| `a2_state/progress_log.py` | TODO 4 `normalise_progress` |

Work here, or copy the folder and pass the copy with `A2_IMPL=<folder>`:

```bash
make check-assignment-2
```

When your layer is final, run the live step once. It writes `live/` next to `a2_state/`. Submit the
folder with both.
