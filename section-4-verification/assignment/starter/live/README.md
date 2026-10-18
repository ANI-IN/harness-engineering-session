# Module 1: Harness Engineering for Coding Agents - Live evidence for Assignment 4: Verification

The files of your two live runs go here (instructions: steps 6 to 8 of the
[assignment](../../README.md), and [SPEC.md](../../SPEC.md#evidence-to-hand-in)). The self-check and the grader validate them; nothing is re-run.

| File | What goes in it |
|---|---|
| `testgen.txt` | First line `$ <the exact testgen command>`, then everything it printed |
| `testgen-report.json` | `testgen-report.json` from the `--out` folder, after `apply_filter ... --update-report` |
| `ab.txt` | First line `$ uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview`, then everything it printed |
| `scores/<run_id>.json` | The two score records of that A/B, copied from `exports/scores/` |

`F4` in the A/B command is Feature 4: Version checks on issue edits.
