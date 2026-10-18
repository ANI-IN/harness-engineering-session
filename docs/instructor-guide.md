# Instructor guide

This guide runs the live class of Module 1: Harness Engineering for Coding Agents. The first section
fits on one printed page. The sections after it give the detail behind each line.

> **Terms on this page**
>
> - **Harness arm**: The same run with the harness turned on.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **A/B**: Bare arm and harness arm on the same ticket, scored the same way.
> - **Harness in action**: A `make show-N` run: the harness arm alone, live, not an A/B.
> - **Referee**: The program that scores each run after the agent stops.
> - **Primary verdict**: The referee's answer to the one question the section asks.
> - **Console**: The browser page that shows a run live, on five screens.
> - **Fallback recording**: A run you record the day before and replay only if a live run breaks.
> - **Hidden tests**: Tests the agent never sees; the referee runs them after the agent stops.
> - **Mutant**: A copy of the code with one small bug planted on purpose; good tests catch it.
> - **Gate**: The check that must pass before a feature counts as done.
> - **Baseline**: The referee's or gate's result on the app before the agent changes it, saved so
>   each run is compared against it.
> - **Pill**: A small status badge on screen 1; one shows the primary verdict, others the gate.

The [Live Demo Guide](../guide/README.md) ([PDF](../guide/Harness%20Engineering%20Demo%20Guide.pdf)) walks
through every demo step by step, with an instructor note at each step.

## Class-day cheat sheet

Run every command in the repository folder, in an Ubuntu terminal. Terminal A runs the console.
Terminal B runs the section demos. Terminal C runs the final.

| Time | Terminal | Command | What you should see |
|---|---|---|---|
| T-30 min | B | `sed -i "s/^SHIPHARNESS_CLASS_DATE=.*/SHIPHARNESS_CLASS_DATE=$(date +%F)/" .env` | `grep ^SHIPHARNESS_CLASS_DATE= .env` shows today |
| T-30 min | B | `make doctor` | Last line `result: + ready` |
| T-30 min | B | `make warm` | `warm: done` |
| T-30 min | A | `make console` | `Console: http://127.0.0.1:8765/`; open it |
| 0:08 | B | `make doctor` | Read the key lines aloud |
| 0:11 | B | `make show-1` | Section 1: Instructions, harness in action |
| 1:11 | B | `make show-2 SESSION_BUDGET=12,38` | Section 2: State and sessions, two sessions |
| 2:01 | B | `make demo-3 FEATURE=version-checks` | Section 3: Scope and sandbox, live A/B |
| 2:57 | B | `make show-4` | Right after the one poll (2:55): Section 4: Verification, harness in action |
| 2:57 | C | `make final FEATURES=watchers,bulk-close` | The final A/B; the poll's winner first |
| 3:40 | C | No command | Read the final's arm lines |

After each launch, reload the run list ("← All runs") and open the top card. At section minute 15,
look for the `Cost:` line in terminal B. Breaks: 1:00-1:10 and 2:50-2:55.

