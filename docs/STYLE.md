# Course style guide

This page is for anyone who writes or edits a page in this course. Every public page follows it.
It has two parts: the rules that apply to every page, and one template per document type.

Two scripts check the parts that a machine can check. Run both before you commit:

```bash
make check-style
uv run python platform/scripts/lint_prose.py
```

`make check-style` runs `platform/scripts/check_style.py`. It checks placeholders, empty code
blocks, images and captions, ids and bare codes outside the evidence pages, names without their
full form on first mention, sources named without a link, empty links, the Sources list, table width, the title line, and internal phrases; any of these is an error
and fails the check. Length limits, template headings,
the scenario label, and the glossary box are printed as warnings; they fail only with
`make check-style CHECK_STYLE_OPTS=--strict`. `uv run python platform/scripts/check_style.py
--list-checks` lists every check. `lint_prose.py` checks banned words and emoji. Both must report 0
errors. Everything else on this page is checked by a reviewer who reads the page as a first-time
engineer.

If a line must break a rule, for example to quote real output, end it with
`<!-- check-style: allow SC08 quoted terminal output -->`: the check id, then the reason. A marker on its own
line, right before a fenced block, covers the whole block.

Public course files are: `README.md`, `setup/`, the section folders `section-1-*` to `section-4-*`,
`final-project/`, `slides/README.md`, `use-in-your-repo/`, and `docs/`. Every Markdown page in
them is checked, including the pages under an assignment's `starter/` and `solution/` folders. The
assignment graders and hidden test cases are not part of the course text. Files outside that list
are not part of the course text either. The class deck in `slides/` is a PowerPoint file and is
not checked.

Agent files are the files an agent reads, not a learner: `section-N-*/demo/harness/`,
`final-project/harness/` (except its `README.md`), Assignment 1's
instruction trees (`instructions/` and `original/` under `starter/` and `solution/`), skills
(`use-in-your-repo/skills/`, a `skill/<name>/` folder in an assignment, any `.agents/skills/` or
`.claude/skills/` folder), `use-in-your-repo/kit/templates/`, and `use-in-your-repo/kit/examples/*/filled/`.
They follow their own format; only the image rules and the finding-id rule apply to them, with
these exceptions, which follow every label rule of rule 5: the skills in `use-in-your-repo/skills/`
and the kit templates (copied into learners' repositories; their scripts and other text files are
checked for ids too), a `skill/<name>/` folder in an assignment, and the harness docs that ship:
the `.md` files under `section-N-*/demo/harness/` and `final-project/harness/`. Since 2026-10-18 the
TeamTrack harness the agent reads uses the same names as the pages (see the disclosure in
`docs/evidence/general.md`). Assignment 1's instruction trees keep their own wording, because a
grader reads them.

Folder rules (checked on a full run): every `section-N-*/` folder has `README.md`, `concepts.md`,
`session-notes.md`, `demo/` (`README.md`, `run.sh`, `walkthrough.md`, `harness/`, `expected/`),
`assignment/` (`README.md`, `SPEC.md`, `starter/`, `solution/SOLUTION.md`), `post-class-reading/`,
and `diagrams/README.md` once it has a `diagrams/` folder (SC19). `final-project/` has `README.md`,
`run.sh`, `tasks/`, `harness/`, `walkthrough.md`, `expected/`, `your-repo/`, and `CHECKLIST.md`
(SC19). Every `.png` or `.svg` in a `diagrams/` folder has an `.excalidraw` source with the same name
next to it (SC20).

---

## Rules for every page

### 1. Title line

Every `README.md` and every setup page starts with the module title as its only H1:

```markdown
# Module 1: Harness Engineering for Coding Agents
```

The root README uses exactly that line. Other READMEs and setup pages add the page name after a
spaced hyphen:

```markdown
# Module 1: Harness Engineering for Coding Agents - Section 1: Instructions
# Module 1: Harness Engineering for Coding Agents - Setup on Windows
```

Other pages (`concepts.md`, `walkthrough.md`, `SPEC.md`, and so on) have one H1 with their own name.

### 2. Problem first

Pages that teach (root README, section READMEs, `concepts.md`, demo READMEs, assignment READMEs,
the final project) open with `## The problem`. Its first paragraph starts with the label
**Illustrative scenario.** and tells a short work story an engineer recognises. The root
README tells its story without the label. Each section uses
its own failure:

