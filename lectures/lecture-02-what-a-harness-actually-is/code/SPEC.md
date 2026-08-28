# SPEC: minimal-harness-loop

One deterministic loop iteration through the five harness subsystems, with
single-subsystem ablation. The harness artifacts are ordinary language-neutral
files in the workspace directory; both tracks read the same bytes and must
emit the same report. `expected/` is the grading authority.

## CLI surface

```text
main <workspace-dir> [--disable=<subsystem> | --ablation-table]
```

`<workspace-dir>` contains the harness artifacts:

| File | Subsystem it feeds | Contents used |
| --- | --- | --- |
| `AGENTS.md` | instructions | the `- Convention: ...` line; the feature names |
| `feature_list.json` | state | statuses + dependencies (valid against `library/templates/feature_list.schema.json`) |
| `environment.json` | environment | `dependencies.formatter` must be `"installed"` |
| `tools.json` | tools | `allowed` must include `write_file` (and `run_check` for the check) |
| `clock.json` | (injected clock) | `today`, an ISO 8601 UTC timestamp; no wall clock is ever read |

## Loop semantics

Five steps in fixed order: instructions, state, environment, tools, feedback.
`--disable=<name>` removes exactly one subsystem for the run:

1. **instructions**: read the date convention from `AGENTS.md`. Disabled:
   guess `MM/DD/YYYY` (rendered from `today`'s date part).
2. **state**: choose the first `not-started` feature whose dependencies are
   all `passing` (here: `format-dates`). Disabled: start from the first
   feature named in the project summary (`stamp-header`), redoing done work.
3. **environment**: the formatter dependency must be installed to render the
   date. Disabled: rendering fails; nothing can be written.
4. **tools**: writing the artifact requires the `write_file` tool. Disabled:
   the work product cannot be produced.
5. **feedback**: run `run_check date-format` on the artifact (an ISO 8601
   UTC timestamp must be present, matched by
   `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z`). Disabled: completion is claimed
   with no check. A check that runs and FAILS is the feedback subsystem
   working (step `ok: true`), catching someone else's defect.

## The convention is read, not assumed

The date convention comes from the workspace's `AGENTS.md` and decides two
things: how the agent renders the date, and what the check accepts. Neither
is hardcoded. `fixtures/workspace` declares ISO 8601 and
`fixtures/workspace-us` declares `MM/DD/YYYY`; the same code produces
`date: 2026-08-27T00:00:00Z` for the first and `date: 08/27/2026` for the
second, and both pass their own check.

That is what makes the instructions ablation mean something. An
implementation that hardcodes ISO renders `2026-08-27T00:00:00Z` into the
`MM/DD/YYYY` workspace and its check, hardcoded the same way, passes it: the
subsystem the lecture ablates would be decorative, and removing it would
prove nothing. The checker reads the declared convention whether or not the
agent did, which is why disabling instructions still produces a caught
violation on `fixtures/workspace`.

## Outcomes (deterministic, one per configuration)

| Configuration | Outcome | The characteristic degradation |
| --- | --- | --- |
| all five enabled | `completed-verified` | none |
| `--disable=instructions` | `failed-verification` | wrong convention written; the check catches it |
| `--disable=state` | `completed-redundant` | correct work on the wrong (already passing) feature |
| `--disable=environment` | `error` | dependency missing; rendering fails |
| `--disable=tools` | `blocked` | no way to write the work product |
| `--disable=feedback` | `claimed-unverified` | done is declared, never demonstrated |

## Output

Default: a JSON report on stdout with exactly the fields `disabled`,
`feature`, `convention`, `steps` (five `{subsystem, ok, note}` entries in
step order), `artifact` (`{written, content}`), `outcome`, `issues`.
`expected/full.json` and the five `expected/disable-*.json` files pin every
configuration.

`--ablation-table`: a plain-text table, one line per configuration in the
order none, instructions, state, environment, tools, feedback, formatted
`<label> | <outcome> | <issue count>` with header `disabled | outcome |
issues` (pinned by `expected/ablation-table.txt`).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report or table emitted |
| 2 | usage error, missing workspace, or unknown subsystem name; stdout empty |

## Language-neutrality (the point of this unit)

Nothing in `fixtures/workspace/` is Python or TypeScript: markdown and JSON
only. The two implementations differ idiomatically but read identical bytes
and are held to identical output by the conformance runner. The repository's
own `feature_list.json` schema validates the workspace's feature list in
`make verify`, so the fixture is a real instance of the course's canonical
artifact, not a lookalike.
