# Instructions checklist: what the agent knows

Sources are listed at the end of this page.
Assessment checks I1-I6 test the items marked with a check id.

| Done | Item | Why | Source |
|---|---|---|---|
| [ ] | (I1) AGENTS.md exists at the repository root. | It is injected into the agent's context at the start of every session. | [Harness engineering](https://openai.com/index/harness-engineering/) |
| [ ] | (I2) AGENTS.md is roughly 100 lines and reads as a map with pointers. | "we treat it as the table of contents"; a giant file "crowds out the task, the code, and the relevant docs". | Source 1 |
| [ ] | (I3) Every pointer in AGENTS.md resolves to a file or folder. | Source 1 checks that the knowledge base is "up to date, cross-linked, and structured correctly" with linters and CI jobs. | Source 1 |
| [ ] | (I4) ARCHITECTURE.md at the root maps domains and package layering. | "Architecture documentation provides a top-level map of domains and package layering." | Source 1 |
| [ ] | (I5) docs/ holds the detail: SECURITY.md, RELIABILITY.md, QUALITY_SCORE.md, PLANS.md, design-docs/, product-specs/, references/, exec-plans/. | "structured docs/ directory treated as the system of record". Source 1 gives these names in its layout figure. | Source 1 |
| [ ] | (I6) Skills sit in both `.claude/skills/` and `.agents/skills/` and pass the spec's validator. | No single folder is read by Claude Code, Codex, and Cursor. | [Agent Skills Specification](https://agentskills.io/specification); [Extend Claude with skills](https://code.claude.com/docs/en/skills); [Build skills](https://learn.chatgpt.com/docs/build-skills); [Agent Skills (Cursor docs)](https://cursor.com/docs/skills) |
| [ ] | Rules that live in chat threads, wikis, or people's heads are moved into the repository. | "Knowledge that lives in Google Docs, chat threads, or people’s heads are not accessible to the system." | Source 1 |
| [ ] | Code that must not be copied is marked as legacy, next to the pattern to copy instead. | "Codex replicates patterns that already exist in the repository—even uneven or suboptimal ones." | Source 1 |
| [ ] | Error messages from custom checks say how to fix the problem. | "we write the error messages to inject remediation instructions into agent context." | Source 1 |
| [ ] | Each design doc records whether it is verified against the code. | Design docs are indexed "including verification status and a set of core beliefs". | Source 1 |
| [ ] | A quality document grades each domain and layer and lists known gaps. | "A quality document grades each product domain and architectural layer, tracking gaps over time." | Source 1 |

## Signs the instructions part is missing

- The agent breaks a rule that is written in a long handbook it never opened.
- The agent copies the oldest handler in the codebase because it was the first match for a search.
- AGENTS.md grows every time something goes wrong, until nobody reads it (Source 1: "It rots instantly.").

## Notes

- "Map" and "table of contents" are the words Source 1 uses for AGENTS.md. Avoid calling it a router.
- Source 1 names SECURITY.md, RELIABILITY.md, PLANS.md, product-specs/, and references/*-llms.txt only in
  its layout figure. The template contents for those files are the course's, not from Source 1.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Agent Skills Specification, <https://agentskills.io/specification>,
  Agent Skills project, n.d.
- Source 3: Extend Claude with skills, <https://code.claude.com/docs/en/skills>,
  Anthropic (Claude Code docs), n.d.
- Source 4: Build skills, <https://learn.chatgpt.com/docs/build-skills>, OpenAI (Codex docs), n.d.
- Source 5: Agent Skills (Cursor docs), <https://cursor.com/docs/skills>, Cursor, n.d.