Measured 2026-10-18, class profile, from launch: two runs each, alone, the demo guide's ([runs](evidence/general.md#guide-runs-2026-10-18)) and a reviewer's on a fresh clone;
two at once make both slower. In brackets, three earlier runs, two at a time ([runs](evidence/general.md#demo-runs-after-the-speed-up)):

| Run | Primary verdict | Full verdict | Cost (cap) |
|---|---|---|---|
| `make show-1` | 1:45 to 2:35 (2:57 to 6:18) | 3:37 to 4:45 (7:23 to 10:58) | $0.020 to $0.021 ($0.24) |
| `make show-2` | 4:11 to 5:18 (3:21 to 5:20) | 5:52 to 7:11 (5:10 to 6:59) | $0.036 to $0.044 ($0.24) |
| `make demo-3` | bare 1:59 to 3:10, harness 2:57 to 5:59 (1:52 to 7:23) | bare 4:25 to 5:55, harness 5:14 to 8:24 (3:58 to 9:43) | $0.050 to $0.056 ($0.48) |
| `make show-4` | 4:37 to 6:54 (5:51 to 6:50) | 5:32 to 8:02 (6:51 to 8:26) | $0.026 to $0.028 ($0.24) |
| `make final`, one feature | bare 2:48 to 3:27, harness 5:31 to 7:23 (1:49 to 12:04) | bare 5:07 to 6:02, harness 7:25 to 9:10 (4:16 to 15:22) | $0.038 to $0.042 ($0.58) |

Every arm completed. `make show-4` filters only the first three proposed tests (a demo setting,
[disclosed](evidence/s4.md#s4-show-4-settings)); the final's harness arm filters all of its tests,
two at a time, so it still finishes last: start it first in its section. The session cap is $2.50: run two final features only if
the session figure on the Section 3 `Cost:` line is $1.10 or less.

What to say at each verdict:

| Section | Pass | Fail |
|---|---|---|
| 1 | "No new tenant leak. One run shows the layer ran, not that it helped." | "A leak shipped with the map in place. That is a result." |
| 2 | "Session 2 picked up the work. No continuity failure." | "The handoff did not carry the work. Screen 3 shows how." |
| 3 | "No file outside the ticket's paths." | "This arm changed a file it was not asked to touch." |
| 4 | "Every hidden test and every mutant. The work is done." | "The agent said done. The hidden tests and mutants say no." |
| Final | No primary measure: read hidden tests and mutants per arm. | "One A/B is one dot." |

Section 3's pill reads files outside the allowed paths; Feature 4: Version checks on issue edits'
tests and mutants are secondary. Screen 4: bare 1/10, harness 10/10 ([before class](evidence/s3.md#s3-screen-4-before-class)).

Keys: `1` Live, `2` Boards, `3` Evidence, `4` A/B Report, `5` Traces, `F` one arm, `H`/`Esc` run list.

If a demo stalls:

1. `docker ps`: the arm and referee containers stay listed while the run works.
2. `tail -n 3 .shipharness/ledger.jsonl`: a new line appears after each model call.
3. `make replay RUN=<fallback id>`: only after an `ERROR` from outside the experiment.

Who to call: the helper you named the day before. They watch terminal B and restart Docker.

## The day before

The class date is not set yet, so every command today uses `PURPOSE=pilot`. Pilot runs trace to the
LangSmith project `shipharness-pilot` and leave the class session untouched.

### Check the machine

```bash
make doctor PURPOSE=pilot
make warm PURPOSE=pilot
```

`make doctor` ends with `result: + ready`. Both key lines say `accepted by OpenAI` and `accepted by
LangSmith`, and the `agent model` and `reviewer model` lines say `accepted`.
`make warm` builds the images if their source changed, starts each image once, and caches the referee and gate baselines. It makes no model calls. After an image rebuild it took 2 min
21 s and 3 min 40 s before class. With nothing changed it took 1.2 s. A run with nothing to do ends like this:

> Your output will differ: run times, ids, and the agent's wording change on every run.

```text
gate baseline final (Feature 7: Labels): cached (0.0 s)
warm: done (1.9 s)
Cost: $0.000000 (this command: no calls; session $0.000000 of $2.50; build $0.000000 of $15.00 ($15.000000 left))
```

If `make warm` ends with `warm: incomplete`, run `make images`, then `make warm PURPOSE=pilot` again.

### Record the fallbacks

Run each class command once, in class order. The poll in Section 4 can pick any final feature,
so record all three:

```bash
make show-1 PURPOSE=pilot
make show-2 SESSION_BUDGET=12,38 PURPOSE=pilot
make demo-3 FEATURE=version-checks PURPOSE=pilot
make show-4 PURPOSE=pilot
make final FEATURES=bulk-close PURPOSE=pilot
make final FEATURES=watchers PURPOSE=pilot
make final FEATURES=labels PURPOSE=pilot
```

The fallbacks recorded on 2026-10-18 after the harness speed-up, one per command, and the replay
check are listed on the
[evidence page](evidence/general.md#fallbacks-2026-10-18-speed-up).

The first line of each result starts with `A/B` and the id. Write each id down. The fallback for a
command is the first complete run, whatever its result. Do not run a command again to get a nicer
result.

All pilot commands share one cost session, capped at $2.50. Read the session figure on each `Cost:`
line before the next command. If the rest would not fit at the caps, record the final features first.

Check each recording once, then copy it out of the repository. Replace `ID` with the id you wrote
down:

```bash
make replay RUN=ID PURPOSE=pilot
mkdir -p ~/shipharness-fallbacks && cp -a .shipharness/runs/ID ~/shipharness-fallbacks/
```

The replay makes no model calls and shows a red RECORDING badge on every screen. Copy each arm's
score record from `exports/scores/` too. The arms' run ids are in `.shipharness/runs/ID/ab.json`.

### Name a helper

Pick one person who can watch terminal B during class and restart Docker
(`sudo systemctl restart docker`). Give them this page.

## Thirty minutes before

<a id="stage-2-t-30-minutes"></a>

### Set the class date

Class runs trace to the LangSmith project `shipharness-class-` plus the date, and every class command
shares that day's $2.50 session. `make doctor` and `make warm` refuse to start without the date.
Write today's date into `.env`:

```bash
sed -i "s/^SHIPHARNESS_CLASS_DATE=.*/SHIPHARNESS_CLASS_DATE=$(date +%F)/" .env
grep '^SHIPHARNESS_CLASS_DATE=' .env
```

The second command prints the line with today's date. If it prints nothing, the line is missing.
Add `SHIPHARNESS_CLASS_DATE=` followed by today's date (YYYY-MM-DD) to `.env`, and check again.

### Check, warm, and open the console

| Step | Terminal | Command | You should see |
|---|---|---|---|
| 1 | B | `make doctor` | `result: + ready`; the date line names today's class project |
| 2 | B | `make warm` | `warm: done`, in seconds when nothing changed |
| 3 | A | `make console` | `Console: http://127.0.0.1:8765/`; leave it running |
| 4 | Browser | Open `http://127.0.0.1:8765/` | The run list (one card per run, newest first) and the key legend |

If `make doctor` or `make warm` says `SHIPHARNESS_CLASS_DATE is not set`, the date step did not
work. `make warm` then prints `warm: nothing done` and exits 2. Repeat the date step.

Do not run `make show-1`, `make demo-3`, or `make final` before class. They would spend the class
session.

### Arrange the screen

| Window | What it shows |
|---|---|
| Terminal A | `make console`; leave it alone |
| Terminal B | The section commands, in a large font |
| Terminal C | `make final`, from the Section 4 launch to the final block |
| Browser tab 1 | The slides |
| Browser tab 2 | The console: the run list, then the current run |
| Browser tab 3 | The console: the final A/B, opened at its launch |

### Prepare the two opening printouts

Both commands make no model calls:

```bash
uv run python -c 'from shipharness.config import Settings; from shipharness.sandbox import default_policy, render_policy; print(render_policy(default_policy(Settings())))'
uv run python use-in-your-repo/skills/harness-setup/scripts/assess.py platform/teamtrack --out .shipharness/harness-assessment.html
```

The first prints the sandbox policy with the settings as loaded. The class profile raises the CPU
limit to 2 and the agent time limit to 420 s, the same for both arms:

```text
Sandbox policy (identical for both arms)
  network: none
  cpus: 1.0
  memory: 1024 MB (swap: 0 MB)
  pids: 256
  user: 1000:1000
  read-only root: yes
  writable: /work, /tmp
  capabilities dropped: ALL
  tool timeout: 120 s; run timeout: 300 s
  refused commands: 6 rules (network access)
```

The second assesses the bare TeamTrack. It begins with one summary line per area:

```text
Instructions       pass 0  partial 1  fail 5
State              pass 0  partial 0  fail 4
Scope              pass 1  partial 1  fail 3
Verification       pass 1  partial 1  fail 3
Session lifecycle  pass 0  partial 0  fail 5
```

## Section by section

Each section runs the same way. Minutes count from the start of the section.

| Minutes | What happens |
|---|---|
| 0-2 | Start slide: launch in terminal B at minute 1; open the newest run on screen 1 |
| 2-10 | The failure story and the Socratic question, while the run goes on |
| 10-30 | Four ideas and the cheat sheet; check terminal B at 15 |
| 30-40 | DEMO slide: the implementation notes, then the finished run on the console |
| 40-46 | What we measured: this section's results and screen 4 |
| 46-50 | Q&A, and the link to the section's demo page |

Section 3 runs two minutes ahead from the question on: the ideas at 9-28, the DEMO at 28-38, what
we measured at 38-44, and the Q&A at 44-50. The class deck is
[Harness Engineering for Coding Agents.pptx](../slides/Harness%20Engineering%20for%20Coding%20Agents.pptx);
its speaker notes are in the deck.

Only Section 4 opens with a poll, the one poll of the class, at 2:55-2:57: the room picks the final
feature (bulk close, watchers, or labels), then both Section 4 runs launch at 2:57. Section 4 has 45
minutes: the poll at 0-2, the launch at 2-4, the story and the question at 4-11, the ideas at 11-27,
the DEMO at 27-36, what we measured at 36-42, and the Q&A at 42-45.

Every section run ends before its DEMO slide, even with 2 more minutes for the class agent time
limit: show-1 by about 0:23, show-2 by about 1:23, demo-3 by about 2:15, show-4 by about 3:09 (DEMO
slides at 0:40, 1:40, 2:28, 3:22). Two final features launched at 2:57 end about 3:27, later if the
first one slows next to show-4: the latest timings were measured with each demo running alone, and
two runs at once make both slower. If terminal C has no `Cost:` line for the first feature at 3:10,
expect the second to end close to 3:40.

If the run is still going at minute 15, carry on with the ideas and the implementation notes. Then open the demo block on the
running screens: screen 1 shows `primary verdict ready: PASS` or `FAIL` as soon as the primary check
is done (the final, with no primary measure, shows `verdict ready` once all checks are done). A run
with an unwelcome result is a result: show it.

At the end of a run, terminal B prints one `A/B` line, one line per arm, and the `Cost:` line. Read
the session figure aloud. The exit code is 0 when every arm completed, 2 when an arm stopped at a
time or cost limit, and 1 when an arm ended in `ERROR`. Exit 2 is a result, not a broken command.

### Opening (0:00-0:10)

1. The problem slide: the four failures the referee checks in every run.
2. Why it happens, and the harness: one diagram, four layers, one sandbox for both arms.
3. The console tour: press `1` to `5` once each and name each screen.
4. Terminal B: `make doctor`. It never prints any part of a key.
5. Terminal B: the assessment printout. Say: "This is what the bare arm works with: no map, no
   progress file, no feature list. The rules themselves are in both arms."

No run before class leaked another org's cards, so there is no leak screenshot to show. Say so.

### Section 1: Instructions (0:10-1:00)

`make show-1` gives the harness arm the AGENTS.md map, the documents it points to, and the skills.
The ticket is org-wide issue search, next to a legacy handler with no tenant filter. The primary
verdict asks one question: did the change add a new tenant leak?

DEMO, after the implementation notes: screen 1 (the files placed, the map and a skill read, then the code),
screen 3 (files read, and the `r1_tenant` line, the tenant isolation check), screen 2 (the board, own-org cards only), screen 5
(trace links).

Say at the result: "This is one harness arm on one run. It shows the layer ran. It cannot show the
layer helped." Before class, no arm leaked in any run: no measurable difference
([evidence](evidence.md#section-1)).

Q&A: "The bare arm read the same rules and applied them. What would have to be true for the
map to earn its place?"

### Break (1:00-1:10)

Put the return time on the break slide. Nothing runs during the break.

### Section 2: State and sessions (1:10-2:00)

`make show-2 SESSION_BUDGET=12,38` stops session 1 after 12 turns. The harness writes the handoff,
and session 2 starts with an empty context and 38 turns. The primary verdict asks: did session 2
break or redo session 1's work?

DEMO, after the implementation notes: screen 1 (`Session 1 stopped`, then `Session 2 resumed`), screen 3 (Sessions: "Session 1 · 12
turns · turn_budget", then session 2 and the test phase; the state files are read with `cat`, so they
show under "All turns" on screen 1, not under Files read), screen 2 (the board with the comments panel), screen 5 (the first
wrong turn).

Say at the result: "Before class, neither arm failed continuity. The measure cannot fail when
session 1 leaves nothing to redo. In the medium- and low-effort rounds, 6 of 12 arms built nothing"
([evidence](evidence.md#section-2)).

Q&A: "Which state file would you keep for this model, and how would you measure it?"

### Section 3: Scope and sandbox (2:00-2:50)

This section runs a live A/B. Before class, three A/Bs on the version checks ticket showed a real gap: every bare
arm changed `app/services/errors.py`, a file outside the ticket's allowed paths. The scope layer
blocked the same edit in every harness arm. Bare 0 of 3 in scope, harness 3 of 3
([evidence](evidence.md#section-3)). Counting the demo runs of 2026-10-18 as well, screen 4's
"Measured before class" shows bare 1 of 10, harness 10 of 10
([evidence](evidence/s3.md#s3-screen-4-before-class)).

`make demo-3 FEATURE=version-checks` runs both arms at once. The harness arm has the instructions, state, and
scope layers. Each arm has its own sandbox with the same limits.

DEMO, after the implementation notes: screen 3, the Scope and sandbox column first. Look for `blocked app/services/errors.py`
under the harness arm and, usually, `changed app/services/errors.py` under the bare arm (9 of 10
runs before class; in the live guide run of 2026-10-18 the bare arm stayed in scope and both pills
read PASS, [evidence](evidence/s3.md#s3-guide-run)). Then the Verification
column: usually `Files outside the allowed paths (diff_scope): 1 new` against `0 new`. Then screen 1:
the pills on that measure, usually FAIL for bare and PASS for harness, and the harness decision
`block`, with the reason the agent read. Then Sandbox denials on screen 3. Then screen 4: the
before-class dots and this run's dots next to them.

Say at the result: "The guard enforces exactly what we measure, so the harness arm's zero is built
in. What the runs show is that, on this ticket, the bare agent left the allowed paths in 9 of 10
runs." If the bare arm stayed in scope in this run, say: "No file outside the ticket's paths. This is one
dot. Before class the bare arm left the allowed paths in 9 of 10 runs." Then:
"Before class, both arms failed Feature 4's own bar, every hidden test and every mutant, which the
terminal and screen 1 still show as secondary results. The guard keeps the change in scope. It does
not make the change correct."

If screen 3 lists a sandbox denial, show its reason code and command. If not, show the policy
printout and say: "The sandbox is the same for both arms. It is taught here, but it is never the
variable."

Q&A: "The guard won by construction. What would you measure next to it, so that a guard that
blocks everything cannot look good?"

Bridge to Section 4: in a `make demo-3` run on 2026-10-18 the harness arm stayed in scope but
shipped a board bug. Every board save returned HTTP 500, because it added the `version` form field
to `create_issue` instead of `edit_issue` ([evidence](evidence/s3.md#s3-two-tab-check)). Its
API-level hidden tests missed it, and Section 3's harness has no verification layer. Section 4's
gate, which includes the board check, is what would catch it.

### Break (2:50-2:55)

Five minutes. Put the return time on the break slide. Nothing runs during the break.

### Section 4: Verification (2:55-3:40)

Section 4 opens with the one poll of the class, a Live Zoom Poll at 2:55-2:57: which feature both
arms build in the final A/B, bulk close, watchers, or labels. Note the winner and the runner-up, and
close the poll before the launch. Read the session figure on the Section 3 `Cost:` line: run two
features only if it is $1.10 or less.

1. 2:57, terminal B: `make show-4`. Open its run in browser tab 2 right away.
2. 2:57, right after, terminal C: `make final` with `FEATURES=` set to the winner, a comma, and the runner-up,
   for example `make final FEATURES=watchers,bulk-close`. Always pass `FEATURES`: without it, make
   runs bulk close, then watchers. Open the
   newest run in browser tab 3, then go back to tab 2.

`make show-4` runs the version checks feature with all four layers. A run passes only with all 69 hidden tests and all 4
referee mutants killed by its own tests.

DEMO, after the implementation notes: screen 1 (the gate pills, then the test phase), screen 3 (the filter table and the
mutant table), screen 2 (the two-tab conflict panel).

Say at the result: "The gate checks what the agent can see. The hidden tests and the referee's
mutants stay out of its reach." Before class, neither arm passed the version checks ticket once: no measurable difference
([evidence](evidence.md#section-4)).

Q&A, four minutes: "What would a gate need to catch to earn its turns on this model?"

### Final results and wrap-up (3:40-4:00)

The final A/B started at 2:57. This block starts no run.

1. Terminal C: read each arm line and the session figure. The final has no primary measure, so
   `passed=True` does not mean the feature works. Read `hidden` and `mutants` instead.
2. Browser tab 3: screens 1, 3, and 5 for both arms, then screen 2.
3. Screen 4, then the all-results slide. Say: "One A/B is one dot. Read it next to the runs from
   before class, never alone."
4. Assignments, the skills, and the starter kit (`uv run shipharness init --target ../your-repo`).
5. References: the two References slides list every source cited in class, with its link.

If the final is not finished at 3:40, walk through its live screens 1 and 2 instead of step 2. Come
back to its screen 4 at the end.

## If something breaks

| What you see | Why | What to do |
|---|---|---|
| `x SHIPHARNESS_CLASS_DATE is not set` | The date step did not run | Repeat the date step |
| `x invalid` on a key line of `make doctor` | The key is wrong or revoked | Replace it in `.env`, run `make doctor` |
| `docker not found` | Docker is not running in Ubuntu | `sudo systemctl start docker` |
| `warm: incomplete` | An image build or start failed | `make images`, then `make warm` |
| Arm `ERROR` with `docker run failed` | Docker stopped, or an image is missing | Restart Docker, then replay the fallback |
| Arm `ABORTED: timeout` or `ABORTED: cap` | A time or cost limit | Nothing: the run is judged. Say which limit |
| Arm `ERROR`: OpenAI billing limit reached | The account is out of credit | Replay fallbacks for the rest of the class |
| Console header says `reconnecting` | The console stopped | Restart `make console` in terminal A, reload |
| Wrong final feature started | `FEATURES` missing or wrong | Ctrl+C in terminal C, launch again |

<a id="replay-procedure"></a>

Use a replay only when a live run failed for a reason outside the experiment: Docker, the network,
the OpenAI account, or time. A run the harness arm "lost" is a result.

1. Say: "This run failed for a reason outside the experiment. Here is the same command, recorded
   yesterday. The referee judges it live now."
2. Terminal B: `make replay RUN=ID`, with the fallback id in place of `ID`.
3. Press `H` for the run list, reload it, and open the top card. Every screen shows the red
   RECORDING badge.

Screen 2 of a replay shows broken images, because the replay does not copy the board screenshots.
Copy them once the replay's folder exists, then reload. `ID` is the fallback id and `NEW` is the
replay's id:

```bash
cp -a .shipharness/runs/ID/screenshots .shipharness/runs/NEW/
```

If Docker itself is down, a replay cannot run either. Open the recording at
`http://127.0.0.1:8765/run/` followed by the fallback id, and say "recorded yesterday" before you
switch screens. Never switch to `SANDBOX_MODE=none` for class results.

The full list of messages is in [troubleshooting.md](troubleshooting.md).

## After class

1. Run `uv run shipharness report`. It writes `exports/report.html`. Harness-in-action runs and
   replays stay out of the A/B report.
2. Back up `.shipharness/runs/` and `exports/`. Every class run counts, including aborted ones.
3. Write down each command's run id, its `Cost:` line, the times from screen 1, and the session
   total.

The review session runs two hours: about 25 minutes per assignment, then 20 minutes of open
questions.

| Time | Item |
|---|---|
| 0:00-0:25 | Assignment 1: Instructions |
| 0:25-0:50 | Assignment 2: State and sessions |
| 0:50-1:15 | Assignment 3: Scope and sandbox, with the hidden-diff reveal |
| 1:15-1:40 | Assignment 4: Verification |
| 1:40-2:00 | Open questions |

Each assignment's reference solution is in its `assignment/solution/` folder, with a step-by-step
walkthrough. The graders and their hidden cases are kept outside this repository. Count the lost
points per criterion before the session, and use those counts in each "common mistakes" slot.
