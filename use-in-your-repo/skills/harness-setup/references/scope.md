# Scope checklist: what the agent may change and reach

Sources are listed at the end of this page.
Assessment checks C1-C5 test the items marked with a check id.

| Done | Item | Why | Source |
|---|---|---|---|
| [ ] | (C1) feature_list.json lists every feature, each starting with `"passes": false`. | The features in [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) "were all initially marked as “failing” so that later coding agents would have a clear outline of what full functionality looked like." [Autonomous Coding Agent Demo](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) labels the file "source of truth". | Source 1; Source 2 |
| [ ] | The list is JSON, not Markdown. | "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files." | Source 1 |
| [ ] | (C2) Each entry has `id`, `category`, `description`, `steps`, `passes`; shipharness adds `evidence` and `testedAt`. | The sample entry in Source 1 has category, description, steps, passes. The two extra fields are course design. | Source 1 |
| [ ] | Agents may change only `passes`, and AGENTS.md says so in strong words. | "We prompt coding agents to edit this file only by changing the status of a passes field"; "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality." | Source 1 |
| [ ] | Decide who sets `passes`. | In Source 1 the agent sets it after careful testing. shipharness moves the decision to the harness after a gate, citing [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps): "Separating the agent doing the work from the agent judging it proves to be a strong lever". | Source 1; Source 3 |
| [ ] | (C3) A JSON schema describes the file, so a script can reject a malformed edit. | Structured formats for state data. | [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) |
| [ ] | One feature per session. | "work on only one feature at a time"; Source 3: "worked well for scope management." | Source 1; Source 3 |
| [ ] | Each phase has a list of paths the agent may change; changes outside it are rejected or reverted. | Source 2: "File operations restricted to the project directory only"; [Harness engineering](https://openai.com/index/harness-engineering/): "enforce boundaries centrally, allow autonomy locally." The per-phase list is the course's application of both. | Source 2; Source 5 |
| [ ] | (C4) Layering is enforced by code (an import-linter contract or a structural test). | "These constraints are enforced mechanically via custom linters ... and structural tests." | Source 5 |
| [ ] | (C5) The agent runs in a container with no network. | "for each agent, a Docker container is spun up"; "Claude did not have internet access at any point during its development". | [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) |
| [ ] | Commands outside an allowlist are blocked. | "Commands not in the allowlist are blocked by the security hook." | Source 2 |

## Signs the scope part is missing

- The agent starts three features in one session and finishes none.
- A feature is marked done by editing its description to match what was built.
- The agent edits a test file in the build phase to make a failing test pass.

## Notes

- Source 1 calls feature-list entries "tests" in its strongly-worded instruction; it means the entries,
  not unit test files.
- File presence is all the assessment can see for C5. A Dockerfile does not prove the agent runs
  inside it.

## Sources

- Source 1: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 2: Autonomous Coding Agent Demo (README in claude-quickstarts),
  <https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding>, Anthropic,
  2025-11-26
- Source 3: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 4: Prompting best practices,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>,
  Anthropic (Claude docs), n.d.
- Source 5: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 6: Building a C compiler with a team of parallel Claudes,
  <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic),
  2026-02-05