| Section | The failure in the story |
|---|---|
| Section 1: Instructions | Agent copies a tenant leak from legacy code |
| Section 2: State and sessions | A migration is rewritten across sessions |
| Section 3: Scope and sandbox | Out-of-scope edits break old features |
| Section 4: Verification | Agent says done when it is not |

The scenario contains no numbers. It is a story, not a measurement. After the scenario come: why it
happens (cited), how the harness layer fixes it (and that the course measures whether it helps),
and then the how-to.

### 3. Plain short sentences

- One idea per sentence. Aim for 25 words or fewer.
- Write to the reader as "you". Use the active voice and the present tense.
- Say what happens, not what something "allows" or "enables".
- Use the source's own words for its ideas: AGENTS.md is a "map" or "table of contents"; the
  feature list field is `passes`; say "existing tests keep passing" and "grading criteria".
- Report results as counts ("0 of 3 runs"), never as percentages.
- Pages are read on any day. For the class or a run, write "today", "in class", "this session", or
  "this run", never "tonight"; `lint_prose.py` flags it. <!-- lint-prose: allow -->
- Short paragraphs: at most 5 lines.
- Standard terms (API, CI, HTTP, JSON, SQL, ETag) need no explanation. Spell out any less common
  term on first use on each page, in a few plain words: "mutant (a copy of the code with one small
  bug planted on purpose)". Every such term is in the [glossary](glossary.md), one line each, in
  alphabetical order.

### 4. One glossary box per page

Each page defines the course terms it uses once, in one glossary box placed at the end of
`## The problem`, after the scenario (or right after the H1 on pages without that section). Define a term in the box, then
use it without explaining it again. Do not write sentences about labels, such as "this code is a
course label, not a source term". If a code such as `R1` appears on screen or in quoted output,
put it in a code span and explain it once in plain words right there: "`F4` (Feature 4: Version
checks on issue edits)".

```markdown
> **Terms on this page**
>
> - **Harness**: the files and code around the agent that decide what it sees and what it may do.
> - **Bare arm**: an agent run that gets the ticket and the repository, and no harness.
> - **Harness arm**: the same run with the harness turned on.
> - **Referee**: the program that scores each run after the agent stops.
```

Use the same wording for a term on every page. The standard wordings are at the end of this page.

### 5. Evidence stays in the evidence pages, and names follow one format

Run ids, A/B ids, source ids (`A1` to `A7`, `B1` to `B14`), finding ids (`F-a-` or `F-b-` and a
number), and commit hashes appear only in the evidence pages: `docs/evidence.md` (the index) and the
files under `docs/evidence/`, one per section (`s1.md` to `s4.md`, `final.md`, and `general.md`).

Features, house rules, sections, assignments, and test filters are named "<Kind> N: <name>". The
first mention on a page is the full form with the exact name; later
mentions use the short form "Feature 4", "House rule 1" (SC22). Plurals such as "Sections 1 to 4"
are not mentions. The exact names:

- Feature 1: Org-wide issue search; Feature 2: Comments on issues; Feature 3: Safe retries for
  issue creation; Feature 4: Version checks on issue edits; Feature 5: Bulk close; Feature 6:
  Watchers; Feature 7: Labels.
- House rule 1: Tenant isolation; House rule 2: Roles; House rule 3: API conventions; House rule 4:
  Safe retries; House rule 5: Audit log; House rule 6: Layering; House rule 7: Migrations; House
  rule 8: Deleted issues stay hidden.
- Section 1: Instructions; Section 2: State and sessions; Section 3: Scope and sandbox; Section 4:
  Verification. Assignment N has the name of Section N.
- Filter 1: Builds and collects; Filter 2: Passes five runs; Filter 3: Adds coverage or catches a
  mutant; Filter 4: Real assertions; Filter 5: No source changes; Filter 6: No duplicate tests.

The same names are in `shipharness.datasets.names`, which the console and the CLI use, and a test
keeps the checker's copy equal to it.

