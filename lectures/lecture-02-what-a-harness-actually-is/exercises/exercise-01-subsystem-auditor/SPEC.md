# SPEC: exercise-01 subsystem-auditor

Audits repository trees for the minimal artifact of each of the five harness
subsystems. Every audit signal is a language-neutral file; the criteria
below never mention an implementation language, which is the lecture's
point made executable.

## CLI surface

```text
main <repos-dir>
```

`<repos-dir>` contains one subdirectory per repository to audit. Repos are
audited in name order.

## Audit criteria (one per subsystem)

| Subsystem | Present when | Evidence string |
| --- | --- | --- |
| instructions | `AGENTS.md` or `CLAUDE.md` exists with non-whitespace content (checked in that order) | the filename found |
| tools | `verify.sh` exists | `verify.sh` |
| environment | a manifest AND a runtime pin exist: `pyproject.toml` + `.python-version` (checked first) or `package.json` + `.nvmrc` | `<manifest> + <pin>` |
| state | BOTH `feature_list.json` AND `claude-progress.md` exist | `feature_list.json + claude-progress.md` |
| feedback | the instructions file contains a line whose trimmed form starts with `- Verification:` | `Verification line in <filename>` |

`evidence` is `null` whenever `present` is false.

## Output

```json
{
  "repos": [
    {
      "name": "<dir name>",
      "subsystems": { "<subsystem>": { "present": true, "evidence": "..." } },
      "score": "<present>/5",
      "missing": ["<subsystem>", "..."]
    }
  ],
  "audited": 0
}
```

`missing` lists absent subsystems in the canonical order instructions,
tools, environment, state, feedback. For the committed fixtures:
`repo-complete` scores 5/5, `repo-no-state` 4/5 (missing state),
`repo-prompt-only` 1/5 (a prompt file alone is not a harness).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error or `<repos-dir>` is not a directory; stdout empty |

## Starter state (the intended failure)

The starter implements the instructions and feedback audits; tools,
environment, and state always report absent. Verification fails with a
report mismatch first diverging at `$.repos[0].missing: length 3 != 0`
(repo-complete appears to be missing three subsystems it actually has).
The starter must run cleanly and fail only by producing that wrong report.

## Expected output

- `basic` case: `fixtures/repos` → `expected/audit-report.json` (kind json;
  the grading authority for both tracks).
