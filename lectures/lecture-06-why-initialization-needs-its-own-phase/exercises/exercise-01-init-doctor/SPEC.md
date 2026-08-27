# SPEC: exercise-01 init-doctor

Same contract as the lecture demo
([../../code/SPEC.md](../../code/SPEC.md)): the four startup-readiness
checks, in order, with a per-check report and the ready/not-ready exit
verdict. This exercise applies it to fresh fixture repositories, and the
starter ships three naive checks that stop at file existence.

## CLI surface

```text
main <repo-dir>
```

Check ids, rules, detail strings, report shape, and exit codes are
identical to the demo SPEC.

## Fixtures

- `repos/repo-solid`: passes all four (Python pair pinned, strict
  executable `init.sh`, Verification line, progress with a Next best step
  line); exit 0.
- `repos/repo-hollow`: looks initialized and is not, one trap per naive
  check: `pyproject.toml` with no `.python-version`, an executable
  `init.sh` without strict mode, and a progress file with no
  `- Next best step:` line. `verification-command` passes. Exit 1.

## Starter state (the intended failure)

The starter's three naive checks accept existence where the rule demands
substance:

| Naive check | Its mistake | What repo-hollow shows |
| --- | --- | --- |
| `dependencies-pinned` | accepts a manifest without its runtime pin | passes on an unpinned interpreter |
| `init-script` | accepts any file named `init.sh` | passes a script with no strict mode |
| `progress-artifact` | accepts any progress file | passes a file that names no next step |

Verification fails first on `repo-solid` at
`$.checks[0].detail: 'pyproject.toml' != 'pyproject.toml + .python-version'`
(the naive evidence names half the criterion), and on `repo-hollow` the
starter exits 0 where the expected verdict is exit 1: the hollow repo is
declared ready. The starter must run cleanly and fail only by producing
these wrong values and that wrong verdict.

## Expected output

- `solid` case: `fixtures/repos/repo-solid` → `expected/solid.json`,
  exit 0.
- `hollow` case: `fixtures/repos/repo-hollow` → `expected/hollow.json`,
  exit 1.
