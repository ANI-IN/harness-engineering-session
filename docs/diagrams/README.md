# Module 1: Harness Engineering for Coding Agents - Diagrams

This folder holds the diagrams for the opening and the close of the course: the agent loop, the
harness around it, the A/B, and the results. Each section has its own `diagrams/` folder for the
diagrams that only it uses.

## How to read these files

Every diagram has three files with the same name:

| File | What it is for |
|---|---|
| `.excalidraw` | The source. Open it at excalidraw.com to edit it |
| `.png` | A render at 2x scale, for slides |
| `.svg` | A render with the font embedded, for pages on GitHub |

Some diagrams are built up on slides one step at a time. They also have step frames, named
`-step-1`, `-step-2`, and so on. Each frame adds one element, and every frame has the same size, so
the picture does not jump between slides. The file without a step number is the full diagram, the
same as the last step.

The colours mean the same thing in every diagram:

| Colour | Meaning |
|---|---|
| Grey `#78909C` | The bare arm |
| Blue `#3896D2` | The harness arm, and the parts of the harness |
| Amber `#FFAB40` | What to notice: a done claim, a question |
| Red `#E46962` | A "no": a block, a revert, a failure |
| Dark `#212121` | Every label, and everything else |

Every diagram sits on a light rounded panel (`#F0F3F6`), so it reads on the navy slide
background (`#324158`) and on GitHub in light or dark mode. Each panel is a fixed canvas: 1920 by
1080 for the 16:9 diagrams, placed at 80% of the slide width (1440 by 1080 for 4:3, placed at
60%). At that size every label shows at 20 px or more on a 1080p slide.

In the results charts, each dot is one run: a filled dot passed, a hollow dot failed.

Colour is never the only signal. Each diagram also names its parts in words, such as "Bare arm",
"Harness arm", "BLOCKED", and "REVERTED", and the alt text and caption of each diagram say what it
shows. You do not need to tell the colours apart to read a diagram.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Harness layer**: One part of the harness: instructions, state, scope, or verification.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **A/B**: Bare arm and harness arm on the same ticket, scored the same way.
> - **Referee**: The program that scores each run after the agent stops.
> - **Primary verdict**: The referee's answer to the one question the section asks.
> - **Ticket**: The task the agent gets, written like a work ticket.

## The diagrams

### The agent loop

![The agent loop: ticket, model, tool call, result, repository, and the done claim](./agent-loop.svg)

*The loop has no check of its own: the phase ends when the agent calls finish with claim done.*

- **What it teaches**: an agent is a model that calls tools in a loop, one model call per turn,
  until it says it is done.
- **Slide topic**: the agent loop, in the opening.
- **Files**: `agent-loop`, with step frames `agent-loop-step-1` to `agent-loop-step-5`.
- **Source**: the tools and `finish` in `platform/src/shipharness/runner/prompts.py`.

### The harness around the loop

![The loop in the centre, with instructions, state, scope, verification, and the sandbox around it](./harness-around-loop.svg)

*Each layer acts at one point of the loop; the sandbox is the same for both arms.*

- **What it teaches**: the four harness layers and the sandbox, and where each one acts on the loop.
- **Slide topic**: the harness, in the opening.
- **Files**: `harness-around-loop`, with step frames `harness-around-loop-step-1` to
  `harness-around-loop-step-6`.
- **Source**: the layer names in `platform/src/shipharness/harness/decisions.py` and
  `platform/sandbox/README.md`.

### Four stories, four causes, four layers

![Three columns, one row per gap: four failure stories, their causes, and the section whose layer answers each](./stories-causes-layers.svg)

*Each section starts from one failure story and ends with the layer that answers it.*

- **What it teaches**: the plan of the course, one row per section.
- **Slide topic**: the class plan, in the opening.
- **Files**: `stories-causes-layers`.
- **Source**: the failure table in `docs/STYLE.md` and the four `concepts.md` pages.

### The TeamTrack data model

![The seven TeamTrack tables: orgs on the left, five tables with org_id inside a dashed box, project_members below it](./teamtrack-data-model.svg)

*Every table inside the dashed box carries org_id; project_members reaches its org through a project.*

- **What it teaches**: the app every ticket changes, and House rule 1: Tenant isolation, which the agent must keep.
- **Slide topic**: meet TeamTrack, in the opening.
- **Files**: `teamtrack-data-model`.
- **Source**: `platform/teamtrack/app/db/models.py` (the seven tables).

### One ticket, two arms, one referee

![One ticket split into a bare arm and a harness arm, both scored by one referee](./ab-referee.svg)

*Only the harness differs between the arms; one A/B gives one dot per arm.*

- **What it teaches**: how the course measures a layer.
- **Slide topic**: how we measure, in the opening.
- **Files**: `ab-referee`, with step frames `ab-referee-step-1` to `ab-referee-step-6`.
- **Source**: the A/B and referee definitions in `docs/STYLE.md`.

### Optimistic concurrency

![Two tabs read ETag 1; the first save gets ETag 2, the second save with If-Match 1 gets 412](./optimistic-concurrency.svg)

*The second save names a version that is no longer current, so it gets 412 and changes nothing.*

- **What it teaches**: the ticket for Feature 4: Version checks on issue edits, which
  Section 3: Scope and sandbox and Section 4: Verification both run.
- **Slide topic**: the Feature 4 ticket, in Sections 3 and 4.
- **Files**: `optimistic-concurrency`.
- **Source**: `platform/teamtrack/docs/features/f4.md`.

### The harness in one picture