- Never a bare `F1` to `F7`, `R1` to `R8`, `S1` to `S4`, `A1` to `A4`, or a source id in prose,
  headings, link text, tables, or HTML comments (SC21). Code spans, fenced code, and commands are
  identifiers and are not read: `make demo-3 FEATURE=version-checks`, the file `f1.md`, the slide
  anchor `S4:gate`.
- Commands use the readable aliases: `FEATURE=version-checks`, `FEATURE=safe-retries` (Feature 3;
  `idempotent-create` and `F3` still work), `make final FEATURES=watchers,bulk-close`.
- Other codes a learner can see (checkpoint tags such as `m1-s1-start`, task ids such as `F1-trap`,
  mutant ids) go in a code span with a plain-words explanation where they appear; leave them out
  where they are not needed.
- Sources: in prose, cite the source by its linked title, such as
  [Harness engineering](https://openai.com/index/harness-engineering/). Every mention of a source's
  title is a link to it; after the first citation you may write "Source 2" (SC23). A page that
  cites a source ends with a `## Sources` list, numbered per page in the order the page first cites
  each source, one entry per source in exactly this form (SC25):

  ```markdown
  ## Sources

  - Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
  ```

  A long entry may wrap onto an indented line. That H2 may close any template; on a concepts page it
  comes after `## Further reading`. URLs, titles, authors, and dates come from the course's source
  register (the Sources sections of the evidence pages), never from memory.
- A link always has text and a target: no `[text]()`, no `[link]`, no malformed URL (SC24).
- Every relative link resolves: the file or folder exists, and an anchor into a Markdown page
  matches one of its headings or HTML ids (SC30; images are SC06). Two exceptions: links to
  `docs/REFERENCES.md`, which the release build writes, and links in the kit templates
  (`use-in-your-repo/kit/templates/`, `use-in-your-repo/templates/`, and a skill's
  `assets/templates/`), which point into the learner's own repository once copied there.
- Where a page relies on a finding, keep the claim and link to the section of the evidence page.
- Captured terminal output (`expected/*.txt`, `captured/*.txt`) is real output: it is not edited,
  and the check does not read it. A line a program parses (such as a row of Assignment 1's report,
  read by its `check.py`) keeps its token with an allow marker that says so.
- The skills and the kit templates carry no source, finding, run, or assignment ids at all.

Good:

```markdown
Agents copy patterns that already exist in the repository, even poor ones
([Harness engineering](https://openai.com/index/harness-engineering/)).
In our test runs, no arm leaked data on this ticket ([evidence](../docs/evidence/s1.md)).
In Section 1: Instructions you hand in Assignment 1: Instructions. House rule 1: Tenant isolation
says another org's issue answers 404; Section 1 checks House rule 1 on every endpoint.
```

Not this:

```markdown
A1 reports that agents copy patterns (A1, F-a-NN); see run ab-20261016-181736-a07558.
In S1 you hand in A1. Section 1 checks R1, the tenant rule.
```

### 6. No internal language

These words come from how the course was built. Learners do not know them. Never use them:

| Do not write | Write instead |
|---|---|
| "owner scope", "the owner's", "brief", "lead" (a role) | Say who does it: "you", "the instructor" |
| "class host" | "the instructor's machine" |
| "build repository", "build branch" | Nothing: learners see only this repository |
| "not a make target in this release", "this release" | The command to run instead, or nothing |
| "pilot run 3" (no context) | "a test run before class", with an evidence link |
| `PENDING`, `CAPTURE` markers | Capture the real output, or cut the sentence |
| "M6", "M8" (milestone codes) | Nothing |
| "generated when released", "(private)" | Nothing; link the page that exists |

### 7. No invented numbers

Every number comes from one of two places: a file in this repository (name the file, for example
`platform/config/prices.toml` for model prices), or a real run listed in an evidence page. Do not
estimate times or costs. Caps are stated as caps: "at most `MAX_RUN_COST_USD` per arm (set in
`.env.example`)", not "about 20 cents". If a number is missing, run the command and capture it.
Never commit a placeholder.

### 8. One "your output will differ" note per page

A page with captured output or screenshots has exactly one note, placed right before the first
captured block or image:

```markdown
> Your output will differ: run times, ids, and the agent's wording change on every run.
```

Do not repeat it under each block or caption. Pages without captured output have none.

### 9. Consistent headings

- One H1 per page. H2 headings are exactly the ones in the page's template, in that order, plus
  an optional last `## Sources` (rule 5).
