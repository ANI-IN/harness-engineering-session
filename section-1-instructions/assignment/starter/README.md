# Module 1: Harness Engineering for Coding Agents - Starter for Assignment 1: Instructions

Your work folder for [Assignment 1](../README.md). The steps are in the assignment README, and the
detailed requirements in [SPEC.md](../SPEC.md).

| Path | What it is | What you do |
|---|---|---|
| `original/AGENTS.md` | The 899-line instruction file, 70 tagged rules | Read it; never edit it |
| `instructions/AGENTS.md` | A stub with two gaps, marked `TODO(A1-1)` and `TODO(A1-2)` | Replace it with the map; add the docs and one skill |
| `checker/check_docs.py` | The checker's interface, with stubs marked `TODO(A1-3)` and `TODO(A1-4)` | Implement it |
| `checker/test_check_docs.py` | The visible tests; 12 of 15 fail on the stubs | Do not edit; add your own test file |
| `ab-report.md` | The A/B report template, with fields to fill | Fill it after the A/B run |
| `live/` | Not there yet: the evidence of your A/B run | Create it with `live_evidence.py` (step 6) |

Start with these two commands. Both run without keys or Docker:

```bash
make check-assignment-1
uv run python -m pytest -q -p no:cacheprovider section-1-instructions/assignment/starter/checker
```

The first prints one FAIL line per requirement still open. The second shows which parts of the
checker are missing.
