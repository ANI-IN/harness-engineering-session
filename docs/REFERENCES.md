# References

The public sources this course cites, with their URLs, and the findings that the course
material cites by id. A finding id such as F-a-05 names one short verbatim quote from one
source; source ids (A1, B11, D27, ...) are listed below.

Every source was accessed on 2026-10-16.

## Teaching sources

| ID | Title | Author or organization | Date | URL |
|---|---|---|---|---|
| A1 | Harness engineering: leveraging Codex in an agent-first world | Ryan Lopopolo, OpenAI | 2026-02-11 | https://openai.com/index/harness-engineering/ |
| A2 | Effective harnesses for long-running agents | Justin Young, Anthropic | 2025-11-26 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| A3 | Harness design for long-running application development | Prithvi Rajasekaran, Anthropic | 2026-03-24 | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| A4 | Building a C compiler with a team of parallel Claudes | Nicholas Carlini, Anthropic | 2026-02-05 | https://www.anthropic.com/engineering/building-c-compiler |
| A5 | Autonomous Coding Agent Demo (README) | Anthropic | README committed 2025-11-26 | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |
| A6 | Prompting best practices (multi-context-window and state-management sections) | Anthropic, Claude docs | living page | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#workflows-across-multiple-context-windows |
| A7 | Using PLANS.md for multi-hour problem solving | Aaron Friel, OpenAI Cookbook | 2025-10-07 (archived) | https://cookbook.openai.com/articles/codex_exec_plans |
| B1 | Agent Skills Specification | Agent Skills project | undated | https://agentskills.io/specification |
| B2 | What are skills? | Agent Skills project | undated | https://agentskills.io/home |
| B3 | How to add skills support to your agent | Agent Skills project | undated | https://agentskills.io/client-implementation/adding-skills-support.md |
| B4 | agentskills/agentskills (GitHub repo) | Agent Skills project | repo; last skills-ref commit seen 2026-08-03 | https://github.com/agentskills/agentskills |
| B5 | skills-ref README and source (`validator.py`, `parser.py`, `pyproject.toml`) | Keith Lazuka (Anthropic), per pyproject | repo files | https://github.com/agentskills/agentskills/tree/main/skills-ref |
| B6 | skills-ref on PyPI | Keith Lazuka | 0.1.0 and 0.1.1 both released 2026-01-10 | https://pypi.org/project/skills-ref/ ; https://pypi.org/pypi/skills-ref/json |
| B7 | Extend Claude with skills | Anthropic | living page | https://code.claude.com/docs/en/skills |
| B8 | Build skills (Codex) | OpenAI | living page | https://learn.chatgpt.com/docs/build-skills ; https://developers.openai.com/codex/skills |
| B9 | Agent Skills (Cursor docs) | Anysphere (Cursor) | undated web page | https://cursor.com/docs/context/skills |
| B10 | Cursor 2.4 changelog | Anysphere (Cursor) | 2026-01-22 | https://cursor.com/changelog/2-4 |
| B11 | Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM) | Alshahwan et al., Meta | 2024-02-14; FSE '24 | https://arxiv.org/abs/2402.09171 |
| B12 | Mutation-Guided LLM-based Test Generation at Meta (ACH) | Foster et al., Meta | 2025-01-22; submitted to FSE 2025 Industry Track | https://arxiv.org/abs/2501.12862 |
| B13 | SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents (arXiv 2605.21384v2) | Bingchen Zhao, Dhruv Srikanth, Yuxiang Wu, Zhengyao Jiang (Weco AI) | v1 2026-05-20; v2 2026-09-09; arXiv preprint, no venue listed | https://arxiv.org/abs/2605.21384 |
| B14 | WecoAI/SpecBench (GitHub) | Weco AI | repo | https://github.com/WecoAI/SpecBench |

## Technical references

Official documentation that the course material cites by id.