- H3 headings are free. Do not go deeper than H3.
- Sentence case ("What the result means"), no numbers in headings. Setup steps are the one
  exception: "Step 3: Install Docker Engine".

### 10. Tables

At most 4 columns. Keep each cell short: a few words, a count, or a command. No ids in tables
(they go in the evidence pages). If a table needs more columns, split it or use a list.

### 11. Images with captions

Screenshots are real, from real runs, and stored in the repository: section screenshots in
`section-N-*/demo/expected/`, root README screenshots in `docs/images/`. File names are lowercase with
hyphens (`screen-1-minute-4.png`). Each image stands on its own line with alt text, then a blank
line, then an italic caption that says what to notice. Dates and run ids for captures go in the
captures table of the section's evidence page (`docs/evidence/s1.md` and so on), not in the
caption.

```markdown
![Console screen 1 at minute 4, with the primary verdict PASS](expected/screen-1-minute-4.png)

*At minute 4 the primary verdict is ready, while the secondary checks still run.*
```

Alt text says what the image shows, for a reader who cannot see it: never empty, never the file
name, never one word such as "image" or "screenshot" (SC26). Colour never carries meaning alone:
say it in words too ("the blocked file", "a filled dot passed"). The one remote image allowed is
the CI status badge at the top of the root README; it needs no caption.

Link official pages instead of pasting screenshots of other products.

### 12. Code blocks

- Commands go in `bash` blocks. Captured output goes in `text` blocks. A diagram is either a
  `mermaid` block (small and labelled) or an Excalidraw SVG from a `diagrams/` folder, with its
  `.excalidraw` source next to it. An SVG is an image, so rule 11 applies: alt text, a blank line,
  an italic caption.
- Code excerpts come from real files. The first line is a comment with the path and line numbers.
  At most 40 lines per excerpt.
- Never leave a block empty, and never leave a block whose only content is a comment. If the
  output is not captured yet, the page is not ready.
- Explain any placeholder in a command (such as a key you paste) in the sentence before it.

```python
# platform/teamtrack/app/repositories/issues.py (lines 53-55)
def list_all_legacy(session: Session, offset: int, limit: int) -> list[Issue]:
    """LEGACY (used only by /v1/issues). Not tenant-scoped: do not use or copy this function."""
    return list(session.scalars(select(Issue).order_by(Issue.id).offset(offset).limit(limit)))
```

### 13. Links

Use relative links between course pages. Clone commands use the real repository URL.

---

## Templates

Each template gives the file, the length limit, the heading skeleton, and a short good example.
The skeletons are the exact H2 headings that `check_style.py` expects; text in angle brackets is
what you replace.

### Root README (`README.md`)

Limit: 250 lines. The make targets, variables, and caps go in `docs/reference.md`. Run ids, finding
ids, and provenance go in the evidence pages under `docs/evidence/`.

```markdown skeleton:root-readme
# Module 1: Harness Engineering for Coding Agents
<one sentence: what this module teaches>
## The problem
## Why it happens
## The harness
## The class plan
## What we measured
## Quick start
## Where next
```

- **The problem**: one illustrative scenario that covers the whole module.
- **The harness**: one diagram of the four layers around the agent, two sentences each.
- **The class plan**: the four sections and the final, as a table (section, what you see, time).
- **What we measured**: one small table, an honest summary, and a link to `docs/evidence.md`.
- **Quick start**: exactly 5 commands, then a link to `setup/` for a first install.
- **Where next**: links to Section 1, setup, and `use-in-your-repo/`.

Good example (What we measured):

```markdown
In our test runs the harness arm did not beat the bare arm on any of the four tickets. The class
shows each layer at work and measures it live. Details: [evidence](docs/evidence.md).
```

### Section README (`section-N-*/README.md`)

Limit: 120 lines.

```markdown skeleton:section-readme
# Module 1: Harness Engineering for Coding Agents - Section <N>: <name>
## The problem
## Why it happens
## How this section fixes it
## How to work through this section
## Where next
```

- **How this section fixes it**: the harness layer in two or three sentences, and what the course
  measures to see whether it helps.
- **How to work through this section**: a table of the parts in order (concepts, demo, assignment,
  reading, session notes), with what each gives you.

