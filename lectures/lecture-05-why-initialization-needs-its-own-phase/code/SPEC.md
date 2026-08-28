# SPEC: init-check

Two surfaces over the same four readiness checks: `replay`, the
behavioral demo, and `doctor`, the gate that predicts it.

## The replay (the demo, pinned)

`main replay <repo-dir>` runs a scripted session with a step budget of
12 after a fixed feature task (five feature steps plus one verification
step). Costs derive from the doctor's checks and nothing else:

| Failing check | When it bites | Cost |
| --- | --- | --- |
| `progress-artifact` | session start | 2 extra steps of re-derivation |
| `dependencies-pinned` | dependency install | 1 extra step (mid-install failure, pin by hand) |
| `init-script` | after feature step 2 | 2 extra steps (mysterious failure traced to the half-built environment) |
| `verification-command` | at completion | the finished feature is claimed unverified |

Output: `{"repo", "budget", "events": [{"step", "action", "outcome"}],
"steps_spent", "setup_overhead", "feature_completed", "verified"}`. Exit
0 when the feature completed AND was verified; 1 otherwise. On the
committed fixtures the broken repository exhausts its budget at feature
step four (exit 1) and the ready repository finishes verified in nine
steps (exit 0); the pinned transcripts are the lecture's argument.

The startup-readiness doctor: four file-based checks that decide whether a
fresh session can start from a known-good state. Both tracks read the same
repositories and must emit the same report; `expected/` is the grading
authority.

## CLI surface

```text
main <repo-dir>            # the doctor
main replay <repo-dir>     # the session replay
```

## The four checks (fixed order)

| id | Passes when | Failure detail names |
| --- | --- | --- |
| `dependencies-pinned` | every dependency manifest present has its runtime pin (`pyproject.toml` + `.python-version`, `package.json` + `.nvmrc`); at least one pair exists | the manifest whose pin is missing, or the absence of any manifest |
| `init-script` | `init.sh` exists, is executable, and enables strict mode (contains `set -euo pipefail`) | which of the three properties is missing |
| `verification-command` | the instructions file (`AGENTS.md`, then `CLAUDE.md`) carries a `- Verification: <command>` line | the absent line |
| `progress-artifact` | `claude-progress.md` exists and carries a `- Next best step: <text>` line | the missing file or the missing line |

## Output

```json
{ "checks": [ { "id": "...", "passed": true, "detail": "..." } ], "ready": true }
```

Pass details are affirmative evidence (which pair, which command); failure
details name the exact missing piece.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ready: every check passed |
| 1 | not ready; the report on stdout names what initialization still owes |
| 2 | usage error or `<repo-dir>` is not a directory; stdout empty |

## Fixtures and seeded symptoms

`repos/repo-ready` passes all four; its `init.sh` is the module's
**declared single-file exception**: one language-neutral script showing
both ecosystems' install paths side by side (see docs/conventions.md,
command-block exceptions), which is also why the fixture pins both
ecosystems (`pyproject.toml` + `.python-version` AND `package.json` +
`.nvmrc`).

`repos/repo-broken` seeds three failures, each caught by its named check
with the exact detail string:

| Seeded defect | Caught by | Detail |
| --- | --- | --- |
| `package.json` with no `.nvmrc` | `dependencies-pinned` | `package.json present but .nvmrc missing` |
| `init.sh` without strict mode | `init-script` | `init.sh does not enable strict mode (set -euo pipefail)` |
| no progress log | `progress-artifact` | `claude-progress.md missing` |

`verification-command` passes in both fixtures: a broken repo is rarely
broken everywhere, and the doctor must report per-check, not overall
impressions.
