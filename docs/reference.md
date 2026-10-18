# Reference

> **Terms on this page**
>
> - **Bare arm**: an agent run with the ticket and the repository, and no harness.
> - **Harness arm**: the same run with the harness turned on.
> - **A/B**: bare arm and harness arm on the same ticket, scored the same way.
> - **Referee**: the program that scores each run after the agent stops.
> - **Class profile**: the settings the live class runs use, the same for both arms (below).
> - **Class date**: the class day in `.env`, which names the LangSmith project and keys the session cap.

This page lists everything you look up but do not read in order: every make target, every setting
and variable, the caps and limits, and the folders. Each table names the file its values come from.

### Names used in this course

Pages name each feature, house rule, section, assignment, and test filter as "Kind N: name" the
first time, such as "Feature 4: Version checks on issue edits", and by the short form after that
("Feature 4"). The code in the last column appears only in code: commands, file names, logs,
console screens, and captured output. For the filters, it names the file that defines them
(under `platform/src/shipharness/filters/`, or in the last assignment for the sixth filter).

| Name | What it means | Command alias | Code in code and logs |
|---|---|---|---|
| Feature 1: Org-wide issue search | `GET /issues` across every project of your org | `org-search` | `F1` |
| Feature 2: Comments on issues | Add and list comments on an issue | `comments` | `F2` |
| Feature 3: Safe retries for issue creation | A retried create never makes a duplicate issue | `safe-retries` | `F3` |
| Feature 4: Version checks on issue edits | A stale edit is refused, never silently saved; issue history | `version-checks` | `F4` |
| Feature 5: Bulk close | Close all finished issues of a project in one request | `bulk-close` | `F5` |
| Feature 6: Watchers | Follow issues and see them in one list | `watchers` | `F6` |
| Feature 7: Labels | Tag issues with labels and filter lists by label | `labels` | `F7` |
| House rule 1: Tenant isolation | Another org's resource answers 404 | | `R1` |
| House rule 2: Roles | Viewers cannot write; some writes are admin-only | | `R2` |
| House rule 3: API conventions | List and error envelopes, status codes | | `R3` |
| House rule 4: Safe retries | Creates honour the `Idempotency-Key` header | | `R4` |
| House rule 5: Audit log | One audit row per write | | `R5` |
| House rule 6: Layering | The API layer never imports the database layer | | `R6` |
| House rule 7: Migrations | One Alembic head; upgrades work on an empty database | | `R7` |
| House rule 8: Deleted issues stay hidden | Soft-deleted issues never appear; you add it in the last assignment | | `R8` |
| Section 1: Instructions | What the agent knows | | `S1`, `m1-s1-start` |
| Section 2: State and sessions | What the agent remembers across sessions | | `S2`, `m1-s2-start` |
| Section 3: Scope and sandbox | What the agent may change and reach | | `S3`, `m1-s3-start` |
| Section 4: Verification | What proves the work is done | | `S4`, `m1-s4-start` |
| Assignment 1: Instructions | The take-home work of Section 1 | | `A1`, `check-assignment-1` |
| Assignment 2: State and sessions | The take-home work of Section 2 | | `A2`, `check-assignment-2` |
| Assignment 3: Scope and sandbox | The take-home work of Section 3 | | `A3`, `check-assignment-3` |
| Assignment 4: Verification | The take-home work of Section 4 | | `A4`, `check-assignment-4` |
| Filter 1: Builds and collects | pytest collects the test and runs it | | `filters.py` |
| Filter 2: Passes five runs | The test passes on each of five runs | | `filters.py` |
| Filter 3: Adds coverage or catches a mutant | New covered lines, or a mutant no other test kills | | `filters.py` |
| Filter 4: Real assertions | An assertion that can fail; no mock of the unit under test | | `filters.py` |
| Filter 5: No source changes | No source file changes during the test phase | | `filters.py` |
| Filter 6: No duplicate tests | Added in Assignment 4: a kept test repeats no kept test | | `dedup_filter.py` |

The four section features (Features 1 to 4) belong to the sections; the final project picks from
Features 5 to 7. Commands take the alias, in any case, or the code: `make demo-3
FEATURE=version-checks`, `make final FEATURES=watchers,bulk-close`. The earlier alias
`idempotent-create` still works for Feature 3. A checkpoint tag such as `m1-s1-start` is the git
tag of the repository state at the start of a section. A walkthrough anchor such as `S4:gate` is a
marker in the code that a walkthrough page points to; it keeps the short form.

