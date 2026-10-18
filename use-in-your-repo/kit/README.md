# Module 1: Harness Engineering for Coding Agents - Harness starter kit

## The problem

**Illustrative scenario.** You want your repository to have what TeamTrack had in class: a short
map for the agent, session files, a feature list, house-rule checks, and a CI job. You start writing
them from memory. Each file comes out a little different from the one that worked, nobody can say
which values matter, and the first agent session trips over a command that was never run.

The cost: a harness that looks right but was never tested, and hours spent rebuilding files that
already exist.

> **Terms on this page**
>
> - **Kit**: TeamTrack's harness as templates, copied into your repository by `shipharness init`.
> - **Map**: a short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **REPLACE marker**: a line in a kit template that says what to write in place of the example value.
> - **House rule**: a team convention written as one checkable sentence, with a check that finds violations.
> - **House rules 1 to 7**: TeamTrack's rules, from House rule 1: Tenant isolation to
>   House rule 7: Migrations. The kit files name them by code, `R1` to `R7`.
> - **Exec plan**: a living plan for one feature, kept in the repository and updated as the work goes.
> - **Adapter**: the one file that tells `shipharness check` the facts it needs about your app.

## Why it happens

A harness is many small files that point at each other. The map points to the docs, the docs name
the checks, and the checks need facts about your app. Written from scratch, one wrong path or one
untested command breaks the chain, and the agent only finds out mid-session. The source behind the
map puts it plainly: "From the agent’s point of view, anything it can’t access in-context while
running effectively doesn’t exist."
([Harness engineering](https://openai.com/index/harness-engineering/))

## What the kit does

The kit is TeamTrack's harness, packaged as templates for your own repository: the map, the docs it
points to, the state files a session reads and writes, the feature list with its schema, house-rule
checks, a sandbox policy, a CI workflow, and the four course skills. Every template holds
TeamTrack's real, working values as the example. A REPLACE marker next to each value says what it
means and what to write instead. A test keeps each template equal to the TeamTrack file it came
from, so the example values are the ones the course really ran.

`shipharness init` copies the kit into a repository, and `shipharness init --check` lists the
markers you have not filled yet. Both make no model calls and use no network. The step-by-step
guide, with a worked example on a real repository, is [apply-to-your-repo.md](../apply-to-your-repo.md).

## Use it

Run these from your shipharness checkout. Replace `~/my-repo` with your repository's path:

```bash
uv run shipharness init --target ~/my-repo
uv run shipharness init --target ~/my-repo --skills claude
uv run shipharness init --check ~/my-repo
```

The first command copies the kit; files that already exist are skipped. The second installs the
skills only in `.claude/skills/`. The third lists the REPLACE markers still unfilled.

`--target` refuses to overwrite a file that exists with other content. It prints
`! skipped <file>: exists with other content (--force overwrites)` and leaves the file alone. A
second run on the same repository writes nothing. `--check` exits 1 while markers remain and 0 when
none are left. A kit file you deleted on purpose is listed as not present and does not count.

## What gets copied, and where each file comes from

| In your repository | What it is | Taken from (shipharness repository) |
|---|---|---|
| `AGENTS.md` | The map: where each rule lives, house rules, commands, session steps | `platform/teamtrack/harness/instructions/AGENTS.md`; session steps from `platform/src/shipharness/harness/state/lifecycle.py` |
| `ARCHITECTURE.md` | Domains, layers, what each layer may import | `platform/teamtrack/harness/instructions/ARCHITECTURE.md` |
| `docs/SECURITY.md`, `docs/RELIABILITY.md`, `docs/QUALITY_SCORE.md`, `docs/PLANS.md` | The house rules (`R1` to `R7`), quality grades, plans and known debt | `platform/teamtrack/harness/instructions/docs/` |
| `docs/design-docs/`, `docs/product-specs/`, `docs/references/` | Design decisions, product specs, tool notes | `platform/teamtrack/harness/instructions/docs/` |
| `docs/clean-state-checklist.md` | What "ready to merge" means, as commands | `use-in-your-repo/skills/harness-setup/assets/templates/clean-state-checklist.md` and `platform/src/shipharness/harness/verify/clean_state.py` |
| `docs/house-rules.md` | How to adapt the seven house rules, and the adapter methods each one needs | `platform/src/shipharness/checks/` |
| `docs/exec-plans/active/F1.md` | An exec plan the harness wrote for Feature 1: Org-wide issue search (`F1`) | `platform/src/shipharness/harness/state/assets/exec-plan.md` |
| `feature_list.json`, `feature_list.schema.json` | The list of work (`passes`, `evidence`, `testedAt`) and its schema | `platform/src/shipharness/harness/scope/features.py` and `scope/assets/feature_list.schema.json` |
| `progress.md`, `session-handoff.md`, `init.sh` | The session log, the structured handoff, the start script | `platform/src/shipharness/harness/state/assets/` |
| `harness/shipharness_adapter.py`, `harness/check-params.json` | What `shipharness check` needs to know about your app | `TeamTrackAdapter` in `platform/src/shipharness/checks/adapter.py`; `platform/src/shipharness/checks/params.py` |
| `harness/sandbox-policy.toml` | Container limits for a coding agent | `SandboxPolicy` in `platform/src/shipharness/sandbox/policy.py` |
| `.github/workflows/shipharness.yml` | `shipharness check` on every push; `shipharness testgen` on demand | `.github/workflows/ci.yml` and the `check` and `testgen` commands |
| `.claude/skills/<name>/`, `.agents/skills/<name>/` | harness-setup, assured-tests, house-rules, skill-template | `use-in-your-repo/skills/` |

Files the harness renders at run time (progress.md, session-handoff.md, init.sh, the exec plan,
feature_list.json) were rendered with the harness's own functions for TeamTrack's Feature 1
(`F1`). One value is the kit's own: the six `steps` of that feature, shortened from
the API section of `platform/teamtrack/docs/features/f1.md`. In the course's A/B runs (the same
ticket run with and without the harness) the dataset line has no `steps`, so the
state and scope layers take them from the ticket's bullet lines or, failing that, its title
(`platform/src/shipharness/harness/scope/features.py`); the kit writes them out so you see the shape a good
step list has.

## The REPLACE markers

One form per file type, each on its own line, so `grep` finds all of them:

| File type | Marker |
|---|---|
| Markdown | `<!-- REPLACE: what the field means; the TeamTrack value is shown below it -->` |
| Shell, YAML, TOML, Python, text | `# REPLACE: ...` |
| JSON | a `"_replace": "..."` key |

`grep -rn "REPLACE:" .` and `grep -rn '"_replace"' .` find the same lines as
`shipharness init --check`. The feature list schema rejects the `_replace` key, so a feature list
that still has its note fails validation. Delete each marker line when you have replaced the value
below it, or delete the whole section or file when it does not apply to your repository.

## How the kit stays true to its sources

`platform/tests/unit/kit/test_templates.py` compares every template with the source it was taken from: a
copied document must equal its TeamTrack source once the marker lines are removed; a rendered file
must equal a fresh rendering; the feature list and schema must match the scope layer's; the sandbox
policy must equal `SandboxPolicy()`; the adapter template must answer like `TeamTrackAdapter` and
pass the checks for House rules 2, 5, and 6 (`R2`, `R5`, `R6`) on TeamTrack (`platform/tests/unit/checks/test_kit_adapter.py`). When a source
changes, the test names the template to recopy. Print a fresh rendering with
`uv run python -m shipharness.kit.sources progress.md` (or `init.sh`, `session-handoff.md`,
`docs/exec-plans/active/F1.md`, `feature_list.json`, `feature_list.schema.json`).

## When it fails

| Output | Fix |
|---|---|
| `x target directory not found: <dir>` | Create the repository folder first, or fix the path |
| `! skipped <file>: exists with other content (--force overwrites)` | Merge the template into your file by hand, or pass `--force` |
| `x no kit files in <dir>: run shipharness init --target <dir> first` | `--check` was pointed at a folder without the kit |
| `x <n> REPLACE markers left in <m> files` (exit 1) | Fill or delete each listed line, then run `--check` again |

More, with captured output: the "When something goes wrong" table in the
[guide](../apply-to-your-repo.md#when-something-goes-wrong).

## What the kit does not do

- It writes rules down; only the checks, tests, and CI enforce them. `docs/house-rules.md` and the
  adapter template are where enforcement starts.
- It does not run sessions for you. In TeamTrack the harness sends the session start and end
  steps, writes the machine summary in the handoff, and sets `passes`; in your repository, the
  AGENTS.md map tells the agent to do those steps itself.
- It does not call a model. The first step that does is `shipharness testgen`, which costs money
  (see the guide).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
