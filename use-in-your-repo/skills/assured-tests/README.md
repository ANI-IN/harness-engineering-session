# Module 1: Harness Engineering for Coding Agents - Skill: assured-tests

## The problem

**Illustrative scenario.** You ask an agent to add tests to a module with thin coverage. It writes a
dozen, they all pass, and the coverage number goes up. A month later a real bug ships in that module.
Half of the new tests asserted almost nothing, and one passed only because it mocked the code it was
meant to test.

## Why it happens

- Agents grade their own work kindly: "agents reliably skew positive when grading their own work."
  ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps))
- A generated test can fail on correct code, pass by luck, or pass without checking anything. Meta's
  [TestGen-LLM](https://arxiv.org/abs/2402.09171) keeps a test only after "progressively demanding semantic filters".

## How this skill helps

An Agent Skill that generates unit tests for one Python module and keeps only the tests that pass
five filters. A skill is a folder with a `SKILL.md` file (YAML frontmatter, then Markdown
instructions) and optional `scripts/`, `references/`, and `assets/` folders ([Agent Skills Specification](https://agentskills.io/specification)). This page
says what the skill does, how to install it in Claude Code, Codex, and Cursor, how to call it, and
how to check that it loaded. The instructions the agent follows are in [SKILL.md](SKILL.md).

Sources are cited by their linked title, then as "Source N", and listed in full at the end of
this page.

## What it does and when to use it

A generated test can fail on correct code, pass by luck, or pass without checking anything.
[TestGen-LLM](https://arxiv.org/abs/2402.09171) at Meta runs every candidate through "progressively
demanding semantic filters" and keeps only the survivors. This skill applies the same idea. Its script runs
`shipharness testgen`, which proposes tests with a model and keeps a test only if it passes all
five filters, cheapest first:

| Filter | What it checks | Source |
|---|---|---|
| Filter 1: Builds and collects | pytest collects the test with no errors | Source 2, "buildable" |
| Filter 2: Passes five runs | The test passes on every one of five runs | Source 2 |
| Filter 3: Adds coverage or catches a mutant | New line coverage, or a mutant no existing test kills | Source 2; [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862) |
| Filter 4: Real assertions | An assertion that can fail; the unit under test is not mocked | Course filter; no direct source |
| Filter 5: No source changes | No source file changed during the test phase | Course filter, built on Source 2; [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) |

A mutant is a copy of the code with one small bug planted on purpose; a test kills it when the
test fails on that copy.

Filters 4 and 5 are the course's own additions and are presented as such. The agent then reads the
result table (one row per proposed test, with the first filter it failed and why) and reviews the
kept tests as code.

Use it when a module has thin coverage and you want tests that are proven to add something; when
you want to protect a specific behaviour (tenant isolation, permission checks) against a known
kind of fault by writing mutants for that fault (Source 4); or when you want to compare filtered tests
with what an agent writes unfiltered (`--layers none`).

## What is in the folder

| Path | What it is |
|---|---|
| `SKILL.md` | The instructions the agent loads when the skill is used |
| `scripts/run_testgen.py` | Builds and runs the `shipharness testgen` command; `--dry-run` prints it without running; Python 3.10+ standard library only |
| `references/filters.md` | Why each filter exists and what it cannot catch |
| `references/testgen-llm.md`, `references/ach.md` | Short summaries of the two papers (Source 2; Source 4) |

Agents load only the `name` and `description` of every installed skill at startup and read the
rest of `SKILL.md` when a task matches the description; reference files are read only when a step
needs them (Source 3; [Agent Skills Overview](https://agentskills.io/home)).

## What you need

- Python 3.12+, uv, and the shipharness CLI with an OpenAI key (the skill's `compatibility` field).
  The script calls `shipharness` if it is on your PATH and `uv run shipharness` otherwise, which
  works from inside the shipharness checkout.
- A repository with a pytest suite, and coverage.py configured (Filter 3 measures line coverage).
- Docker, if you want generated tests to run in a container (`--sandbox docker --image <image>`).
  Without it, generated tests run on your machine with your permissions, and both the script and
  shipharness say UNSANDBOXED. Use a container for any repository you do not trust.

## Install

The [Agent Skills Specification](https://agentskills.io/specification) does not say where skills live; each agent has its own folders
([How to add skills support to your agent](https://agentskills.io/client-implementation/adding-skills-support.md)). These are the folders each tool documents, checked on its official page on
2026-10-17.

| Tool | Project folder | User-level folder | Skill folders it reads |
|---|---|---|---|
| Claude Code | `.claude/skills/assured-tests/` | `~/.claude/skills/assured-tests/` | `.claude/skills/` (`.agents/skills/` not documented) |
| Codex | `.agents/skills/assured-tests/` | `$HOME/.agents/skills/assured-tests/` | `.agents/skills/` (`.claude/skills/` not documented) |
| [Cursor 2.4](https://cursor.com/changelog/2-4) or later | `.agents/skills/assured-tests/` or `.cursor/skills/assured-tests/` | `~/.agents/skills/assured-tests/` or `~/.cursor/skills/assured-tests/` | Both |

What each page says:

- Claude Code reads personal skills from `~/.claude/skills/<skill-name>/SKILL.md` and project
  skills from `.claude/skills/<skill-name>/SKILL.md`, in the folder where you start it and in every
  parent folder up to the repository root. If the same name exists at both levels, the personal
  skill wins. Claude Code watches these folders and picks up added or edited skills without a
  restart; if the `.claude/skills/` folder did not exist when the session started, run
  `/reload-skills`. The page does not mention `.agents/skills/`. ([Extend Claude with skills](https://code.claude.com/docs/en/skills), read 2026-10-17.)
- Codex scans `.agents/skills` in every folder from the working directory up to the repository
  root, then `$HOME/.agents/skills` and `/etc/codex/skills`. It detects new skills automatically;
  if one does not appear, restart Codex. It follows symlinked skill folders. The page does not
  mention `.claude/skills/`. ([Build skills](https://learn.chatgpt.com/docs/build-skills), redirected
  from https://developers.openai.com/codex/skills, read 2026-10-17.)
- Cursor reads `.agents/skills/` and `.cursor/skills/` in the project and `~/.agents/skills/` and
  `~/.cursor/skills/` in your home folder, and for compatibility also `.claude/skills/`,
  `.codex/skills/`, `~/.claude/skills/`, and `~/.codex/skills/`. It discovers skills when it
  starts. ([Agent Skills (Cursor docs)](https://cursor.com/docs/skills), redirected from
  https://cursor.com/docs/context/skills, read 2026-10-17.) Skills arrived in
  [Cursor 2.4](https://cursor.com/changelog/2-4), released 2026-01-22, "in the editor and CLI" (changelog read 2026-10-17). The page does not say whether a skill added
  while Cursor is open appears without a restart (not documented as of 2026-10-17); restart Cursor
  if it does not appear.

No single folder is documented for all three tools. Copy the skill into both `.claude/skills/` and
`.agents/skills/`: Claude Code reads the first, Codex the second, and Cursor both. Run these from
the root of your shipharness checkout:

```bash
SKILL=assured-tests
TARGET=~/my-repo        # your repository; use TARGET=~ for a user-level install
mkdir -p "$TARGET/.claude/skills" "$TARGET/.agents/skills"
cp -r "use-in-your-repo/skills/$SKILL" "$TARGET/.claude/skills/"
cp -r "use-in-your-repo/skills/$SKILL" "$TARGET/.agents/skills/"
```

```powershell
$Skill = "assured-tests"
$Target = "C:\path\to\my-repo"   # your repository; use $Target = $HOME for a user-level install
New-Item -ItemType Directory -Force "$Target\.claude\skills", "$Target\.agents\skills" | Out-Null
Copy-Item -Recurse "use-in-your-repo\skills\$Skill" "$Target\.claude\skills\"
Copy-Item -Recurse "use-in-your-repo\skills\$Skill" "$Target\.agents\skills\"
```

With `TARGET=~` the same commands write `~/.claude/skills/assured-tests/` (Claude Code and Cursor)
and `~/.agents/skills/assured-tests/` (Codex and Cursor). To update an installed copy, delete it
first and copy again, so files removed from the skill do not linger. Cursor reads both folders;
the course has not checked which copy it uses when both hold the same name, so keep the two copies
identical.

## Check the files before you start an agent

Run the course validator on the source folder and on each installed copy:

```bash
uv run shipharness skills validate use-in-your-repo/skills/assured-tests
uv run shipharness skills validate ~/my-repo/.claude/skills/assured-tests
uv run shipharness skills validate ~/my-repo/.agents/skills/assured-tests
```

Captured on 2026-10-17 from `uv run shipharness skills validate use-in-your-repo/skills/assured-tests`;
your output will differ:

```text
+ assured-tests: valid (SKILL.md 96 lines)
1 skill checked, 0 errors, 0 warnings
Cost: $0.000000 (no model calls)
```

`shipharness skills validate` runs the checks of skills-ref, the reference validator, and adds
warnings for a `SKILL.md` over 500 lines, reference chains deeper than one level, and missing
referenced files (Source 3; [skills-ref](https://github.com/agentskills/agentskills)). The skill uses only the six frontmatter
fields the specification allows, so it also passes the reference validator itself,
`uv run agentskills validate use-in-your-repo/skills/assured-tests` (captured on 2026-10-17 from that command: `Valid skill: use-in-your-repo/skills/assured-tests`).

The validators check the files. They do not show that a tool loaded the skill; for that, see the
next section.

## Use it

| Tool | Call it by name | Let the agent choose it | See that it loaded |
|---|---|---|---|
| Claude Code | `/assured-tests` | Claude uses a skill when the task matches its description | Ask "What skills are available?", or type `/` and look for `/assured-tests` (Source 9, read 2026-10-17) |
| Codex (CLI or IDE extension) | Type `$assured-tests`, or run `/skills` and pick it | Codex can choose a skill when the task matches its description | Run `/skills` and look for it in the list (Source 10, read 2026-10-17) |
| Cursor | Type `/` in Agent chat and search for `assured-tests` | The agent applies a skill when it judges it relevant | Open **Customize** in the sidebar, then **Skills** (Source 11, read 2026-10-17) |

Example prompt, the same in all three tools (prefix `/assured-tests` in Claude Code or
`$assured-tests` in Codex to call it by name):

```text
Add assured tests for app/services/members.py. Run the existing suite first and tell me about
any failures. Preview the testgen command with --dry-run and wait for my go-ahead before the real
run, because it calls a model. Then explain every discarded test by the first filter it failed,
and review the kept tests as code.
```

The agent runs the script from the installed folder, for example
`python .claude/skills/assured-tests/scripts/run_testgen.py --repo . --module <path> --max-tests 8 --dry-run`.
Captured on 2026-10-17 against the course's TeamTrack app from
`python3 use-in-your-repo/skills/assured-tests/scripts/run_testgen.py --repo platform/teamtrack --module app/services/members.py --max-tests 8 --dry-run`
(run from the checkout root, with no `shipharness` on the PATH, so the script falls back to
`uv run shipharness`):

```text
command: uv run shipharness testgen --repo platform/teamtrack --module app/services/members.py --layers verify --max-tests 8
note: UNSANDBOXED. Generated tests will run on this machine with your permissions. Use --sandbox docker --image <image> to run them in a container.
note: this calls a model and costs money; the command prints a Cost: line at the end.
```

The dry run makes no model calls. The real run, without `--dry-run`, does. One real run of
`shipharness testgen` on a TeamTrack module (the command the script wraps), captured on 2026-10-17 (the run id is
replaced; the target line is cut); discarded-test lines cut to the first one:

```text
$ uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 --out .shipharness/a4/testgen
! UNSANDBOXED — results not official: generated tests run on this machine
Baseline: existing suite without doctests
testgen <run id>: completed; kept 1 of 5 proposed tests
+ tests/visible/test_issue_repository.py::test_list_for_project_uses_ascending_keyset_pages
- tests/visible/test_issue_repository.py::test_add_flushes_issue_with_requested_fields_and_database_defaults: filter 3: adds no line coverage over the existing suite and kills no filter-set mutant that the existing tests miss (0 checked)
Kept tests and report: .shipharness/a4/testgen
Cost: $0.003287 (testgen, model gpt-6-luna)
```

The other three proposed tests were discarded by Filter 3 for the same reason: on a module the
existing suite already covers, most proposals add nothing, as the Limits section below says.

## What it costs

Two things cost money, and both are yours:

- The skill runs inside your own agent (Claude Code, Codex, or Cursor), on that tool's model and
  your plan or API account with that vendor. The course does not pay for it and has not measured
  how many tokens a run uses.
- `shipharness testgen` calls the OpenAI API with your key. It prints `Cost: $X` when it ends and
  stops at the per-run cost cap, `MAX_RUN_COST_USD`, whose default is $0.20
  (`platform/src/shipharness/config/settings.py`). The run shown above, with 5 proposed tests, cost
$0.003287; that is one measured run, not a typical cost.
  When LangSmith tracing is on and `LANGSMITH_API_KEY` is set, the run is also traced to the
  `shipharness-testgen` project, which counts against your LangSmith trace allowance.

## Limits

- The current code is the oracle. A kept test asserts what the code does today, so it protects
  against future regressions, but it "cannot detect existing faults residing in the code base"
  (Source 4).
- Five runs catch most flaky tests, not all of them. The number five comes from Source 2.
- The filters prove a test runs reliably and adds coverage or catches a mutant. They do not prove
  that its name and assertions describe the behaviour you want; review kept tests as code.
- On a well-tested module most proposals fail Filter 3. That is expected; add mutants for the
  faults you care about and run again.
- Without `--sandbox docker`, generated tests run with your permissions on your machine.
- The tool facts above come from each vendor's documentation as read on 2026-10-17. The course did
  not run the skill inside Claude Code, Codex, or Cursor to confirm them; vendors change these
  pages, so check them again if a skill does not appear.

Related skills: [harness-setup](../harness-setup/README.md) checks whether coverage is configured
(its coverage check, `V5`); [house-rules](../house-rules/README.md) turns a rule into a check with a seeded
violation.

## Sources

- Source 1: Harness design for long-running application development,
  <https://www.anthropic.com/engineering/harness-design-long-running-apps>,
  Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 2: Automated Unit Test Improvement using Large Language Models at Meta (TestGen-LLM),
  <https://arxiv.org/abs/2402.09171>, Alshahwan et al. (Meta), 2024-02-14
- Source 3: Agent Skills Specification, <https://agentskills.io/specification>,
  Agent Skills project, n.d.
- Source 4: Mutation-Guided LLM-based Test Generation at Meta (ACH),
  <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta), 2025-01-22
- Source 5: Effective harnesses for long-running agents,
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>,
  Justin Young (Anthropic), 2025-11-26
- Source 6: Agent Skills Overview, <https://agentskills.io/home>, Agent Skills project, n.d.
- Source 7: How to add skills support to your agent,
  <https://agentskills.io/client-implementation/adding-skills-support.md>, Agent Skills project,
  n.d.
- Source 8: Cursor 2.4 changelog, <https://cursor.com/changelog/2-4>, Cursor, 2026-01-22
- Source 9: Extend Claude with skills, <https://code.claude.com/docs/en/skills>,
  Anthropic (Claude Code docs), n.d.
- Source 10: Build skills, <https://learn.chatgpt.com/docs/build-skills>, OpenAI (Codex docs), n.d.
- Source 11: Agent Skills (Cursor docs), <https://cursor.com/docs/skills>, Cursor, n.d.
- Source 12: skills-ref, the reference validator (source and README),
  <https://github.com/agentskills/agentskills>, Agent Skills project, PyPI package 0.1.1, 2026-01-10