Sources are cited by their linked title, such as
[Harness engineering](https://openai.com/index/harness-engineering/), then as "Source 1". Each
page ends with a numbered Sources list: "Source N: title, link, author, date". Numbering is per
page.

### Glossary

Every course term, in plain words, is in the [glossary](glossary.md): every feature, house rule,
section, filter, and assignment name, and terms such as arm, referee, mutant, and pass^k.

## Make targets

Every target is a thin wrapper over `uv run ...` (`Makefile`). On Windows, run make inside Ubuntu
on WSL2. The "Runs" column is what `make -n <target>` prints. `make help` lists every target with a
one-line description, and the feature names:

> Your output will differ: run times, ids, and the agent's wording change on every run.

```text
Targets (on Windows, run make inside Ubuntu on WSL2):
  help                 Print this list of targets and feature names
  setup                Install the pinned packages, build both images, create .env if missing
  images               Build the agent and referee sandbox images
  doctor               Check tools, Docker, both keys, the course models, prices, the class date
  warm                 Before class: images, containers, referee and gate baselines; no model calls
  up                   Start TeamTrack and its board on http://127.0.0.1:8000/board
  console              Start the live console on http://127.0.0.1:8765/
  datasets             Upload the two datasets to LangSmith once (Assignment 1 needs them)
  show-N               Live: the harness arm alone on the ticket of section N (N is 1 to 4)
  demo-N               Live A/B on the ticket of section N; LAYERS=-<layer> removes one layer
  final                Live: one A/B per feature in FEATURES, for example FEATURES=watchers,bulk-close
  swap-N               Re-judge the latest A/B of section N with the labels swapped; AB=<id> picks one
  replay               Replay a recorded run on every screen, no model calls: make replay RUN=<id>
  example-N            Optional: the layers of section N driven by scripted steps, no model
  experiments          Show the options of uv run shipharness experiments
  report               Show the options of uv run shipharness report
  check-assignment-N   Offline self-check of Assignment N
  grade-assignment-N   Instructor only: grade a submission, SUBMISSION=<folder or git URL>
  test                 Run the fast test suite
  test-all             Run every test that needs no key and no container
  test-live            Run the tests that call OpenAI and LangSmith
  test-docker          Run the sandbox tests in real containers
  lint                 Ruff, the import contract, anchors, and skills validation
  format               Rewrite files with ruff check --fix and ruff format
  lint-prose           Check the course pages for banned words and emoji
  check-style          Check the course pages against docs/STYLE.md; CHECK_STYLE_OPTS=--strict
  anchors              List the code walkthrough anchors
Feature names for FEATURE and FEATURES (the readable name or the code, any case):
    org-search           F1  Feature 1: Org-wide issue search
    comments             F2  Feature 2: Comments on issues
    safe-retries         F3  Feature 3: Safe retries for issue creation (idempotent-create also works)
    version-checks       F4  Feature 4: Version checks on issue edits
    bulk-close           F5  Feature 5: Bulk close
    watchers             F6  Feature 6: Watchers
    labels               F7  Feature 7: Labels
Examples: make demo-3 FEATURE=version-checks; make final FEATURES=watchers,bulk-close
```

### Setup and checks (no model calls)

| Target | Runs | What it does |
|---|---|---|
| `make setup` | `uv sync --frozen`, then `make images` | Installs the pinned packages, builds both images, copies `.env.example` to `.env` if missing |
| `make images` | `docker build -f platform/sandbox/Dockerfile ...` | Builds `shipharness-agent:1` and `shipharness-referee:1` |
| `make doctor` | `uv run shipharness doctor --purpose class` | Checks tools, Docker, both keys, prices, and the class date |
| `make warm` | `uv run shipharness warm --purpose class --profile class ...` | Rebuilds changed images, starts each once, caches the baselines |
| `make up` | `uv run shipharness up --port 8000` | TeamTrack and its board on http://127.0.0.1:8000/board |
| `make console` | `uv run shipharness console --port 8765` | The live console on http://127.0.0.1:8765/; `VERBOSE=1` logs each request |
| `make datasets` | `uv run shipharness datasets upload` | Uploads the two datasets to LangSmith once (Assignment 1 needs them) |

`make doctor` tests the OpenAI key and asks whether it can use the agent model and the reviewer
model, which uses no tokens. With `PURPOSE=class`,
`make doctor` and `make warm` stop with a clear message when the class date is missing.

### Live runs (call OpenAI)

These call OpenAI live and never fall back to a recording. Each prints a `Cost:` line at the end.

| Target | Runs | What it does | At most, at the caps |
|---|---|---|---|
| `make show-1` to `make show-4` | `uv run shipharness ab --section demo-N --feature <name> --arms harness ...` | The harness arm alone, judged by the referee | $0.24 |
| `make demo-1` to `make demo-4` | `uv run shipharness ab --section demo-N --feature <name> ...` | A/B: both arms, both judged | $0.48 |
| `make demo-3 FEATURE=version-checks` | `uv run shipharness ab --section demo-3 --feature version-checks ...` | The Section 3 live A/B in class, on Feature 4 | $0.48 |
| `make final` | one `uv run shipharness ab --section final --feature <f> ...` per feature | One A/B per feature in `FEATURES` | $0.58 per feature |

`<name>` is the section's feature name: `org-search`, `comments`, `safe-retries`, or
`version-checks`. `make final` prints one line per feature, for example `Final A/B: Feature 5: Bulk
close`, then that A/B's output.

The worst cases come from the caps in `.env.example`: one arm $0.20 plus one review $0.04; a final
arm $0.25. A `make show-N` run is not an A/B, so its score stays out of every comparison, out of
screen 4, and out of `make swap-N`. Exit codes: 0 when every arm completed, 2 when an arm was
aborted (cost cap or time limit; still judged and shown), 1 on an error.

### Replays and re-judging (no model calls)

| Target | Runs | What it does |
|---|---|---|
| `make swap-1` to `make swap-4` | `uv run shipharness ab --swap latest --section demo-N ...` | Re-judges the latest A/B with the labels swapped (`AB=<id>` picks another) |
| `make replay RUN=<id>` | `uv run shipharness replay <id> --purpose class` | Replays a recorded run with RECORDING on every screen and judges it again |
| `make example-1` to `make example-4` | `uv run shipharness example --section demo-N --profile class` | Optional extra: scripted steps, no model ([extras](extras.md)) |

### Assignments and tests

| Target | Runs | What it does |
|---|---|---|
| `make check-assignment-1` to `-4` | `uv run python section-N-*/assignment/check.py` | Offline self-check of your work |
| `make grade-assignment-1` to `-4` | `uv run python platform/scripts/grade_assignment.py N "<SUBMISSION>"` | The instructor's grader; the graders are not in this repository |
| `make test` | `uv run pytest` | The fast suite |
| `make test-all` | `uv run pytest -n auto -m "not live and not docker"` | Every test that needs no key and no container |
| `make test-live` | `uv run pytest -m live platform/tests/live` | Tests that call OpenAI and LangSmith |
| `make test-docker` | `uv run pytest -m docker platform/tests/unit/test_sandbox_docker.py` | Sandbox tests in real containers |
| `make lint` | ruff, the import contract, anchors, skills validation | Code checks |
| `make format` | `uv run ruff check --fix .`, `uv run ruff format .` | Rewrites files |
| `make lint-prose` | `uv run python platform/scripts/lint_prose.py` | Banned words and emoji in the course pages |
| `make anchors` | `uv run python platform/scripts/anchors.py list` | Lists the code walkthrough anchors |

`make experiments` and `make report` show the options of `uv run shipharness experiments` and
`uv run shipharness report`; run those commands directly with the options you need.

### Other commands

| Command | What it does | Model calls |
|---|---|---|
| `uv run shipharness report` | Writes `exports/report.html` from `exports/` | None |
| `uv run shipharness verify --tag class-v1` | Checks that your copy matches the class release tag | None |
| `uv run shipharness init --target <your-repo>` | Copies the starter kit into your repository | None |
| `uv run shipharness testgen ...` | Proposes tests for one module and keeps those that pass Filters 1 to 5 | Yes, at most $0.20 |
| `uv run shipharness check ...` | House-rule checks for a FastAPI app; exit 3 on new violations | None |
| `uv run shipharness skills validate <dir>` | Validates Agent Skills folders | None |

`uv run shipharness --help` lists every command. In `init`, `<your-repo>` is the path to a
repository of yours.

### The console

`make console`, then open http://127.0.0.1:8765/ and click a run. Press `1` to `5` to switch
screens and `F` to show one arm full width (both, bare, harness).
Its terminal prints only the address, warnings, and errors; `make console VERBOSE=1` also prints
a line per request.

| Key | Screen | What it shows |
|---|---|---|
| `1` | Live | Each arm's turns, cost, harness decisions, the gate, and the verdict |
| `2` | Boards | Each arm's running board as an Acme user, every 5 s |
| `3` | Evidence | Files read, the diff map, sandbox denials, the referee's checks, mutants |
| `4` | A/B report | One dot per run for each feature and arm, reviewer agreement |
| `5` | Traces | A live tail of events and the LangSmith trace links |

A replay shows a red `● RECORDING` badge on every screen. A run without a sandbox shows
`⚠ UNSANDBOXED — results not official`.

## Settings and variables

### Make variables

Defaults from the `Makefile`.

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `PURPOSE` | `class` | live runs, swap, replay, doctor, warm | LangSmith project and cost session (table below) |
| `PROFILE` | `class` | live runs, examples, warm | `class` or `standard` (the settings in `.env`) |
| `FEATURE` | `safe-retries` (Feature 3) | demo-3 | `version-checks` runs the Section 3 class A/B |
| `FEATURES` | `bulk-close,watchers` (Features 5 and 6) | final | Comma-separated final features, for example `watchers` |
| `LAYERS` | empty | demo-N, show-N, final | `-<layer>` removes one layer, for example `-state` |
| `SESSION_BUDGET` | empty | demo-N, show-N | Session turn budgets, for example `12,38` |
| `AB` | `latest` | swap-N | The A/B or run id to re-judge |
| `RUN` | empty | replay | The A/B or run id to replay (required) |
| `SUBMISSION` | empty | grade-assignment-N | Folder or git URL (instructor only) |
| `A1_WORK`, `A2_IMPL`, `A3_IMPL`, `A4_IMPL` | the starter | check-assignment-N | Your work folder |
| `PORT`, `CONSOLE_PORT` | `8000`, `8765` | up, console | Server ports |
| `RUNTIME` | `docker` | setup, images, warm | `podman` also works (set `SANDBOX_RUNTIME=podman` too) |
| `UV` | `uv` | every target | The uv command |

### The class profile

`PROFILE=class` is the default of the live targets and `make warm`. It sets the same values for
both arms (`platform/src/shipharness/config/profiles.py`):

| Setting | Class profile | Standard profile (`.env`) |
|---|---|---|
| Reasoning effort, agent | `low` | `OPENAI_REASONING_EFFORT` (`medium`) |
| OpenAI service tier, agent | Fast | `OPENAI_SERVICE_TIER` (`auto`) |
| CPUs per container | 2 | `SANDBOX_CPUS` (`1.0`) |
| Agent time limit per arm | 420 s | `RUN_TIMEOUT_S` (300 s) |
| Harness work limit per arm | 900 s | `HARNESS_TIMEOUT_S` (120 s) |

The reviewer keeps `OPENAI_EVAL_REASONING_EFFORT` and the Standard tier. Each call is charged by the
tier its response reports: a Fast request answered at the Standard tier is charged the Standard
rate, and `.shipharness/ledger.jsonl` records the tier. The referee also runs the primary measure's
checks first, so the primary verdict shows early, and re-runs each shipped test five times for
flakiness.

### The class date

`SHIPHARNESS_CLASS_DATE` in `.env` is the class day as `YYYY-MM-DD`. It names the LangSmith project
`shipharness-class-<date>`, and every command under one date shares one session cap. Live runs,
`make replay`, `make doctor`, and `make warm` with `PURPOSE=class` refuse to start without it. Set it
to the day you run the commands, or use another purpose:

| `PURPOSE` | LangSmith project | Cost session |
|---|---|---|
| `class` | `shipharness-class-<date>` | One per class date |
| `pilot` | `shipharness-pilot` | One, named `pilot` |
| `assignment` | `shipharness-assignments` | One, named `assignment` |

### Settings in `.env`

`make setup` copies `.env.example` to `.env`. The ones you may change:

| Setting | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY`, `LANGSMITH_API_KEY` | empty | Required; never printed, logged, traced, or passed into a container |
| `OPENAI_MODEL`, `OPENAI_EVAL_MODEL` | `gpt-6-luna`, `gpt-5.6-luna` | Agent and reviewer models |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` | EU accounts: `https://eu.api.smith.langchain.com` |
| `SANDBOX_MODE` | `docker` | `none` runs commands on the host, labelled UNSANDBOXED |
| `RUNS_DIR`, `EXPORTS_DIR` | `.shipharness/runs`, `exports` | Where runs and score records go |

## Caps and limits

The cost tracker checks every model call against these caps before it is sent
(`.env.example`). When a call would cross a cap, the run ends as `ABORTED: cap`, and the referee
still judges and shows it. Commands running at the same time share the caps.

| Cap | Value | Scope |
|---|---|---|
| `MAX_RUN_COST_USD` | $0.20 | One arm of one run; also one `testgen` run |
| `MAX_FINAL_RUN_COST_USD` | $0.25 | One arm of one `make final` run |
| `MAX_REVIEW_COST_USD` | $0.04 | One blinded review |
| `MAX_SESSION_COST_USD` | $2.50 | Every command under one class date or purpose |
| `MAX_BATCH_COST_USD` | $2.50 | Any single command |
| `MAX_EXPERIMENT_TOTAL_USD` | $25.00 | All `shipharness experiments` batches |
| `MAX_BUILD_TOTAL_USD` | $15.00 | Every model call in this machine's cost ledger |

Time and turn limits (`.env.example`; the class profile changes the agent and harness time limits):

| Limit | Value | Scope |
|---|---|---|
| `RUN_TIMEOUT_S` | 300 s (class profile 420 s) | Agent time per arm per run |
| `HARNESS_TIMEOUT_S` | 120 s (class profile 900 s) | Harness work per arm per run |
| `TOOL_TIMEOUT_S` | 120 s | One tool command |
| `MAX_TURNS_PER_SESSION` | 30 | Turns per session unless the task sets its own budget |

Prices per 1M tokens (`platform/config/prices.toml`):

| Model and tier | Input | Cached input | Output |
|---|---|---|---|
| gpt-6-luna, Standard | $0.10 | $0.01 | $0.50 |
| gpt-6-luna, Fast | $0.20 | $0.02 | $1.00 |
| gpt-5.6-luna (reviewer), Standard | $0.20 | $0.02 | $1.20 |

Cache writes cost $0.125, $0.25, and $0.25 per 1M tokens in the same order. At the caps, the class
plan (three `make show-N` runs, one `make demo-3`, two final features) needs at most $2.36, under the
$2.50 session cap. Measured costs of each class command are on the
[evidence page](evidence/general.md#timings). The course's budget for the four assignments together
is $6 of OpenAI usage and 400 LangSmith traces (course policy).

## Folders

| Folder | What it holds |
|---|---|
| `setup/` | First-time setup for Windows, macOS, and Linux |
| `section-1-instructions/` to `section-4-verification/` | One folder per section: concepts, demo, assignment, reading, session notes |
| `final-project/` | The whole harness on a new feature, then your own repository |
| `slides/` | The class deck, one PowerPoint file |
| `use-in-your-repo/` | The starter kit (`kit/`), four skills (`skills/`), and the guide |
| `docs/` | This page, the instructor guide, troubleshooting, architecture, evidence |
| `platform/src/shipharness/` | The command-line tool: runner, harness layers, referee, console |
| `platform/teamtrack/` | The app the agent works on, with its tests and features |
| `platform/sandbox/` | The Dockerfile for the agent and referee images |
| `platform/config/` | `prices.toml` |
| `platform/datasets/` | The TeamTrack tasks and the test-generation targets |
| `platform/scripts/`, `platform/tests/` | Course scripts and the test suite |

Files that runs write: `.shipharness/runs/<ab id>/` (run log, diffs, board screenshots),
`.shipharness/ledger.jsonl` (one line per model call), and `exports/scores/` (one score record per
arm). All three are git-ignored. More detail: [architecture](architecture.md).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
