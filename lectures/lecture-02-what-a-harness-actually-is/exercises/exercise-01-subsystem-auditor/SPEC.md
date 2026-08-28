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

| Repo | Score | Missing | What it is |
| --- | --- | --- | --- |
| `repo-complete` | 5/5 | none | the full minimal harness |
| `repo-list-only` | 4/5 | state | a feature list with no progress log |
| `repo-no-state` | 4/5 | state | working but amnesiac |
| `repo-prompt-only` | 1/5 | all but instructions | a prompt file is not a harness |
| `repo-talks-tools` | 4/5 | tools | instructions describe verify.sh; the file does not exist |
| `repo-unpinned` | 3/5 | environment, state | a manifest with no runtime pin |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error or `<repos-dir>` is not a directory; stdout empty |

## Starter state (the intended failure)

The starter is a genuine partial implementation: all five audits run, and
two are naive first drafts, each with one realistic mistake the fixtures
expose:

| Naive audit | Its mistake | Trap repo that exposes it |
| --- | --- | --- |
| tools | trusts that the instructions *mention* `verify.sh` instead of checking the file exists | `repo-talks-tools` scores 5/5 instead of 4/5 |
| feedback | treats the `- Verification:` tag as the fact, without reading what follows it | `repo-empty-verification` scores 5/5 instead of 4/5 |

The feedback mistake is the malformed-line case: a line can carry the tag
and still name no command, and a subsystem whose command is the empty
string cannot tell anyone whether the work passed. The correct audit reads
what follows the colon, requires it to be non-empty, and reports the command
it found, so the evidence names something a reader can run.

Verification fails with a report mismatch first diverging at
`$.repos[0].subsystems.feedback.evidence: 'Verification line in AGENTS.md'
!= 'Verification line in AGENTS.md: ./verify.sh'`: on the very first repo,
the naive audit's evidence names the tag it matched instead of the command
it found. The starter must run cleanly and fail only by producing these
wrong values; a crash or an all-absent report is a bug in the starter, not
the intended state.

## Expected output

- `basic` case: `fixtures/repos` → `expected/audit-report.json` (kind json;
  the grading authority for both tracks).