Good example (The problem):

```markdown
**Illustrative scenario.** You ask an agent to add org-wide issue search to a multi-tenant app. It
finds an old endpoint that already lists issues, copies its query, and the tests pass. The copied
query has no tenant filter, so a user at one company can now see another company's issues. The
rule against copying that code exists, near the end of a long handbook the agent never opened.
```

### Concepts (`section-N-*/concepts.md`)

Limit: fits 15 minutes live, so at most about 1,800 words, plus diagrams. Code blocks, Mermaid
blocks, and image lines do not count toward the words; captions do.

```markdown skeleton:concepts
# Section <N> concepts: <topic>
## The problem
## The idea in one sentence
## How it works
## How shipharness does it
## What we measured
## When it helps, and when it does not
## Key takeaways
## Check your understanding
## Further reading
```

- **The problem**: the work story, labelled "Illustrative scenario".
- **The idea in one sentence**: one sentence. No list.
- **How it works**: one concept diagram and one before/after example.
- **How shipharness does it**: one short code excerpt (rule 12) and what it does.
- **What we measured**: one small table, no ids, with an evidence link.
- **When it helps, and when it does not**: two short lists.
- **Key takeaways**: exactly 3 bullets.
- **Check your understanding**: 3 to 5 questions, each answer in a `<details>` block.
- **Further reading**: links to this section's post-class reading.

Good example (What we measured):

```markdown
| Measure | Bare arm | Harness arm |
|---|---|---|
| Runs that leaked another tenant's data | 0 of 3 | 0 of 3 |
| Hidden tests passed, each run | 52 of 52 | 52 of 52 |

No measurable difference on this ticket with this model ([evidence](../docs/evidence/s1.md)).
```

### Demo folder (`section-N-*/demo/`)

| File | What it holds |
|---|---|
| `run.sh` | The one command that runs the demo |
| `harness/` | The actual files this section gives the agent |
| `walkthrough.md` | The 30 to 40 lines of code that matter, explained |
| `expected/` | Real output and screenshots from a real run |
| `README.md` | The page learners follow |

**`run.sh`**: starts with a comment block that says what it runs, what it costs at most (the caps
in `.env.example`), and how long it takes (from a measured run). It calls the same make target the
README shows, uses `set -euo pipefail`, and exits non-zero on failure.

```bash
#!/usr/bin/env bash
# Section 1 demo: the harness arm builds org-wide issue search, then the referee scores it.
# Runs: make show-1. Cost: at most MAX_RUN_COST_USD (set in .env.example).
set -euo pipefail
cd "$(dirname "$0")/../.."
make show-1
```

**`harness/`**: exact copies of the files the agent receives in this section, with no course
text added. A check keeps them identical to the files the harness really places.

**`walkthrough.md`**: 30 to 40 lines of real code in total, split into short excerpts.

```markdown skeleton:walkthrough
# Demo <N> walkthrough: <name>
## What this code does
## The code, explained
## If you copy this into your repo
```

Under "The code, explained", one H3 per excerpt (`### <file>, lines <a>-<b>`), then the excerpt,
then a few sentences on the lines that matter.

**`expected/`**: real captured output (`terminal.txt`) and screenshots, named by screen and minute.
Where and when each was captured is listed in the section's evidence page.

**`README.md`**: limit 250 lines. "What you'll see" says what the run shows; "What to watch" goes
screen by screen, with no minute-by-minute replay of a past run. "Run it" ends with a short
`### Files and links` list: `run.sh`, `walkthrough.md`, `harness/`, `expected/` (the fallback when
a run cannot be made), the section's evidence page (`../../docs/evidence/sN.md`), and the console at
`http://127.0.0.1:8765`.

```markdown skeleton:demo-readme
# Module 1: Harness Engineering for Coding Agents - Demo <N>: <name>
## The problem
## What you'll see
## Run it
## What to watch
## What the result means
## If it fails
```

### Final project README (`final-project/README.md`)

The demo README skeleton, with one more section at the end:

```markdown skeleton:final-project
# Module 1: Harness Engineering for Coding Agents - Demo <N>: <name>
## The problem
## What you'll see
## Run it
## What to watch
## What the result means
## If it fails

## Use it on your own repository
```

