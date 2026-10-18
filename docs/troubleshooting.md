# Troubleshooting

> **Terms on this page**
>
> - **Arm**: one agent run in an A/B: the bare arm has no harness, the harness arm has it.
> - **Referee**: the program that scores each run after the agent stops.
> - **Class profile**: the settings the live class runs use, the same for both arms.
> - **Class date**: the class day in `.env`, which names the LangSmith project and keys the session cap.
> - **Primary measure**: the one result each section is judged on, fixed before any run.
> - **Baseline**: the referee's or gate's result on the app before the agent changes it, saved so
>   each run is compared against it.
> - **Gate**: the check that must pass before a feature counts as done.
> - **Mutant**: a copy of the code with one small bug planted on purpose; good tests catch it.
> - **Swap test**: the referee scores a recorded A/B again with the arm labels swapped; the scores
>   must not change.

Find the exact text you see in the first column. The messages are copied from the code, and each
part names the file that prints them, so you can read the code. Never paste your `.env` or a key
into an issue or a chat; none of the messages below contains one.

Parts: [Setup](#setup), [make doctor](#make-doctor), [make warm](#make-warm),
[Running an A/B](#running-an-ab), [Arm status and result lines](#arm-status-and-result-lines),
[The class profile and the Fast tier](#the-class-profile-and-the-fast-tier),
[Replay and swap test](#replay-and-swap-test), [Console](#console), [Slides](#slides),
[Assignments](#assignments), [Your own repository](#your-own-repository).

## Setup

| Symptom | Cause | Fix |
|---|---|---|
| `make: command not found` | make is missing, or you are in PowerShell on Windows | Install make; on Windows open the Ubuntu terminal ([Windows setup](../setup/windows.md#step-8-install-make)) |
| `uv: command not found` | The terminal started before uv was installed | Open a new terminal; check `ls ~/.local/bin/uv` |
| `! docker not found: images not built; sandboxed runs need a container runtime` | Docker is not on the `PATH` (`Makefile`) | Install Docker ([Linux](../setup/linux.md#step-4-install-docker-engine), [macOS](../setup/macos.md#step-4-install-docker-desktop-or-colima)), then `make images` |
| `permission denied` on `/var/run/docker.sock` | Your user is not in the `docker` group yet | `sudo usermod -aG docker $USER`, then log in again (WSL: `wsl.exe --shutdown` in PowerShell) |
| `System has not been booted with systemd` (WSL) | systemd is off | [Windows setup, step 4](../setup/windows.md#step-4-install-wsl2-and-ubuntu) |
| `git tag -l 'm1-*'` prints nothing | The copy was not made with git | Clone with `git clone`; the demos start from these tags |
| The repository path starts with `/mnt/c` (WSL) | The repository is on the Windows drive | Clone again under `~` ([Windows setup, step 9](../setup/windows.md#step-9-clone-the-repository-and-run-make-setup)) |

## make doctor

Source: `platform/src/shipharness/doctor.py`. The last line is `result: + ready` or
`result: x not ready (fix the items above)`. A captured run is on the
[Linux setup page](../setup/linux.md#step-10-run-make-doctor).

| Line | Cause | Fix |
|---|---|---|
| `x missing     OPENAI_API_KEY         not set` (same for `LANGSMITH_API_KEY`) | The key is not in `.env`, or `.env` is in another folder | Fill in `.env` next to the `Makefile` |
| `x invalid     OPENAI_API_KEY ...` | OpenAI rejected the key | Copy the key again, with no spaces or quotes; check that the account has credit |
| `x missing     agent model ...` (or `reviewer model`) | The key cannot use that model (source: `doctor.py`) | Use the key from the program's email, or your own on the Build tier |
| `x invalid     LANGSMITH_API_KEY ...` | LangSmith rejected the key | Create a new key; EU accounts set `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` |
| `! unreachable ...` | A network or proxy problem | Try again, or from another network |
| `! warn        container runtime      docker not found: ...` | No Docker on the `PATH` | Start or install Docker (Linux and WSL: `sudo systemctl start docker`) |
| `x missing     SHIPHARNESS_CLASS_DATE not set (PURPOSE=class needs the class day, YYYY-MM-DD)` | `make doctor` checks the class date by default | Add `SHIPHARNESS_CLASS_DATE=YYYY-MM-DD` to `.env`, or run `make doctor PURPOSE=pilot` |
| `x invalid     .env not in git ...` | `.env` is tracked by git | `git rm --cached .env`, and check that `.gitignore` still lists it |

`uv run shipharness doctor --offline` runs the checks without contacting OpenAI or LangSmith. It
only tells you whether the keys are set.

## make warm

`make warm` runs `uv run shipharness warm` with the class profile. It rebuilds the two images
through `make images` only if their source changed, starts and removes one container per image, and
caches the referee and gate baselines of the class tasks. It makes no model calls and prints one
line per step with its time (source: `platform/src/shipharness/ab/warm.py`).

| Line | Cause | Fix |
|---|---|---|
| `x SHIPHARNESS_CLASS_DATE is not set: class runs need the class day (YYYY-MM-DD)`, then `warm: nothing done` | No class date, with `PURPOSE=class` (the default) | Set the date in `.env`, or run `make warm PURPOSE=pilot` |
| `images: built (<image>: no record of its source; ...)` | First warm-up on this machine | None: it builds once and records the source |
| `images: built (<image>: source changed ...)` | `platform/sandbox/Dockerfile` or `platform/src/` changed | Expected after a code change |
| `x images: build failed (...)` | `make images` failed, usually because Docker is stopped | Start Docker, then `make images` to see the build error |
| `x page-in failed <image>` | The image does not start a container | `make images`; check `docker image ls shipharness-agent` |
| A baseline line starting with `x` | A referee or gate baseline failed | Read the line's detail and rerun; finished baselines stay cached |
| Last line `warm: incomplete (<s> s)` | One of the steps above failed | Fix that step and rerun |

## Running an A/B

`make demo-N`, `make show-N`, `make final`, and `uv run shipharness ab` call OpenAI live and never
fall back to a recorded or scripted run (source: `platform/src/shipharness/ab/commands.py`).

| Message | Cause | Fix |
|---|---|---|
| `x SHIPHARNESS_CLASS_DATE is not set: set it in .env to the class day (YYYY-MM-DD) for class commands, or pass --purpose pilot for a pilot run` | Class commands need the class date | Set it in `.env`, or add `PURPOSE=pilot` or `PURPOSE=assignment` |
| `x OPENAI_API_KEY is missing: live A/B runs call OpenAI and never fall back to a stand-in; ...` | No key | Fill in `.env`, then `make doctor` |
| `x OpenAI refused the key: <reason>; no arm was started` | The key is invalid, cannot use the model, or OpenAI is unreachable | `make doctor` names the problem; `no access to gpt-6-luna (NotFoundError)` means the account is below the Build tier |
| `x no task for feature=<id> example=None variant=canonical` | The feature id is not in `platform/datasets/teamtrack-features-v1.jsonl` | Use one of the feature names listed below the table |
| `! replay needs RUN=<ab or run id>` | `make replay` without `RUN` | `make replay RUN=<id>` (source: `Makefile`) |
| `x unknown --arms '<value>': both or harness` | `--arms` takes `both` (an A/B) or `harness` (what `make show-N` runs) | Use one of the two |
| `x unknown --profile '<value>': standard, class` | `--profile` takes `standard` or `class` | Use one of the two |

The feature names for `FEATURE=` and `FEATURES=` are `org-search`, `comments`, `safe-retries`,
`version-checks`, `bulk-close`, `watchers`, and `labels`, for Features 1 to 7 in that order (the
earlier name `idempotent-create` still works); `make final` takes the last three. The names and
codes are in the [reference](reference.md#names-used-in-this-course). The raw `--feature` flag of
`uv run shipharness ab` also takes the codes `F1` to `F7`, in the same order.

`make experiments` and `make report` only show the options of `uv run shipharness experiments` and
`uv run shipharness report`. Run those commands directly with the options you need.

## Arm status and result lines

At the end of a run the terminal prints `A/B <id> (<feature>, layers=[...], profile=<profile>)`
(with `, harness in action` for `make show-N`), one line per arm, and a cost line.

**Exit code 2 although results were printed.** `shipharness ab` exits 0 when every arm completed, 2
when an arm was aborted (`ABORTED: cap` or `ABORTED: timeout`), and 1 when an arm ended in `ERROR`.
Under make, exit 2 shows as `make: *** [Makefile:<line>: <target>] Error 2` after the cost line. The
run is complete: an aborted arm is scored and shown like any other. `make final` keeps running its
other features and exits with the last non-zero code.

| Status or text | Cause | What it means |
|---|---|---|
| `ABORTED: cap`, reason `cost cap reached: run $<x> of $0.20` (or `session $<x> of $2.50`) | A model call would have crossed a cap (source: `platform/src/shipharness/cost/tracker.py`) | Scored and shown; a session cap stops every live run under that class date |
| `ABORTED: timeout`, reason `agent time limit: RUN_TIMEOUT_S 420 s` | The arm used its agent time (300 s outside the class profile) | Scored and shown, with whatever the arm shipped |
| `ABORTED: timeout`, reason `harness time limit: HARNESS_TIMEOUT_S 900 s exceeded during ...` | The harness work used its 900 s (120 s outside the class profile) | Scored and shown |
| `ERROR`, `OpenAI rejected the request: check OPENAI_API_KEY (authentication failed).` | The key stopped working mid-run (source: `platform/src/shipharness/runner/loop.py`) | Fix the key; the run says nothing about the harness |
| `ERROR`, `OpenAI billing limit reached (quota or spend limit); add credit and retry.` | The account is out of credit or at its spend limit | Add credit |
| `ERROR`, `OpenAI request kept failing after retries` | Repeated rate-limit or server errors | Try again later |
| `ERROR`, `arm setup failed: RuntimeError: docker run failed: ...` | Docker stopped, or an image is missing | Start Docker; `make images` |
| `passed=True` on a `make final` line with a low hidden-test count | The final features have no primary measure, so `passed` is always true | Read the hidden-test and mutant counts ([final project](../final-project/README.md#what-the-result-means)) |

## The class profile and the Fast tier

`PROFILE=class`, the default of the live targets and `make warm`, runs both arms at reasoning effort
`low`, with 2 CPUs per container, a 420 s agent time limit, a 900 s harness work limit, and the
OpenAI Fast tier for the agent's calls (`platform/src/shipharness/config/profiles.py`). Fast costs twice the Standard rate per token (`platform/config/prices.toml`). Each call is
charged by the tier its response reports.

| Symptom | Cause | Fix |
|---|---|---|
| A class run is slower than usual, or costs less than the Fast rates predict | OpenAI answered some Fast requests at the Standard tier (`"service_tier": "default"` in `.shipharness/ledger.jsonl`) | Nothing to fix: the run is valid, priced right, and within the caps |
| Startup error naming `OPENAI_SERVICE_TIER` and a missing `[models."<model>".fast]` table | A model with no Fast prices in `platform/config/prices.toml` | Use the course model, or add `PROFILE=standard` |
| You want the settings from `.env` (for example effort `medium`) | The class profile overrides them | Add `PROFILE=standard` to the make command |

## Replay and swap test

Source: `platform/src/shipharness/ab/commands.py` and `platform/src/shipharness/ab/recorded.py`.

| Message | Cause | Fix |
|---|---|---|
| ``x no recorded A/B for section demo-N under .shipharness/runs; run `make demo-N` first, or pass AB=<id>`` | No finished A/B of that section | Run the demo first, or `make swap-N AB=<ab id>` |
| `x no recorded A/B for '<id>' under .shipharness/runs; check the A/B or run id` | Wrong id | Copy the id from the console's run list |
| `x <ab id> predates checkpoint SHA pinning: ...` | The record has no pinned checkpoint commit | Use a newer recording |
| `x <id> is a single-arm run (harness in action): the swap test needs both arms; ...` | `make swap-N` on a `make show-N` run | Pass the id of an A/B; `make replay` works on single-arm runs |
| `Swap test on <ab id>: judged measures DIFFERENT`, then `<arm> <field>: <before> -> <after>` | The referee scored the same diff differently under the other label | Report it with the A/B id; the referee is meant to be deterministic |
| `make replay` asks for `SHIPHARNESS_CLASS_DATE` | `make replay` runs with `PURPOSE=class` by default | Set the date, or add `PURPOSE=pilot` |
| Screen 2 of a replay shows broken images | Replay does not copy the `screenshots/` folder | `cp -a .shipharness/runs/<recorded id>/screenshots .shipharness/runs/<replay id>/`, then reload |

## Console

| Symptom | Cause | Fix |
|---|---|---|
| `No runs yet. Start one in a second terminal: make show-1 ...` | Nothing under `.shipharness/runs/` of the folder where the console started | Start `make console` from the repository folder |
| The run list does not show a new run | The list does not refresh by itself | Reload the page; the newest run is the top card |
| You are on a run's screens and want another run | Each run has its own page | Press `H` or `Esc`, or click "← All runs" at the top left |
| The header shows `reconnecting` | The console server stopped | Restart `make console` and reload |
| Port 8765 (or 8000) is in use | Another server uses it | `make console CONSOLE_PORT=8766`, `make up PORT=8001` |
| The `make console` terminal shows no line per request | Quiet by default: only warnings and errors print | `make console VERBOSE=1` |
| Screen 2: `No board screenshot yet (the preview container takes one every 5 s).` all run long | The board preview container did not start | Display only; the referee's board checks still run |
| Screen 4: `No results to compare yet` | No records found: neither `docs/evidence/scores/` nor `exports/scores/` | Start `make console` in the repository folder |
| Screen 4 does not show a `make show-N` run | Screen 4 compares arms, and a show-N run has one arm (`platform/src/shipharness/console/report.py`) | Expected; `uv run shipharness report` writes every record to `exports/report.html` |
| Any screen shows `UNSANDBOXED — results not official` | `SANDBOX_MODE=none`, or no runtime was found | Fix Docker; unsandboxed results are for exploring only |

## Slides

The class deck is one PowerPoint file,
[Harness Engineering for Coding Agents.pptx](../slides/Harness%20Engineering%20for%20Coding%20Agents.pptx).
Open it in PowerPoint; the speaker notes are in the deck. There is no PDF and no slide build.

## Assignments

| Symptom | Fix |
|---|---|
| `make check-assignment-N` exits with `Error 1` and FAIL lines on a fresh clone | Expected: the starter files are unfinished, and each FAIL line names what to fix |
| `! grade-assignment-N needs SUBMISSION=<folder or git URL>`, or `no grader for assignment N: ...` | The grader is for the instructor and is not in this repository (`platform/scripts/grade_assignment.py`); use `make check-assignment-N` |
| A live step stops at `cost cap reached` | Read the assignment's cost section; the run is still recorded and scored |

## Your own repository

| Symptom | Fix |
|---|---|
| `UNSANDBOXED: the checks import and run this app's code on this machine.` from `shipharness check` | Expected: `check` runs the app in process; run it only on code you trust |
| `shipharness testgen` keeps no tests on a well-covered module | Kept tests must add coverage or kill a new mutant; pick a less covered module |
| `testgen` prints UNSANDBOXED | It runs generated tests with your permissions; for untrusted code add `--sandbox docker --image` |
| `shipharness skills validate` reports a `name` error | `name` must equal the folder name: lowercase letters, digits, and hyphens |
