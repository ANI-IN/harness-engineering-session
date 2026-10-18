# Module 1: Harness Engineering for Coding Agents - Live Demo Guide

[Harness Engineering Demo Guide.pdf](Harness%20Engineering%20Demo%20Guide.pdf) walks through the
five live demos of the class, one command and one screen at a time, with what to say in class at
each step.

## Who it is for

- **Instructors** who run the demos live in class: every step has an instructor note on what to
  point at and what to say, including when a result differs from the guide's.
- **Learners** who want to run the demos on their own copy after class, or watch for the details
  they missed.
- **Teaching assistants** who rehearse a demo before class or help a learner whose screen looks
  different.

## What you need first

- The course repository set up on Windows 11 with WSL (Ubuntu), macOS, or Linux, as
  [setup/](../setup/README.md) describes, with Docker running.
- Your two keys in `.env` next to the Makefile: the OpenAI key and the LangSmith key. Never paste
  a key into a terminal, a document, or a chat.
- `make doctor PURPOSE=pilot` ending in `result: + ready`. Part 0 of the guide walks through it.

## How to follow it

1. Read Part 0, "Before you start": it opens Terminal 1 and Terminal 2, checks your copy, warms the
   images, and starts the console at http://127.0.0.1:8765.
2. Work through the chapters in order: Section 1: Instructions, Section 2: State and sessions,
   Section 3: Scope and sandbox, Section 4: Verification, and the final A/B.
3. Every step reads the same way: where (which terminal or screen), what to type or press, what
   you should see, where to look, what it means, a checkpoint, what to do if it looks different, and
   an instructor note.
4. Each chapter ends with a result summary, the time and cost, and what to say in class.
5. If a live demo cannot run in class, the appendix shows how to replay a recorded run instead. The
   appendix also has a one-page command cheat sheet, a troubleshooting table, and a glossary.

## Time and cost

Measured on 2026-10-18 with the class profile, each demo running alone (two runs per demo):

| Demo | Command | Time | Cost |
|---|---|---|---|
| Section 1 | `make show-1 PURPOSE=pilot` | 3:37 to 4:45 | $0.020 to $0.021 |
| Section 2 | `make show-2 SESSION_BUDGET=12,38 PURPOSE=pilot` | 5:52 to 7:11 | $0.036 to $0.044 |
| Section 3 | `make demo-3 FEATURE=version-checks PURPOSE=pilot` | 5:14 to 8:24 | $0.050 to $0.056 |
| Section 4 | `make show-4 PURPOSE=pilot` | 5:32 to 8:02 | $0.026 to $0.028 |
| Final A/B | `make final FEATURES=bulk-close PURPOSE=pilot` | 7:25 to 9:10 | $0.038 to $0.042 |

All five demos together cost about $0.18 in model calls. Setup adds about 7 minutes the first time
(`make warm` builds the images) and nothing after that. Following the whole guide, reading every
screen, takes about two hours.

## The slides

The class deck that goes with these demos is in [slides/](../slides/README.md).

## Build the PDF

For maintainers. From the repository root, in the Ubuntu terminal:

```bash
uv run python guide/source/build_pdf.py --images
```

`--images` first copies the screenshots from `~/guide-work/images/` into `images/`; leave it out to
build from the images already here. `--desktop-copy` followed by a folder also copies the PDF
there. The build makes no model calls and starts no container; it needs `markdown-it-py` and
Playwright's Chromium (`uv run playwright install chromium`). The Markdown conventions are in
[source/CONVENTIONS.md](source/CONVENTIONS.md).

| Path | What it holds |
|---|---|
| `source/intro.md` | The short introduction after the contents |
| `part0.md` | Part 0: Before you start |
| `chapters/` | One chapter per demo |
| `appendix.md` | Cheat sheet, troubleshooting, glossary, and the replay fallback |
| `images/` | Screenshots and terminal images, copied in by the build |
| `source/` | The build script, the page template, the styles, and the conventions |
