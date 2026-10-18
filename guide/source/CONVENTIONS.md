# Live Demo Guide: Markdown conventions

This page lists the Markdown that `build_pdf.py` turns into the PDF's boxes and layout. Write
plain Markdown otherwise. `docs/STYLE.md` still applies to every page here, and
`platform/scripts/check_style.py --strict` and `platform/scripts/lint_prose.py` check these files.

## Files and order

The PDF is, in order: the cover and the contents (built by the script), `source/intro.md`,
`part0.md`, `chapters/1-*.md` to `chapters/5-*.md`, and `appendix.md`. Each file has one H1. A
chapter's H1 is `# Chapter N: title`; the text before the colon becomes the small label above the
title in the coloured band, and the whole H1 becomes the running header of its pages. The H1 and
every H2 go into the contents with their page numbers. H3 headings do not.

## Steps

A step starts with `### Step N: short action`. Everything up to the next H1, H2 or H3 belongs to
the step. The step title is always kept on one page with the step's first block, so a title never
stands alone at the foot of a page. A step may break between blocks, but never inside a
screenshot, a command, or a box.

The field lines are paragraphs that start with a bold label, in this order:

- `**Where:**`, `**Type:**`, `**You should see:**`, `**Look at:**`, `**What it means:**`.

The label prints as a small coloured caption. Any other bold start is ordinary text.

## Boxes

A blockquote whose first line is one of these markers becomes a box. A line that holds "→" starts
on a new line, so you can write one "cause → fix" per line; other wrapped lines flow on as one
paragraph. A list works too.

| Marker | Box |
|---|---|
| `> [!CHECKPOINT]` | Green, titled "✓ Checkpoint" |
| `> [!IFDIFFERENT]` | Grey, titled "If it looks different" |
| `> [!INSTRUCTOR]` | Harness blue, titled "Instructor note" |
| `> [!WARNING]` | Amber, titled "Warning" |
| `> [!NOTE]` | White with a grey rule, titled "Note" |

An unknown marker prints as an ordinary quote, and the build lists it as a warning.

## Commands and output

- A fenced `bash` block is a command box: dark, monospaced, with a "copy" label. One command per
  line, no prompt sign.
- A fenced `text` block is an output box: light grey, monospaced, labelled "Output". Keep it to at
  most 12 lines; use a terminal image for longer output.

## Screenshots and callouts

An image on its own line, then one blank line, then an italic caption line, then (optionally) a
numbered list, become one figure kept together on one page. The image prints at the full text
width. The list numbers print in blue circles, like the circles the tooling draws, and must match the numbers on the image.

The check needs the blank line between the image and the caption (`check_style.py` SC07), and it
reads image paths from the page's own folder (SC06). So a chapter in `chapters/` writes
`../images/s1/screen-1.png`, and `part0.md` and `appendix.md` write `images/setup/x.png`. The
build copies `~/guide-work/images/` into `guide/images/` first, so the repository holds
the images and SC06 checks that each one exists. An image that is not there yet prints as an
orange placeholder box, and the build lists it.

## Run ids

This guide follows one recorded run per demo, so a reader types and reads run ids. In files under
`guide/` only, a run id such as `ab-20261018-045459-2efbfc` may stand in a code span or
a fenced block: `make replay RUN=ab-20261018-045459-2efbfc`, or a terminal excerpt. In plain prose
it still fails SC08. Everywhere else in the repository, run ids stay in the evidence pages.

## Build

From the repository root, in WSL:

```bash
uv run python guide/source/build_pdf.py --images
```

It prints the page count, then one line per missing source file, missing image, or unknown box.