- **What you'll see**: two or three sentences and one screenshot.
- **Run it**: the commands, each followed by its real captured output.
- **What to watch**: a short table (minute, screen, what appears) and the screenshots.
- **What the result means**: what PASS and FAIL tell you, and what they cannot tell you.
- **If it fails**: a table of symptom, cause, and fix.

Good example (What to watch):

```markdown
| Minute | Screen | What appears |
|---|---|---|
| 1 | 1 | The agent patches the service, the route, and the tests |
| 4 | 1 | The primary verdict: PASS, no new tenant leak |
| 10 | 1 | The full verdict: hidden tests and mutants scored |
```

### Assignment folder (`section-N-*/assignment/`)

| Path | What it holds |
|---|---|
| `README.md` | The assignment page |
| `SPEC.md` | The detailed requirements |
| `starter/` | The files the learner works in |
| `solution/` | The complete reference solution and `SOLUTION.md` |

**`README.md`**: limit 250 lines. The line right under the H1 is:

```markdown
Try it yourself first. The full solution is in [./solution/](solution/) with a step-by-step walkthrough.
```

```markdown skeleton:assignment-readme
# Module 1: Harness Engineering for Coding Agents - Assignment <N>: <name>
## The problem
## What you'll build
## Step by step
## Grading criteria (100 points)
## Solution walkthrough
```

- **What you'll build**: one diagram and one paragraph.
- **Step by step**: numbered steps; each says what to do and how to check it.
- **Grading criteria (100 points)**: a table of criterion, points, and how it is checked.
- **Solution walkthrough**: a short summary and a link to `solution/SOLUTION.md`.

**`SPEC.md`**: everything detailed that used to crowd the README.

```markdown skeleton:spec
# Assignment <N> specification: <name>
## Inputs
## Files you must produce
## Requirements
## Self-check
## Evidence to hand in
## Limits
```

Requirements are numbered and testable ("The checker exits 1 when a skill has no description").

**`starter/`**: the learner's working files, with a short `README.md` that says which files to edit.

**`solution/`**: the complete working code and files, side by side with `starter/`. It also holds
the captured self-check output (all PASS), one real captured live run, and the grader score
(100/100). The grader code and hidden grader tests are not in the course files.

```markdown skeleton:solution
# Assignment <N> solution: <name>
## The approach, step by step
## Design choices and why
## Alternatives considered
## Common mistakes this avoids
## Run and verify it
## Evidence
```

Good example (Design choices and why):

```markdown
The map stays short and points to one document per topic. A long map would bring back the
problem this assignment fixes: rules the agent never reaches because they sit in a large file.
```

### Post-class reading (`section-N-*/post-class-reading/`)

The folder has a `README.md` index and one file per reading.

```markdown skeleton:reading-index
# Module 1: Harness Engineering for Coding Agents - Section <N> reading list
## Readings
## How to use these
```

The Readings table has three columns: reading (linked), reading time, and why read it.

Each reading file:

```markdown skeleton:reading
# <title of the source>
Reading time: about <N> minutes.
Source: <author, title, date, link>
## Why it matters
## Three key ideas
## Apply it to your repo
```

- **Reading time**: the source's word count divided by 200, rounded up to 5 minutes.
- **Three key ideas**: exactly 3, each in plain words, each 2 to 4 sentences.
- **Apply it to your repo**: concrete steps the reader can do this week.

Good example (one key idea):

```markdown
1. **The agent only knows what is in its context.** A rule in a chat thread or in someone's head
   does not exist for the agent. Put the rule in the repository, then make sure the agent reaches
   it while it works.
```

### Session notes (`section-N-*/session-notes.md`)

Limit: 150 lines. Write them from the real class run. Before the class has run, the page shows the
reference run from the section's evidence page.

```markdown skeleton:session-notes
# Section <N> session notes: <topic>
## What we showed
## Key ideas
## What the result showed
## Questions from class
## What to try next
```

Good example (Questions from class):

```markdown
**Why not put every rule in AGENTS.md?** A long file pushes the task out of focus and goes stale.
Keep the map short and point to documents the agent opens when it needs them.
```

### Setup pages (`setup/`)

