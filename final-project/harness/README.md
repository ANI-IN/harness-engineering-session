# Module 1: Harness Engineering for Coding Agents - Final project harness

This folder holds every file the harness arm of `make final FEATURES=bulk-close` gets from its four layers,
exactly as the agent gets them. Section by section you saw one layer at a time; here they are
together. Every file except this README was written from the layers' own code, so it is what the
layers produce. Do not edit the files here: change the layer code in `platform/src/shipharness/`,
and the next `make final` gives the agent the new files.

| Layer | Files here | How the agent gets them |
|---|---|---|
| Instructions | `AGENTS.md`, `ARCHITECTURE.md`, `docs/` (except `exec-plans/`), `.agents/skills/` | Placed in the workspace; the map is in every first message |
| State | `init.sh`, `progress.md`, `session-handoff.md`, `docs/exec-plans/active/F5.md` | Placed and committed before turn 1 |
| Scope | `feature_list.json`, `feature_list.schema.json`, `scope-rules.txt` | The two JSON files are placed; `scope-rules.txt` is the scope block of the first message |
| Verification | `context-prefix.txt`, `gate-items-build.txt`, `gate-items-test.txt` | The first-message block, and the gate's checks per phase |

The same files for one section at a time are in the section demo folders, for example
[section-1-instructions/demo/harness/](../../section-1-instructions/demo/harness/) and
[section-4-verification/demo/harness/](../../section-4-verification/demo/harness/). For Feature 6:
Watchers or Feature 7: Labels, the state and scope files name that feature instead; the other files
are the same.
