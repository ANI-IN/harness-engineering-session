# Module 1: Harness Engineering for Coding Agents - Skill: house-rules

## The problem

**Illustrative scenario.** The same review comment keeps coming back on agent changes: "do not
query across tenants", "write an audit row". The rule is in the docs, and agents still break it,
because they copy an older handler that predates the rule. Every reviewer has to remember to look.

## Why it happens

- Agents copy what they find: agents replicate "patterns that already exist in the repository—even
  uneven or suboptimal ones" ([Harness engineering](https://openai.com/index/harness-engineering/)).
- A rule on paper is not enforced: "When documentation falls short, we promote the rule into code"
  (Source 1).

## How this skill helps

An Agent Skill that turns a team convention into a house rule: a one-page rule document, a
mechanical check whose error message tells the agent how to fix the problem, and a test with a
seeded violation the check must catch. A skill is a folder with a `SKILL.md` file (YAML
frontmatter, then Markdown instructions) and optional `scripts/`, `references/`, and `assets/`
folders ([Agent Skills Specification](https://agentskills.io/specification)). This page says what the skill does, how to install it in Claude Code, Codex,
and Cursor, how to call it, and how to check that it loaded. The instructions the agent follows
are in [SKILL.md](SKILL.md).

Sources are cited by their linked title, such as
[Harness engineering](https://openai.com/index/harness-engineering/), then as "Source N", and
listed in full at the end of this page.

## What it does and when to use it

A house rule is what Source 1 calls "golden principles" encoded in the repository and "taste
invariants" enforced with custom lints. The idea in one line, also from Source 1: "When
documentation falls short, we promote the rule into code".

A house rule is done when all three parts exist:

1. A rule document with the rule in one checkable sentence, why it exists, and the smallest
   correct and incorrect examples.
2. A check that prints one line per violation saying what is wrong and how to fix it. Source 1 writes
   lint messages "to inject remediation instructions into agent context", and [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) asks for
   "ERROR" with the reason "on the same line so grep will find it".
3. A test with a seeded violation the check must catch and a clean case it must pass, written
   before the check.

Use it when the same review comment keeps coming back, when agents copy a pattern that should not
be copied (Source 1: agents replicate "patterns that already exist in the repository—even uneven or
suboptimal ones"), or when a rule is written in the docs and agents still break it. Do not
use it for what a formatter already handles or for one-off decisions; Source 1 enforces invariants and
does not micromanage implementations.

## What is in the folder

| Path | What it is |
|---|---|
| `SKILL.md` | The instructions the agent loads when the skill is used |
| `scripts/new_rule.py` | Writes the rule document, a check stub, and a failing test stub; Python 3.10+ standard library only |
| `assets/rule-template.md` | The rule document template the script copies |

Agents load only the `name` and `description` of every installed skill at startup and read the
rest of `SKILL.md` when a task matches the description (Source 2; [Agent Skills Overview](https://agentskills.io/home)).

## Install

The [Agent Skills Specification](https://agentskills.io/specification) does not say where skills live; each agent has its own folders
([How to add skills support to your agent](https://agentskills.io/client-implementation/adding-skills-support.md)). These are the folders each tool documents, checked on its official page on
2026-10-17.

| Tool | Project folder | User-level folder | Skill folders it reads |
|---|---|---|---|
| Claude Code | `.claude/skills/house-rules/` | `~/.claude/skills/house-rules/` | `.claude/skills/` (`.agents/skills/` not documented) |
| Codex | `.agents/skills/house-rules/` | `$HOME/.agents/skills/house-rules/` | `.agents/skills/` (`.claude/skills/` not documented) |
| [Cursor 2.4](https://cursor.com/changelog/2-4) or later | `.agents/skills/house-rules/` or `.cursor/skills/house-rules/` | `~/.agents/skills/house-rules/` or `~/.cursor/skills/house-rules/` | Both |

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
SKILL=house-rules
TARGET=~/my-repo        # your repository; use TARGET=~ for a user-level install
mkdir -p "$TARGET/.claude/skills" "$TARGET/.agents/skills"
cp -r "use-in-your-repo/skills/$SKILL" "$TARGET/.claude/skills/"
cp -r "use-in-your-repo/skills/$SKILL" "$TARGET/.agents/skills/"
```

```powershell
$Skill = "house-rules"
$Target = "C:\path\to\my-repo"   # your repository; use $Target = $HOME for a user-level install
New-Item -ItemType Directory -Force "$Target\.claude\skills", "$Target\.agents\skills" | Out-Null
Copy-Item -Recurse "use-in-your-repo\skills\$Skill" "$Target\.claude\skills\"
Copy-Item -Recurse "use-in-your-repo\skills\$Skill" "$Target\.agents\skills\"
```

With `TARGET=~` the same commands write `~/.claude/skills/house-rules/` (Claude Code and Cursor)
and `~/.agents/skills/house-rules/` (Codex and Cursor). To update an installed copy, delete it
first and copy again, so files removed from the skill do not linger. Cursor reads both folders;
the course has not checked which copy it uses when both hold the same name, so keep the two copies
identical.

## Check the files before you start an agent

Run the course validator on the source folder and on each installed copy:

```bash
uv run shipharness skills validate use-in-your-repo/skills/house-rules
uv run shipharness skills validate ~/my-repo/.claude/skills/house-rules
uv run shipharness skills validate ~/my-repo/.agents/skills/house-rules
```

Captured on 2026-10-17 from `uv run shipharness skills validate use-in-your-repo/skills/house-rules`;
your output will differ:

```text
+ house-rules: valid (SKILL.md 94 lines)
1 skill checked, 0 errors, 0 warnings
Cost: $0.000000 (no model calls)
```

`shipharness skills validate` runs the checks of skills-ref, the reference validator, and adds
warnings for a `SKILL.md` over 500 lines, reference chains deeper than one level, and missing
referenced files (Source 2; [skills-ref](https://github.com/agentskills/agentskills)). The skill uses only the six frontmatter
fields the specification allows, so it also passes the reference validator itself,
`uv run agentskills validate use-in-your-repo/skills/house-rules` (captured on 2026-10-17 from that command: `Valid skill: use-in-your-repo/skills/house-rules`).

The validators check the files. They do not show that a tool loaded the skill; for that, see the
next section.

## Use it

| Tool | Call it by name | Let the agent choose it | See that it loaded |
|---|---|---|---|
| Claude Code | `/house-rules` | Claude uses a skill when the task matches its description | Ask "What skills are available?", or type `/` and look for `/house-rules` (Source 7, read 2026-10-17) |
| Codex (CLI or IDE extension) | Type `$house-rules`, or run `/skills` and pick it | Codex can choose a skill when the task matches its description | Run `/skills` and look for it in the list (Source 8, read 2026-10-17) |
| Cursor | Type `/` in Agent chat and search for `house-rules` | The agent applies a skill when it judges it relevant | Open **Customize** in the sidebar, then **Skills** (Source 9, read 2026-10-17) |

Example prompt, the same in all three tools (prefix `/house-rules` in Claude Code or
`$house-rules` in Codex to call it by name):

```text
Make a house rule, "Example rule: soft-deleted rows never appear in list endpoints". Scaffold it with the
skill's script, write the seeded-violation test first and show me it failing, then write the
check until it passes. Run the check on the whole repository, put existing violations in the
baseline, and add the rule to AGENTS.md and CI.
```

The agent runs the script from the installed folder, for example
`python .claude/skills/house-rules/scripts/new_rule.py --id Example --title "..." --root .`. You can
preview what it writes with `--dry-run`. Captured on 2026-10-18 against the course's TeamTrack app from
`uv run python use-in-your-repo/skills/house-rules/scripts/new_rule.py --id Example --title "Soft-deleted rows never appear" --root platform/teamtrack --dry-run`
(run from the checkout root):

```text
would write docs/rules/Example-soft-deleted-rows-never-appear.md
would write checks/check_example_soft_deleted_rows_never_appear.py
would write tests/test_check_example_soft_deleted_rows_never_appear.py
```

## What it costs

The skill runs inside your own agent (Claude Code, Codex, or Cursor), on that tool's model and your
plan or API account with that vendor. The course does not pay for it and has not measured how
many tokens a run uses. `scripts/new_rule.py` makes no model or network calls; the cost is the
agent's own work writing the rule, the check, and the test. The shipharness validators print
`Cost: $0.000000 (no model calls)`.

## Limits

- The script writes stubs. The test stub fails on purpose until the agent writes the seeded
  violation, and the check stub finds nothing until the agent writes `check()`.
- A check is only as exact as the method you pick. A text search misses aliased imports; an `ast`
  walk misses behaviour that only shows at run time, which needs a probe against the running app.
- A baseline lets the rule apply to new code from today. The existing violations stay until
  someone removes them, so open a piece of work for each one.
- A rule that is not wired into CI and the gate before "done" is still only documentation. Step 7
  of `SKILL.md` covers this.
- The tool facts above come from each vendor's documentation as read on 2026-10-17. The course did
  not run the skill inside Claude Code, Codex, or Cursor to confirm them; vendors change these
  pages, so check them again if a skill does not appear.

Related skills: [harness-setup](../harness-setup/README.md) adds the map and docs a rule is linked
from; [skill-template](../skill-template/README.md) is the starting point for a skill of your own.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Agent Skills Specification, <https://agentskills.io/specification>,
  Agent Skills project, n.d.
- Source 3: Building a C compiler with a team of parallel Claudes,
  <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic),
  2026-02-05
- Source 4: Agent Skills Overview, <https://agentskills.io/home>, Agent Skills project, n.d.
- Source 5: How to add skills support to your agent,
  <https://agentskills.io/client-implementation/adding-skills-support.md>, Agent Skills project,
  n.d.
- Source 6: Cursor 2.4 changelog, <https://cursor.com/changelog/2-4>, Cursor, 2026-01-22
- Source 7: Extend Claude with skills, <https://code.claude.com/docs/en/skills>,
  Anthropic (Claude Code docs), n.d.
- Source 8: Build skills, <https://learn.chatgpt.com/docs/build-skills>, OpenAI (Codex docs), n.d.
- Source 9: Agent Skills (Cursor docs), <https://cursor.com/docs/skills>, Cursor, n.d.
- Source 10: skills-ref, the reference validator (source and README),
  <https://github.com/agentskills/agentskills>, Agent Skills project, PyPI package 0.1.1, 2026-01-10