`setup/README.md` is the index. There is one page per system: `setup/windows.md` (WSL2, Ubuntu, and
Docker Engine), `setup/macos.md`, and `setup/linux.md`. They assume nothing is installed.
`setup/pre-class.md` is the short list of what to finish before class day; it has no template, but
it starts with the module title like every setup page.

```markdown skeleton:setup-index
# Module 1: Harness Engineering for Coding Agents - Setup
## What you will install
## Pick your system
## Get help
```

```markdown skeleton:setup-os
# Module 1: Harness Engineering for Coding Agents - Setup on <system>
## Before you start
## Steps
## Common errors
## You're ready
```

Steps, in this order (skip the ones that do not apply to the system): OpenAI account and API key;
add credit (Build tier); LangSmith account and key (no card); WSL and Ubuntu; Docker; git; uv;
make; clone the repository; `.env`; `make doctor`; `make warm`; the first live demo.

Each step is an H3 under "Steps" and has the same five parts, in order:

```markdown
### Step 6: Install git

**Why.** You need git to clone the course repository.

**Do this.**

    sudo apt-get update && sudo apt-get install -y git

**You should see.** The install ends without an error line.

**Check it worked.** `git --version` prints a version number.

**If it fails.** If apt cannot find the package, run `sudo apt-get update` again, then retry.
```

In a real page the command goes in a `bash` block and the captured output in a `text` block.

### Instructor guide (`docs/instructor-guide.md`)

The first section is a one-page class-day cheat sheet: at most 60 lines. Details come after it.

```markdown skeleton:instructor-guide
# Instructor guide
## Class-day cheat sheet
## The day before
## Thirty minutes before
## Section by section
## If something breaks
## After class
```

The cheat sheet holds: the timeline (a table of time, what happens, and the command), the console
keys, the three commands to run if a demo stalls, and who to call. Nothing else.

Good example (cheat sheet row):

```markdown
| Time | What happens | Command |
|---|---|---|
| 0:13 | Launch the Section 1 demo | `make show-1` |
```

### Reference (`docs/reference.md`)

Everything a learner looks up but does not read in order.

```markdown skeleton:reference
# Reference
## Make targets
## Settings and variables
## Caps and limits
## Folders
```

Each table names the file a value comes from, for example "Per-run cap: `MAX_RUN_COST_USD` in
`.env.example`".

### Evidence (`docs/evidence.md` and `docs/evidence/`)

The evidence pages are the only pages that hold run ids, A/B ids, finding ids, commit hashes, and
capture provenance. `docs/evidence.md` is the index: one line per evidence page, with a link.
Each evidence page covers one part of the course: `docs/evidence/s1.md` to `s4.md` for the
sections, `final.md` for the final project, and `general.md` for the root README and anything
shared. Other pages link to the evidence page of their section.

Each page under `docs/evidence/`:

```markdown skeleton:evidence
# Evidence: <section name>
## How to use this page
## Results
## Captures
## Sources and findings
## Commits and tags
```

- **Results**: each row gives the claim, the runs, and the ids.
- **Captures**: each screenshot and captured output: file, date, run id.
- **Sources and findings**: finding ids with the short source name used in the main text.

Good example (a Results row):

```markdown
| Claim | Runs | A/B ids |
|---|---|---|
| No new tenant leak in either arm, trap ticket, low effort | 3 per arm | ab-20261016-232842-b372c2, ... |
```

### Other pages

`final-project/README.md` follows the demo README template, then ends with
`## Use it on your own repository`. There is no grader for the final project. `use-in-your-repo/README.md` follows the section README template. The kit templates, the
filled examples, and the skills under `use-in-your-repo/` are agent files (see the top of this page)
and follow the agent file format, not this guide.

---

## Standard wordings

Use these definitions in glossary boxes, word for word.

| Term | Definition |
|---|---|
| Harness | The files and code around the agent that decide what it sees and may do |
| Harness layer | One part of the harness: instructions, state, scope, or verification |
| Bare arm | An agent run with the ticket and the repository, and no harness |
| Harness arm | The same run with the harness turned on |
| A/B | Bare arm and harness arm on the same ticket, scored the same way |
| Referee | The program that scores each run after the agent stops |
| Primary verdict | The referee's answer to the one question the section asks |
| Ticket | The task the agent gets, written like a work ticket |
| Console | The browser page that shows a run live, on five screens |