| ID | Title | URL |
|---|---|---|
| D21 | Codex: Agent approvals & security | https://developers.openai.com/codex/agent-approvals-security |
| D22 | Codex: Sandboxing concepts | https://developers.openai.com/codex/concepts/sandboxing |
| D23 | Codex: Configuration reference | https://developers.openai.com/codex/config-reference |
| D24 | docker container run reference | https://docs.docker.com/reference/cli/docker/container/run/ |
| D25 | Running containers | https://docs.docker.com/engine/containers/run/ |
| D26 | Resource constraints | https://docs.docker.com/engine/containers/resource_constraints/ |
| D27 | None network driver | https://docs.docker.com/engine/network/drivers/none/ |
| D28 | docker container stats | https://docs.docker.com/reference/cli/docker/container/stats/ |
| D29 | Docker Engine API v1.51 spec | https://docs.docker.com/reference/api/engine/version/v1.51.yaml |
| D30 | Dockerfile reference (USER) | https://docs.docker.com/reference/dockerfile/ |
| E1 | PyPI JSON API, one call per package listed in the tool-versions table (version, upload time of the first file, `requires_python`, classifiers, license expression) | https://pypi.org/pypi/{package}/json |
| E2 | boltons repository, tag 26.2.0 | https://github.com/mahmoud/boltons/tree/26.2.0 |
| E3 | boltons LICENSE (BSD-3-Clause text) | https://github.com/mahmoud/boltons/blob/26.2.0/LICENSE |
| E4 | WTForms repository, tag 3.2.2 | https://github.com/pallets-eco/wtforms/tree/3.2.2 |
| E5 | WTForms LICENSE.rst (BSD-3-Clause text) | https://github.com/pallets-eco/wtforms/blob/3.2.2/LICENSE.rst |
| E6 | packaging repository, tag 26.3 (evaluated, rejected) | https://github.com/pypa/packaging/tree/26.3 |

## Findings

