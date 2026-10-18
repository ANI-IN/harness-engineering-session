# Module 1: Harness Engineering for Coding Agents - Starter for Assignment 3: Scope and sandbox

Your work folder for [Assignment 3](../README.md). Edit the files marked "yours" below; the
requirements are in [SPEC.md](../SPEC.md).

| File | What to do |
|---|---|
| `a3scope/diffparse.py` | Yours, Part A1: write `parse_diff` and `changed_paths` |
| `a3scope/scope.py` | Yours, Part A2: write `glob_matches` and `check_diff` |
| `a3scope/status.py` | Yours, Part B: write `update_status` |
| `a3scope/policy.py` | Yours, Part C: write `HISTORY_MESSAGE` and `HISTORY_RULES` |
| `tests/test_a3_sandbox_rule.py` | Yours, task 6: write the denial test |
| `a3scope/sandbox.py` | Given: `PolicySandbox`, which refuses a command before it runs |
| `tests/test_a3_docker_rule.py` | Given: an optional check in a real container (`pytest -m docker`) |
| `live/` | Written later by `live.py collect`, after your live A/B; commit it |

Each place to fill is marked `TODO(A3 ...)` (`A3` is Assignment 3), and `make check-assignment-3` lists the ones left. The
package imports and the self-check runs on these files as they are; it fails until the parts are done.
