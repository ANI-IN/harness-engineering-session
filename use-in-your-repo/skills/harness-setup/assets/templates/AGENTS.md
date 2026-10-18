# AGENTS.md

<!-- A map for coding agents, not a manual. Keep it near 100 lines ([Harness engineering](https://openai.com/index/harness-engineering/): "A short AGENTS.md
(roughly 100 lines) is injected into context and serves primarily as a map"). Put each rule in the
document it belongs to and point to it from here. Replace every <placeholder>. -->

<Project name>: <one sentence on what this repository is and who uses it>.

## Getting up to speed (start of every session)

1. Run `pwd`. Work only inside this directory.
2. Read `progress.md` and the last commits (`git log --oneline -20`).
3. Read `session-handoff.md` if it exists: it is the previous session's structured handoff.
4. Read `feature_list.json` and pick the highest-priority feature whose `passes` is `false`.
   Work on one feature per session.
5. Run `./init.sh`. It starts the app and runs a smoke test. If it fails, fix that first.
6. Open the exec plan for your feature in `docs/exec-plans/active/`, or create one as
   `docs/PLANS.md` describes.

## Map

| Need | Read |
|---|---|
| Domains, layers, which package may import which | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Security rules: auth, roles, tenant data, secrets | [docs/SECURITY.md](docs/SECURITY.md) |
| Reliability rules: errors, retries, migrations | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Quality grade per domain and layer, known gaps | [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md) |
| How to write and keep an exec plan | [docs/PLANS.md](docs/PLANS.md) |
| Active and finished plans | `docs/exec-plans/active/`, `docs/exec-plans/completed/` |
| Design decisions and core beliefs | [docs/design-docs/index.md](docs/design-docs/index.md) |
| What the product does | [docs/product-specs/index.md](docs/product-specs/index.md) |
| Notes on libraries we use | `docs/references/` |
| What "clean state" means here | [docs/clean-state-checklist.md](docs/clean-state-checklist.md) |
| Skills for repeated tasks | `.agents/skills/` |

## Rules that always apply

- `feature_list.json` is the list of work. Never remove or rewrite an entry. The only change
  allowed is setting `passes` to `true`, and only after the clean-state checklist passes.
- Copy patterns from the code that ARCHITECTURE.md names as the example. Never copy code it
  lists as legacy.
- Change only files your feature needs. Note anything else you find under "Next" in
  `progress.md` instead of fixing it now.
- A failing check prints how to fix it. Read the message before changing the check.

## Commands

| Task | Command |
|---|---|
| Start the app and run the smoke test | `./init.sh` |
| Run the tests | `<test command>` |
| Lint and format | `<lint command>` |
| Database migrations | `<migration command>` |

## End of session

1. Go through `docs/clean-state-checklist.md`.
2. Update `progress.md`: Done, In progress, Next, and one line in the Session log.
3. Update the exec plan: Progress, Surprises & Discoveries, Decision Log.
4. Write your notes in `session-handoff.md` for the next session.
5. Commit with a message that says what changed and why.