| ID | Source | Quote | URL |
|---|---|---|---|
| F-a-02 | A1 | "design environments, specify intent, and build feedback loops that allow Codex agents to do reliable work." | https://openai.com/index/harness-engineering/ |
| F-a-05 | A1 | "From the agent’s point of view, anything it can’t access in-context while running effectively doesn’t exist." | https://openai.com/index/harness-engineering/ |
| F-a-06 | A1 | "Knowledge that lives in Google Docs, chat threads, or people’s heads are not accessible to the system." | https://openai.com/index/harness-engineering/ |
| F-a-07 | A1 | "If it isn’t discoverable to the agent, it’s illegible in the same way it would be unknown to a new hire joining three months later." | https://openai.com/index/harness-engineering/ |
| F-a-08 | A2 | "each new session begins with no memory of what came before." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-09 | A2 | "Imagine a software project staffed by engineers working in shifts, where each new engineer arrives with no memory of what happened on the previous shift." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-11 | A2 | "the agent tended to try to do too much at once—essentially to attempt to one-shot the app." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-12 | A2 | "leaving the next session to start with a feature half-implemented and undocumented. The agent would then have to guess at what had happened" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-13 | A2 | "a later agent instance would look around, see that progress had been made, and declare the job done." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-14 | A3 | "When asked to evaluate work they've produced, agents tend to respond by confidently praising the work—even when, to a human observer, the quality is obviously mediocre." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-15 | A3 | "agents reliably skew positive when grading their own work." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-17 | A4 | "For autonomous systems, it is easy to see tests pass and assume the job is done, when this is rarely the case." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-18 | A4 | "(Run this in a container, not your actual machine)." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-19 | A4 | "in one instance, I did see Claude pkill -9 bash on accident, thus killing itself and ending the loop." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-20 | A1 | "Codex replicates patterns that already exist in the repository—even uneven or suboptimal ones. Over time, this inevitably leads to drift." | https://openai.com/index/harness-engineering/ |
| F-a-21 | A6 | "Without guidance, Claude Opus 4.6 may take actions that are difficult to reverse or affect shared systems, such as deleting files, force-pushing, or posting to external services." | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#workflows-across-multiple-context-windows |
| F-a-22 | A1 | "give Codex a map, not a 1,000-page instruction manual." | https://openai.com/index/harness-engineering/ |
| F-a-23 | A1 | "Context is a scarce resource. A giant instruction file crowds out the task, the code, and the relevant docs" | https://openai.com/index/harness-engineering/ |
| F-a-24 | A1 | "Too much guidance becomes non-guidance. When everything is “important,” nothing is." | https://openai.com/index/harness-engineering/ |
| F-a-25 | A1 | "It rots instantly. A monolithic manual turns into a graveyard of stale rules." | https://openai.com/index/harness-engineering/ |
| F-a-26 | A1 | "A single blob doesn’t lend itself to mechanical checks (coverage, freshness, ownership, cross-links), so drift is inevitable." | https://openai.com/index/harness-engineering/ |
| F-a-27 | A1 | "So instead of treating AGENTS.md as the encyclopedia, we treat it as the table of contents." | https://openai.com/index/harness-engineering/ |
| F-a-28 | A1 | "A short AGENTS.md (roughly 100 lines) is injected into context and serves primarily as a map, with pointers to deeper sources of truth elsewhere." | https://openai.com/index/harness-engineering/ |
| F-a-29 | A1 | "The repository’s knowledge base lives in a structured docs/ directory treated as the system of record." | https://openai.com/index/harness-engineering/ |
| F-a-30 | A1 | "In-repository knowledge store layout." (figure caption; file names from the figure, e.g. "uv-llms.txt", "tech-debt-tracker.md") | https://openai.com/index/harness-engineering/ |
| F-a-31 | A1 | "Design documentation is catalogued and indexed, including verification status and a set of core beliefs that define agent-first operating principles." | https://openai.com/index/harness-engineering/ |
| F-a-32 | A1 | "Architecture documentation provides a top-level map of domains and package layering." | https://openai.com/index/harness-engineering/ |
| F-a-33 | A1 | "A quality document grades each product domain and architectural layer, tracking gaps over time." | https://openai.com/index/harness-engineering/ |
| F-a-34 | A1 | "complex work is captured in execution plans with progress and decision logs that are checked into the repository." | https://openai.com/index/harness-engineering/ |
| F-a-36 | A1 | "This enables progressive disclosure: agents start with a small, stable entry point and are taught where to look next, rather than being overwhelmed up front." | https://openai.com/index/harness-engineering/ |
| F-a-37 | A1 | "Dedicated linters and CI jobs validate that the knowledge base is up to date, cross-linked, and structured correctly." | https://openai.com/index/harness-engineering/ |
| F-a-38 | A1 | "A recurring “doc-gardening” agent scans for stale or obsolete documentation that does not reflect the real code behavior and opens fix-up pull requests." | https://openai.com/index/harness-engineering/ |
| F-a-43 | A1 | "When documentation falls short, we promote the rule into code" | https://openai.com/index/harness-engineering/ |
| F-a-45 | A7 | "We enable Codex to use these documents by first updating AGENTS.md to describe when to use PLANS.md" | https://cookbook.openai.com/articles/codex_exec_plans |
| F-a-46 | A7 | "Every ExecPlan must be fully self-contained. Self-contained means that in its current form it contains all knowledge and instructions needed for a novice to succeed." | https://cookbook.openai.com/articles/codex_exec_plans |
| F-a-47 | A7 | "it should always be possible to restart from _only_ the ExecPlan and no other work." | https://cookbook.openai.com/articles/codex_exec_plans |
| F-a-48 | A7 | "ExecPlans must contain and maintain a `Progress` section, a `Surprises & Discoveries` section, a `Decision Log`, and an `Outcomes & Retrospective` section." | https://cookbook.openai.com/articles/codex_exec_plans |
| F-a-49 | A2 | "an initializer agent that sets up the environment on the first run, and a coding agent that is tasked with making incremental progress in every session" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-50 | A2 | "an init.sh script, a claude-progress.txt file that keeps a log of what agents have done, and an initial git commit that shows what files were added." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-52 | A2 | "We refer to these as separate agents in this context only because they have different initial user prompts." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-53 | A2 | "accomplished with the claude-progress.txt file alongside the git history." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-54 | A2 | "However, compaction isn’t sufficient." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-56 | A2 | "ask the model to commit its progress to git with descriptive commit messages and to write summaries of its progress in a progress file." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-57 | A2 | "This allowed the model to use git to revert bad code changes and recover working states of the code base." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-58 | A2 | "Run pwd to see the directory you’re working in. You’ll only be able to edit files in this directory." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-59 | A2 | "Read the git logs and progress files to get up to speed on what was recently worked on." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-60 | A2 | "Read the features list file and choose the highest-priority feature that’s not yet done to work on." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-61 | A2 | "ask the initializer agent to write an init.sh script that can run the development server, and then run through a basic end-to-end test before implementing a new feature." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-62 | A2 | "If the agent had instead started implementing a new feature, it would likely make the problem worse." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-63 | A2 | "End the session by writing a git commit and progress update." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-65 | A3 | "Context resets—clearing the context window entirely and starting a fresh agent, combined with a structured handoff that carries the previous agent's state and the next steps" | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-66 | A3 | "While compaction preserves continuity, it doesn't give the agent a clean slate, which means context anxiety can still persist." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-67 | A3 | "Some models also exhibit \"context anxiety,\" in which they begin wrapping up work prematurely as they approach what they believe is their context limit." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-68 | A3 | "This solves the core issue, but adds orchestration complexity, token overhead, and latency to each harness run." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-69 | A3 | "Opus 4.5 largely removed that behavior on its own, so I was able to drop context resets from this harness entirely." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-71 | A3 | "decomposing the build into tractable chunks, and using structured artifacts to hand off context between sessions." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-78 | A2 | "These features were all initially marked as “failing” so that later coding agents would have a clear outline of what full functionality looked like." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-79 | A2 | "We prompt coding agents to edit this file only by changing the status of a passes field" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-80 | A2 | "“It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality.”" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-81 | A2 | "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-82 | A2 | "\"passes\": false" (example entry with "category", "description", "steps") | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-83 | A2 | "the next iteration of the coding agent was then asked to work on only one feature at a time." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-84 | A2 | "By “clean state” we mean the kind of code that would be appropriate for merging to a main branch" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-85 | A5 | "feature_list.json         # Test cases (source of truth)" | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |
| F-a-86 | A5 | "File operations restricted to the project directory only" | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |
| F-a-87 | A5 | "Commands not in the allowlist are blocked by the security hook." | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |
| F-a-88 | A4 | "for each agent, a Docker container is spun up with the repo mounted to /upstream." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-90 | A4 | "Claude did not have internet access at any point during its development" | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-92 | A1 | "By enforcing invariants, not micromanaging implementations, we let agents ship fast without undermining the foundation." | https://openai.com/index/harness-engineering/ |
| F-a-93 | A1 | "These constraints are enforced mechanically via custom linters (Codex-generated, of course!) and structural tests." | https://openai.com/index/harness-engineering/ |
| F-a-96 | A1 | "we statically enforce structured logging, naming conventions for schemas and types, file size limits, and platform-specific reliability requirements with custom lints." | https://openai.com/index/harness-engineering/ |
| F-a-97 | A1 | "Because the lints are custom, we write the error messages to inject remediation instructions into agent context." | https://openai.com/index/harness-engineering/ |
| F-a-98 | A1 | "enforce boundaries centrally, allow autonomy locally." | https://openai.com/index/harness-engineering/ |
| F-a-99 | A1 | "we started encoding what we call “golden principles” directly into the repository and built a recurring cleanup process." | https://openai.com/index/harness-engineering/ |
| F-a-108 | A2 | "Self-verify all features. Only mark features as “passing” after careful testing." | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| F-a-110 | A3 | "Separating the agent doing the work from the agent judging it proves to be a strong lever to address this issue." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-111 | A3 | "tuning a standalone evaluator to be skeptical turns out to be far more tractable than making a generator critical of its own work" | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-112 | A3 | "the evaluator is still an LLM that is inclined to be generous towards LLM-generated outputs." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-113 | A3 | "\"Is this design beautiful?\" is hard to answer consistently, but \"does this follow our principles for good design?\" gives Claude something concrete to grade against." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-119 | A3 | "Each criterion had a hard threshold, and if any one fell below it, the sprint failed and the generator got detailed feedback on what went wrong." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-123 | A3 | "The practical implication is that the evaluator is not a fixed yes-or-no decision. It is worth the cost when the task sits beyond what the current model does reliably solo." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-124 | A3 | "every component in a harness encodes an assumption about what the model can't do on its own, and those assumptions are worth stress testing" | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-125 | A3 | "removing one component at a time and reviewing what impact it had on the final result." | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-126 | A3 | "It is always good practice to experiment with the model you're building against, read its traces on realistic problems, and tune its performance" | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| F-a-127 | A4 | "it’s important that the task verifier is nearly perfect, otherwise Claude will solve the wrong problem." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-129 | A4 | "I built a continuous integration pipeline and implemented stricter enforcement that allowed Claude to better test its work so that new commits can’t break existing code." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-131 | A4 | "The test harness should not print thousands of useless bytes. At most, it should print a few lines of output and log all important information to a file" | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-132 | A4 | "if there are errors, Claude should write ERROR and put the reason on the same line so grep will find it." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-135 | A4 | "LLM-written code frequently re-implements existing functionality, so I tasked one agent with coalescing any duplicate code it found." | https://www.anthropic.com/engineering/building-c-compiler |
| F-a-143 | A1 | "should not be assumed to generalize without similar investment—at least, not yet." | https://openai.com/index/harness-engineering/ |
| F-b-01 | B1 | "The `SKILL.md` file must contain YAML frontmatter followed by Markdown content." | https://agentskills.io/specification |
| F-b-02 | B1 | "Must match the parent directory name" | https://agentskills.io/specification |
| F-b-03 | B1 | "Should describe both what the skill does and when to use it" | https://agentskills.io/specification |
| F-b-05 | B1 | "The `name` and `description` fields are loaded at startup for all skills" | https://agentskills.io/specification |
| F-b-06 | B1 | "Keep your main `SKILL.md` under 500 lines. Move detailed reference material to separate files." | https://agentskills.io/specification |
| F-b-07 | B1 | "Keep file references one level deep from `SKILL.md`. Avoid deeply nested reference chains." | https://agentskills.io/specification |
| F-b-09 | B3 | "Name doesn't match the parent directory name → warn, load anyway" | https://agentskills.io/client-implementation/adding-skills-support.md |
| F-b-10 | B5 | "This library is intended for demonstration purposes only. It is not meant to be used in production." | https://github.com/agentskills/agentskills/tree/main/skills-ref |
| F-b-11 | B5 | "Unexpected fields in frontmatter: {extras}. Only {allowed} are allowed." | https://github.com/agentskills/agentskills/tree/main/skills-ref |
| F-b-12 | B7 | "Claude Code skills follow the Agent Skills open standard, which works across multiple AI tools." | https://code.claude.com/docs/en/skills |
| F-b-14 | B8 | "Codex scans `.agents/skills` in every directory from your current working directory" | https://learn.chatgpt.com/docs/build-skills |
| F-b-15 | B9 | "For compatibility, Cursor also loads skills from Claude and Codex directories" | https://cursor.com/docs/context/skills |
| F-b-16 | B11 | "applying a series of progressively demanding semantic filters to candidate solutions generated by the language models." | https://arxiv.org/abs/2402.09171 |
| F-b-17 | B11 | "The first filter simply checks that the candidate code is fully buildable within the existing infrastructure of the app under test." | https://arxiv.org/abs/2402.09171 |
| F-b-18 | B11 | "TestGen-LLM discards any test case that does not pass on first execution." | https://arxiv.org/abs/2402.09171 |
| F-b-19 | B11 | "a test that does not pass on every one of five executions is deemed flaky." | https://arxiv.org/abs/2402.09171 |
| F-b-20 | B11 | "Any test that does not improve coverage is also discarded." | https://arxiv.org/abs/2402.09171 |
| F-b-21 | B11 | "The candidate test cases that pass through all three filters are thus guaranteed to improve the existing test class, and to provide reliable regression test signal." | https://arxiv.org/abs/2402.09171 |
| F-b-22 | B11 | "retaining all existing test cases and thereby guaranteeing there will be no regression, by construction." | https://arxiv.org/abs/2402.09171 |
| F-b-23 | B11 | "25% of test classes had at least one test case that builds correctly, passes and increases line coverage" | https://arxiv.org/abs/2402.09171 |
| F-b-24 | B11 | "TestGen-LLM was therefore able to automatically improve approximately 10% of the test classes to which it was applied. Over all, 73%" | https://arxiv.org/abs/2402.09171 |
| F-b-25 | B11 | "A trial is only considered successful if the generated test case builds, passes, and increases coverage over all existing test cases." | https://arxiv.org/abs/2402.09171 |
| F-b-26 | B11 | "we doubled down on this observation and included an extra filter to remove previously seen test cases." | https://arxiv.org/abs/2402.09171 |
| F-b-28 | B11 | "TestGen-LLM's goal is to provide a recommender system [1], that leaves the software engineer in ultimate control of the code that lands into the code base." | https://arxiv.org/abs/2402.09171 |
| F-b-29 | B12 | "construct mutants that denote faults that are both relevant to the issue of concern and also currently not caught (unkilled) by any existing test case" | https://arxiv.org/abs/2501.12862 |
| F-b-32 | B12 | "Hardening: The new tests catch faults that no existing test can catch" | https://arxiv.org/abs/2501.12862 |
| F-b-34 | B12 | "extra test cases that will fail on the mutant version of the class, but would pass on the correct version." | https://arxiv.org/abs/2501.12862 |
| F-b-40 | B12 | "a large proportion (49%) of test cases that uniquely additionally kill a mutant, do not also add line coverage." | https://arxiv.org/abs/2501.12862 |
| F-b-41 | B12 | "This allows us to protect against future regressions, but it cannot detect existing faults residing in the code base." | https://arxiv.org/abs/2501.12862 |
| F-b-42 | B13 | "visible validation tests that exercise specified features in isolation, and (iii) held-out tests that compose those same features to simulate real-world usage." | https://arxiv.org/abs/2605.21384 |
| F-b-43 | B13 | "A separate held-out test suite ... never shown to the agent, is used solely for evaluation." | https://arxiv.org/abs/2605.21384 |
| F-b-44 | B13 | "Crucially, test introduces no requirements beyond what [spec] and val already specify. Every composition tested is mandated by the specification." | https://arxiv.org/abs/2605.21384 |
| F-b-45 | B13 | "while every frontier agent saturates the visible suite, reward hacking persists, with smaller models exhibiting larger gaps on holdout suites." | https://arxiv.org/abs/2605.21384 |
| F-b-46 | B13 | "it grows by 28 percentage points for every tenfold increase in code size." | https://arxiv.org/abs/2605.21384 |
| F-b-50 | B13 | "Figure 9 shows that deliberate exploits are rare, while compositional failures account for a much larger fraction of reward hacking behavior." | https://arxiv.org/abs/2605.21384 |
| F-b-51 | B13 | "These findings suggest that reward hacking cannot be eliminated by improving the test suite alone" | https://arxiv.org/abs/2605.21384 |