![The model in the centre, its tools in one dashed box for the sandbox of both arms, the four layers around them (instructions and state feed the model, scope guards the tools, verification checks the done claim), and the referee outside scoring the diff](./harness-one-picture.svg)

*Each layer changes what the agent knows, remembers, may change, or must prove; the referee scores the diff after the stop.*

- **What it teaches**: the whole harness on one page, as a summary.
- **Slide topic**: the summary, at the close.
- **Files**: `harness-one-picture`.
- **Source**: the four `concepts.md` pages.

### Which layer when

![Four rows from a failure to its harness layer: broken written rule to instructions, redone work to state, edits outside the ticket to scope, a false done to verification; scope carries the only measured gap, on Feature 4](./which-layer-when.svg)

*Start from what went wrong, pick the layer, then measure it with an A/B.*

- **What it teaches**: how to choose a layer for your own repository.
- **Slide topic**: use it in your repo, at the close.
- **Files**: `which-layer-when`.
- **Kept to five boxes**: the failures are plain text with an arrow, not boxes; the cost and
  the signal for each layer are in the slide notes and the four `concepts.md` pages.
- **Source**: the four `concepts.md` pages, and the scope result on Feature 4 (the class deck's "All results" slide).

### The results

![Dot chart, one row per section and ticket, a bare and a harness column, filled for passed, hollow for failed, each count in words: Sections 1 and 2 and Section 3 on Feature 3: Safe retries for issue creation 7 of 7 passed per arm; Section 3 on Feature 4 bare 3 of 3 failed, harness 3 of 3 passed; Section 4 4 of 4 failed per arm](./results-final.svg)

*The harness arm was ahead only on out-of-scope files on the Feature 4 ticket: 3 of 3 runs passed against 0 of 3.*

- **What it teaches**: what the course measured, as counts, with every run shown.
- **Slide topic**: what we measured, at the close.
- **Files**: `results-final`.
- **Source**: [the final evidence page](../evidence/final.md).

### House rules

![Seven boxes, one per TeamTrack house rule, each with an example](./house-rules.svg)

*Each rule with one TeamTrack example.*

- **What it teaches**: House rules 1 to 7, which the referee checks, in plain words.
- **Slide**: the house rules slide, right after the data model.
- **Files**: `house-rules`.
- **Source**: `platform/teamtrack/docs/HANDBOOK.md`.
- **How to edit**: open `house-rules.excalidraw`, edit it, then export the PNG and the SVG (see [How to edit a diagram](#how-to-edit-a-diagram)).

### Glossary

![Eight boxes: arm, referee, primary measure, hidden tests, mutant, allowed paths, gate, harness in action](./glossary-terms.svg)

*One plain line per term.*

- **What it teaches**: the eight words the course uses all session.
- **Slide**: the glossary slide, right before "How we'll measure".
- **Files**: `glossary-terms`.
- **Source**: the glossaries in the section `concepts.md` pages and `docs/STYLE.md`.
- **How to edit**: open `glossary-terms.excalidraw`, edit it, then export the PNG and the SVG (see [How to edit a diagram](#how-to-edit-a-diagram)).

### Module 1 summary

![Four numbered layer boxes, each with its mechanism and measured result (scope: harness 3/3, bare 0/3; the others: no measurable difference), all leading to takeaway 5: measure before you keep](./module-summary.svg)

*One mechanism and one result per layer, then the rule.*

- **What it teaches**: the four layers and the one measured gap, as a closing picture.
- **Slide**: "Module 1 Summary: Key takeaways".
- **Files**: `module-summary`.
- **Source**: the four `concepts.md` pages and [the final evidence page](../evidence/final.md).
- **How to edit**: open `module-summary.excalidraw`, edit it, then export the PNG and the SVG (see [How to edit a diagram](#how-to-edit-a-diagram)).


## How to edit a diagram

The diagrams were drawn by a generator script, so the style is the same everywhere. That script is
not part of the course files: the `.excalidraw` file next to each picture is the source you edit.
Keep the same style when you change one:

- Font Excalifont (Excalidraw's hand-drawn font), labels 28, titles 36, never smaller than 26.
- The colours in the table above, each with the same meaning, and the meaning also said in words.
- At most 5 words per label (a title may have 8). Explanations belong in the slide notes, not the
  diagram. No label smaller than 20 px when the picture fills a slide.

To change a diagram:

1. Open its `.excalidraw` file at [Excalidraw](https://excalidraw.com) (menu, Open) and make the
   change.
2. Save it back over the same `.excalidraw` file (menu, Save to, Disk).
3. Export the PNG at 2x scale and the SVG, under the same name, next to the source.
4. Look at the PNG on the navy slide background (`#324158`) before you commit it.

For a diagram with step frames, each frame adds one element, and every frame keeps the full panel,
so the picture does not move between slides. Edit every frame of a diagram the same way.

Every label comes from a file in this repository. If you change a number or a file name, check it
against that file first.

## Licences

| Part | Licence | Used for |
|---|---|---|
| Excalidraw (`@excalidraw/excalidraw` 0.18.0) | MIT | The editor and the export to PNG and SVG |
| Excalifont, the hand-drawn font | SIL Open Font License 1.1 | All text; each SVG embeds a subset |
| React 18.3.1 | MIT | Loaded by the Excalidraw export |
| Playwright for Python and Chromium | Apache-2.0 and BSD-3-Clause | Running the export without a screen |
| fontTools and Brotli | MIT | Measuring text in Excalifont |

The Open Font License allows a font to be embedded in documents. The embedded font keeps its own
licence.

## Sources

- Source 1: Excalidraw, <https://excalidraw.com>, Excalidraw project, n.d.
