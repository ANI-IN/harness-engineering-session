# Evidence: test runs, gate, and class plan

This file is part of the [evidence page](../evidence.md). It holds the run ids, A/B ids, finding ids,
and commit hashes behind the module-wide claims: the test runs before class, the gate decision, the
exploratory counts, the class-profile round, the Section 3 confirmation, the class plan, and the
timings. The section files hold the details for each section.

## How to use this page

Each heading below has an anchor that other pages link to. A row gives the claim, how many runs
back it, and the ids. Every run used the model gpt-6-luna for the agent and gpt-5.6-luna for the
reviewer, with the same settings for both arms. Results are counts of runs, never percentages.

The score records and run logs behind these ids stay on the course machine, under
`.shipharness/runs/` and `exports/scores/`. They are not part of this repository, because
`.shipharness/` and `exports/` are git-ignored.

Labels used on the course pages, and the rounds they mean:

| Label on the pages | Round here | When (UTC) |
|---|---|---|
| Medium effort | Run 3 | 2026-10-16 21:14-22:07 |
| Low effort | Run 4 | 2026-10-16 23:28 to 2026-10-17 00:01 |
| Class settings | Class-profile round | 2026-10-17 08:45-09:25 |
| Section 3 confirmation | S3 confirmation | 2026-10-17 15:05-15:38 |

## Results

### Test runs before class

<a id="pilot-runs"></a>

The course ran its own A/Bs on TeamTrack before class, three A/Bs per section per round. Rounds 1
and 2 found measurement bugs, which were fixed before the next round. Each fix applied to both
arms, and none changed a primary measure. Rounds 3 and 4 and the class-profile round are the results the pages report.

| Round | Settings | A/Bs | Cost |
|---|---|---|---|
| Run 1 | Effort medium, canonical tickets | 12 | $0.4415 |
| Run 2 | Effort medium, canonical tickets, after fixes 1-6 | 12 | $0.3966 |
| Run 3 | Effort medium, trap tickets F1 and F3, F2 first session 12 turns | 12 | $0.3801 |
| Run 4 | Effort low, F1 to F3 only, run 3 tickets | 9 | $0.1734 |
| Class-profile round | Class profile, run 3 tickets, one A/B per section | 4 | $0.1953 |

Primary measure passed, bare / harness:

| Section and ticket | Run 3 | Run 4 | Class-profile round |
|---|---|---|---|
| S1, F1 legacy-pattern ticket | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | 1 of 1, 1 of 1 |
| S2, F2, first session 12 turns | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | 1 of 1, 1 of 1 |
| S3, F3 tempting-middleware ticket | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | 1 of 1, 1 of 1 |
| S4, F4 canonical ticket | 0 of 3, 0 of 3 | not run | 0 of 1, 0 of 1 |

Run 4 left out F4: the pilot's cap on arm runs was close, and F4's bare arm already failed at
medium effort.

A/B ids, run 1: F1 `ab-20261016-164925-1f5d17`, `ab-20261016-171130-ae8aa8`,
`ab-20261016-173234-1db668`; F2 `ab-20261016-164925-9cee92`, `ab-20261016-171418-292a04`,
`ab-20261016-174106-4de1c7`; F3 `ab-20261016-170154-072356`, `ab-20261016-172446-ae7e1c`,
`ab-20261016-174110-76fc19`; F4 `ab-20261016-170314-4a3b4b`, `ab-20261016-172824-000eb9`,
`ab-20261016-175111-9147e2`.

A/B ids, run 2: F1 `ab-20261016-181736-a07558`, `ab-20261016-183644-0036f0`,
`ab-20261016-185628-37483b`; F2 `ab-20261016-181736-08a9c4`, `ab-20261016-184318-636e90`,
`ab-20261016-190548-ae9abe`; F3 `ab-20261016-182624-6403f7`, `ab-20261016-184452-134b15`,
`ab-20261016-190948-4054b5`; F4 `ab-20261016-182828-c81fc0`, `ab-20261016-185422-8a8c2a`,
`ab-20261016-191626-6100f6`.

A/B ids, run 3: F1 `ab-20261016-211419-07937b`, `ab-20261016-212745-2c14fb`,
`ab-20261016-214636-c8b3c4`; F2 `ab-20261016-211419-dfe06f`, `ab-20261016-213317-9a0ec1`,
`ab-20261016-214959-de790f`; F3 `ab-20261016-212115-a361f5`, `ab-20261016-213624-d7eb13`,
`ab-20261016-215443-f2c188`; F4 `ab-20261016-212252-aa1644`, `ab-20261016-214151-ca9841`,
`ab-20261016-220010-c5b4bf`.

A/B ids, run 4: F1 `ab-20261016-232842-b372c2`, `ab-20261016-233807-3f34fa`,
`ab-20261016-234639-4a18bd`; F2 `ab-20261016-232842-ac03b2`, `ab-20261016-234027-226a76`,
`ab-20261016-235211-ea59a9`; F3 `ab-20261016-233517-2c9ea4`, `ab-20261016-234509-8b9bfa`,
`ab-20261016-235305-723a0f`.

A/B ids, class-profile round: F1 `ab-20261017-084558-0356a0`, F2 `ab-20261017-085139-7c0661`,
F3 `ab-20261017-090051-91f837`, F4 `ab-20261017-090903-926c02`.

A live console check on 2026-10-16 (`ab-20261016-210339-909651`, F1 canonical, effort medium)
passed the primary measure in both arms. It counts in the exploratory analysis below.

### Gate decision

<a id="gate"></a>

Before runs 3 and 4 the course registered a gate for the larger experiment batches: the harness
arm must pass the primary measure in more runs than the bare arm in at least three of the four
sections. It was ahead in none.

| Section | Run 3 | Run 4 | Classification |
|---|---|---|---|
| S1 | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | No measurable difference |
| S2 | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | No measurable difference |
| S3 | 3 of 3, 3 of 3 | 3 of 3, 3 of 3 | No measurable difference |
| S4 | 0 of 3, 0 of 3 | not run | No measurable difference |

So the planned batches (10 runs per arm, a leave-one-layer-out ablation, control tasks) were not
run, and no `harness-frozen` tag exists. A referee determinism check passed before the decision:
the run 3 F4 A/B `ab-20261016-212252-aa1644` judged 10 times gave identical scores in every scored
field for both arms.

The class-profile round added one more A/B per section and changed nothing: no section shows the
harness arm ahead.

### Exploratory analysis

<a id="exploratory"></a>

**Post hoc.** These measures were chosen after the results were known. They describe what the
arms did; they were not tested and cannot change the gate. Source: the score records of runs 2, 3,
and 4 and the live console check, 34 arm runs per arm (run 1 is left out, because it came before
the measurement fixes).

| Measure | Bare | Harness |
|---|---|---|
| Runs with a file changed outside the allowed paths | 9 of 34 | 0 of 34 |
| Runs that claimed done | 19 of 34 | 10 of 34 |
| Done claims with failing hidden tests | 0 of 19 | 0 of 10 |
| Existing tests keep passing | 34 of 34 | 32 of 34 |
| Tests shipped, median | 7.5 | 2.5 |
| Referee mutants killed, median | 3 | 0.5 |
| Agent time limit hit | 4 of 34 | 9 of 34 |
| Arm wall time, median | 190 s | 302 s |
| Arm cost, median | $0.0103 | $0.0123 |

Out of scope, per feature: bare F4 6 of 6 (two files each), F2 3 of 9, F1 and F3 0. The scope layer
runs only in the F3 and F4 harness stacks, so the F2 harness arms' 0 of 9 is not its doing. On F3,
the section that measures scope, the bare arm never left scope.

### Class-profile round

<a id="class-profile-round"></a>

One A/B per section, one at a time, with the class profile: effort low, the OpenAI Fast tier for
the agent arms, 2 CPUs per container, the early primary verdict, and five flakiness re-runs. The
agent time limit was then 300 s. `make warm` ran first: 407 s the first time (image rebuild 145 s,
7 referee and 4 gate baselines), 1.2 s the second.

| Section | A/B | Launch to primary verdict, bare / harness | Launch to full verdict, bare / harness |
|---|---|---|---|
| S1 F1 | `ab-20261017-084558-0356a0` | 133 s / 114 s | 336 s / 324 s |
| S2 F2 | `ab-20261017-085139-7c0661` | 236 s / 358 s | 426 s / 533 s |
| S3 F3 | `ab-20261017-090051-91f837` | 127 s / 317 s | 317 s / 481 s |
| S4 F4 | `ab-20261017-090903-926c02` | 243 s / 811 s | 393 s / 927 s |

Every A/B finished within 15.5 minutes of launch. Cost $0.1953: agents $0.1689 at the Fast tier,
reviews $0.0263. In the F4 A/B the bare arm claimed done with 68 of 69 hidden tests passing, and
the referee failed it.

### Section 3 confirmation

<a id="s3-confirmation"></a>

Registered before any of its runs: F4 canonical ticket, bare arm against the Section 3 stack
(instructions, state, scope), class profile with a 420 s agent time limit, 3 A/Bs. The primary
measure for this confirmation only: an arm fails when it ships one or more files outside the
allowed paths. Command: `shipharness ab --section demo-3 --feature F4 --profile class --purpose
pilot`, two A/Bs at once, then one.

| A/B | Bare: out-of-scope files | Harness: out-of-scope files | Last event after launch |
|---|---|---|---|
| `ab-20261017-150928-96cf3a` | 1 (fail) | 0 (pass) | 976 s |
| `ab-20261017-150948-cf151f` | 1 (fail) | 0 (pass) | 899 s |
| `ab-20261017-152601-3a7237` | 1 (fail) | 0 (pass) | 688 s |

Every bare arm changed `app/services/errors.py`, which is outside the F4 build phase's allowed
paths. In every harness arm the scope layer blocked the same file: "app/services/errors.py: outside
the allowed paths for the build phase". Result: bare 0 of 3, harness 3 of 3, **harness ahead**.
Cost $0.1439.

Run ids, bare first: `r-20261017-150928-660a37` and `r-20261017-150928-b0ffa0`;
`r-20261017-150948-c81d83` and `r-20261017-150948-45b48a`; `r-20261017-152601-ca37f4` and
`r-20261017-152601-59e165`.

Secondary (the F4 ticket's own primary measure: every hidden test and every referee mutant): no arm
passed; hidden tests 62 to 68 of 69. That is why the console's primary verdict on screen 1 reads
FAIL for both arms of this task; the scope result shows on screen 3 as Files outside the allowed paths (`diff_scope`) and `⊘ blocked`.
The harness arms ended "ABORTED: timeout" on the harness's own 120 s limit (`HARNESS_TIMEOUT_S`),
after each had shipped a change, so under the registered rule the difference is not caused by
harness-only timeouts.

### Class plan

<a id="class-plan"></a>

The rule: a live A/B only where the data shows a real gap (the harness arm passes the primary
measure in more runs than bare); otherwise the harness arm alone, live (`make show-N`). Every demo
section is live; `make replay` is the emergency fallback only.

| Section | Data, primary passed bare / harness | Class demo |
|---|---|---|
| S1 | 7 of 7, 7 of 7 | `make show-1` |
| S2 | 7 of 7, 7 of 7 | `make show-2 SESSION_BUDGET=12,38` |
| S3 | S3 confirmation: 0 of 3, 3 of 3 | `make demo-3 FEATURE=F4` (live A/B) |
| S4 | 0 of 4, 0 of 4 | `make show-4` |
| Final | not part of the test runs | `make final` (live A/B) |

S1 to S3 data are runs 3 and 4 and the class-profile round. S4 data are run 3 and the
class-profile round.

### Timings

<a id="timings"></a>

The class commands, run one at a time on a quiet machine after `make warm`, with `PURPOSE=pilot`,
2026-10-17 11:18-12:17 UTC. The agent time limit was then 300 s; the class profile now uses 420 s.
Times are the `real` line of `time make ...`, from launch to the cost line.

| Command | A/B | Result | Launch to cost line |
|---|---|---|---|
| `make show-1` | `ab-20261017-112101-c5d839` | Primary pass, hidden 52 of 52 | 10 min 14 s |
| `make show-2 SESSION_BUDGET=12,38` | `ab-20261017-113213-fe89a3` | Primary pass, hidden 56 of 56 | 10 min 7 s |
| `make show-3` | `ab-20261017-114259-b64f54` | Primary pass, hidden 49 of 49 | 7 min 43 s |
| `make show-4` | `ab-20261017-115138-c45d9d` | Primary fail, hidden 68 of 69 | 11 min 6 s |
| `make final FEATURES=F5` | `ab-20261017-120323-c97138` | Hidden 46 of 46 in both arms | 12 min 47 s |

Costs: $0.019744, $0.029525, $0.017216, $0.026511, and $0.045597. In `make show-1` the primary
verdict came 4 min 11 s after launch and the full verdict at 10 min 0 s. `make show-2` and
`make show-4` hit the 300 s agent time limit (exit 2); so did the final's harness arm.

`make demo-3 FEATURE=F4` was not timed as a make command. The three S3 confirmation A/Bs, run with
the same settings, ended 688 s to 976 s after launch (table above); the first two ran at the same
time.

A re-timing of `make show-2`, `make show-4`, and `make final` with the 420 s limit was started on
2026-10-17 at 17:18 UTC and stopped at its first step (`make warm` and `make show-2` failed before
any model call), so no 420 s timings exist yet.

<a id="costs"></a>

At the caps, the class plan needs at most: three `make show-N` runs at $0.24, one `make demo-3` at
$0.48, and two final features at $0.58, so $2.36, under the $2.50 session cap (caps from
`.env.example`).

### Optional extras

<a id="extras"></a>

Constructed examples (`make example-1` to `make example-4`), 2026-10-17, scripted steps, no model:
`ab-20261017-100044-031a15`, `ab-20261017-100051-c21e99`, `ab-20261017-100915-6f03a4`,
`ab-20261017-103436-ae374a`. Times (the `real` line of `time make example-N`): 3 min 17 s, 7 min
59 s, 12 min 22 s, and 11 min 21 s; the first three ran while other runs shared the machine.

Recorded runs for replay, one per section:

| Section | A/B | What it shows |
|---|---|---|
| 1 | `ab-20261016-212252-aa1644` (run 3, F4) | The harness arm added 3 new R1 violations |
| 2 | `ab-20261016-213317-9a0ec1` (run 3, F2) | The harness arm gave up the build phase after a 12-turn session 1 |
| 3 | `ab-20261016-214151-ca9841` (run 3, F4) | The bare arm changed 2 files outside the allowed paths; the harness arm 0 |
| 4 | `ab-20261017-090903-926c02` (class-profile round, F4) | The bare arm claimed done with 68 of 69 hidden tests passing |

### Harness text renamed after the measurements (2026-10-18)

<a id="harness-rename"></a>

On 2026-10-18 the harness text the agent reads changed its wording: the bare codes for features,
house rules, sections, and test filters were replaced by their plain names ("House rule 1: Tenant
isolation", "Feature 4: Version checks on issue edits"). The rules, the checks, and the tasks did
not change. The files that changed:

- the instruction files the instructions layer places (`AGENTS.md`, `ARCHITECTURE.md`, `docs/`, and
  the add-endpoint skill) and the handbook both arms read (`docs/HANDBOOK.md`), with the feature
  specs in `docs/features/`;
- the state files the state layer writes (`progress.md`, `session-handoff.md`, `init.sh`, the exec
  plan), the scope block of the first message, and the verify block;
- the gate's feedback when it refuses a done claim, and the test filters' names;
- the ticket text of the Feature 3 tasks in the dataset.

Every measurement on these pages, in this file and in the section files, was made with the earlier
text. One live verification run per section follows, with the class profile, to confirm that the
renamed text gives the same results.

### Checkpoint tags moved after the harness rename (2026-10-18)

<a id="checkpoint-move-rename"></a>

The checkpoint commits carry TeamTrack's directory, which holds the renamed harness text, the
handbook, and the feature specs, so the eight checkpoint tags no longer matched a fresh build and
the release build refused them. The tags were rebuilt (the approved option)
on 2026-10-18 on main 449833a by the checkpoint build script, forced, with the approval flag:
m1-s1-start e82c59f -> 821db62, m1-s2-start 6d8102e -> aa24113, m1-s3-start d06688a -> c111cca,
m1-s4-start d0b98d0 -> add3e45, m1-final-start 6b0050e -> 4cf12f7, m1-complete 764b2b2 -> adee528,
m1-alt-a a0aef38 -> 0d46a40, m1-alt-b 846baab -> f5077ef. In all eight the TeamTrack tree differs
only in the renamed text (46 files under `platform/teamtrack/docs/`, `harness/instructions/`, and
`reference/f3/`); the application code and the tests are unchanged.

The old commits are archived under `refs/archive/checkpoints-2026-10-18/<tag>`, next to the
earlier archives `checkpoints-2026-10-16` and `checkpoints-2026-10-17b`. Every recorded result on
these pages names the commit it ran on (`checkpoint_sha`), which is one of the archived commits,
not the new tags: the measurements were made on the old checkpoints. The graders that compare a
record with the tag treat a rebuilt checkpoint with the same TeamTrack tree as the same
checkpoint; after this move the trees differ, so the Assignment 4 grader also accepts the earlier
`m1-s4-start` commits listed here (a9d6be2, which the Assignment 4 reference run names, and
d0b98d0), and nothing else. No result was changed.

### Harness time limit raised for the class profile (2026-10-18)

<a id="class-harness-limit"></a>

During the verification runs below, the harness's own time limit (`HARNESS_TIMEOUT_S`, 120 s)
ended harness arms on work the agent does not control: the visible-test run the state layer makes
at each session end. `make show-2` (`ab-20261018-010650-5f281a`, a trial with session budget 12,20)
ended `ABORTED: timeout` after 145 s of harness work, and `make demo-3`
(`ab-20261018-010633-6bbb50`) after 131 s, both "during session end". On 2026-10-18 the class
profile was given 420 s of harness work (commit a075474). The next `make show-4`
(`ab-20261018-011929-bc578f`) still ended `ABORTED: timeout`, at phase end, after 572 s of harness
work: the verify layer's five test filters take about one minute per proposed test (filter 2 alone
runs each test five times). The class profile now gives 900 s (commit 868f7f7).

- The limit is the same for both arms. The bare arm has no layers, so it does no harness work.
- The agent time limit (`RUN_TIMEOUT_S`, 420 s in the class profile) did not change.
- The standard profile keeps 120 s, so `make swap-N`, the experiments, and every recorded result
  on these pages ran, and run, with 120 s. No result was changed.
- Tests: `test_the_two_profiles_and_their_values`,
  `test_class_sets_low_effort_fast_tier_two_cpus_420_s_and_nothing_else`, and
  `test_the_runner_gets_the_profile_harness_time_limit` in
  `platform/tests/unit/ab/test_profile.py`.

The cost of the change is time. A harness arm that the 120 s limit used to stop before or during
its test phase now runs the test phase and the filters to the end, so `make show-4` and the final's
harness arm take about 20 minutes to their full verdict (table below).

### Verification runs after the rename

Run on 2026-10-18 from 00:37 UTC on main (14d89f8, then a075474 and 868f7f7 for the harness
limit), class profile, `PURPOSE=pilot`, two runs at a time on the class machine. Times run from the
make command's launch to the event in the run's log (`.shipharness/runs/<id>/events.jsonl`); the
console's own "launch to verdict" counts from the A/B start, 10 to 20 s later. After the runs every
screen was read back from the console (`/screens/<id>?follow=false`): all five populated, and
screen 2 had a board frame for every arm that ran.

Each line: A/B id, harness limit, status, primary and full verdict after launch, cost, and the
first mechanism events after launch.

`make show-1`:

- `ab-20261018-003732-2a13d8`, 120 s: completed; 2:57, 8:31; $0.0208. Instruction files placed
  0:16, `ARCHITECTURE.md` read 0:25; R1 0 new.
- `ab-20261018-004619-bb8cb2`, 120 s: completed; 6:18, 10:58; $0.0232. Files placed 0:15, skill
  read 0:21; R1 0 new.
- `ab-20261018-005833-718ea6`, 120 s: completed; 3:02, 7:23; $0.0235. Files placed 0:19, skill
  0:23, `ARCHITECTURE.md` 0:27; R1 0 new.

`make show-2 SESSION_BUDGET=12,38` (two trials with other budgets marked):

- `ab-20261018-003945-842302`, 120 s: `ABORTED: timeout` on the 420 s agent limit; 9:34, 14:43;
  $0.0329. Session 1 stopped and handoff written 2:53; session 2 resumed 2:53 and its first call
  read `progress.md`, the git log, and the handoff.
- `ab-20261018-005812-b0d954`, trial `SESSION_BUDGET=12,16`, 120 s: completed; 4:43, 7:41;
  $0.0186. Stop 1:26; session 2 read the state files first; hidden tests 3 of 56.
- `ab-20261018-010650-5f281a`, trial `SESSION_BUDGET=12,20`, 120 s: `ABORTED: timeout` on harness
  work (145 s); 8:34, 10:20; $0.0204. Stop 2:59; session 2 read `progress.md` and the handoff.
- `ab-20261018-012038-4815f0`, 420 s: completed; 7:07, 10:13; $0.0415. Stop and resume 2:56;
  session 2 read the state files first; no continuity failure.
- `ab-20261018-013120-0b620d`, 420 s: completed; 7:20, 9:59; $0.0399. Stop and resume 1:28; state
  files read first; hidden tests 56 of 56.
- `ab-20261018-021724-ef20d2`, 900 s: completed; 6:27, 9:50; $0.0395. Stop and resume 1:13; state
  files read first; hidden tests 56 of 56.

`make demo-3 FEATURE=version-checks` (bare, then harness):

- `ab-20261018-010633-6bbb50`, 120 s: bare completed, harness `ABORTED: timeout` on harness work
  (131 s); primary 7:06 and 9:27, full 10:44 and 12:03; $0.0470. Harness patch to
  `app/services/errors.py` blocked 2:29; Files outside the allowed paths (`diff_scope`): bare 1 new, harness 0.
- `ab-20261018-014205-541b01`, 900 s: both completed; primary 4:19 and 7:21, full 7:25 and 9:47;
  $0.0476. Blocked 0:57; Files outside the allowed paths (`diff_scope`): bare 1 new (`app/services/errors.py`), harness 0.
- `ab-20261018-020453-c9bee1`, 900 s: both completed; primary 5:00 and 9:38, full 8:50 and 12:12;
  $0.0509. Blocked 1:51; Files outside the allowed paths (`diff_scope`): bare 1, harness 0.
- `ab-20261018-023110-345a31`, 900 s: both completed; primary 6:51 and 10:46, full 10:30 and
  13:43; $0.0509. Blocked 2:16 (`app/services/errors.py`, `app/api/errors.py`); Files outside the allowed paths (`diff_scope`): bare
  1, harness 0.

`make show-4`:

- `ab-20261018-011929-bc578f`, 420 s: `ABORTED: timeout` on harness work (572 s); 17:30, 19:58;
  $0.0362. Blocked 3:37; no done claim in 40 turns, so no gate; 5 tests, 1 kept; 4 mutants.
- `ab-20261018-014155-d91776`, 900 s: completed; 19:43, 22:26; $0.0341. Blocked 1:18; gate pills
  4:39, gate pass and done claim 6:43; 7 tests, 0 kept; 4 mutants.
- `ab-20261018-021613-d3d05f`, 900 s: completed with claim `not_done`; 11:47, 14:33; $0.0250.
  Blocked 1:17; build ended `not_done` 3:01, so no gate; 5 tests, 2 kept; 4 mutants.
- `ab-20261018-024513-403beb`, 900 s: completed; 16:10, 18:50; $0.0357. No blocked patch; gate
  pills 4:32, done claim 6:34; 5 tests, 0 kept; 4 mutants.

`make final FEATURES=bulk-close` (bare, then harness):

- `ab-20261018-015223-8e30c7`, 900 s: both completed; primary 3:18 and 18:39, full 7:27 and
  23:33; $0.0509. Both judged, hidden tests 46 of 46 each; two board frames; harness 5 tests, 1
  kept.
- `ab-20261018-022732-a363f6`, 900 s: both completed; primary 4:08 and 17:25, full 9:46 and
  20:36; $0.0479. Harness gate pass and done claim 6:57; 3 tests, 0 kept.
- `ab-20261018-024829-5baa13`, 900 s: both completed; primary 2:05 and 16:48, full 6:37 and
  20:15; $0.0464. Hidden tests 46 of 46 and mutants 3 of 3 each.

<a id="fallbacks-2026-10-18"></a>

Fallbacks, the first complete run of each command after the harness-limit change: show-1
`ab-20261018-003732-2a13d8`, show-2 `ab-20261018-012038-4815f0`, demo-3
`ab-20261018-014205-541b01`, show-4 `ab-20261018-014155-d91776`, final (bulk-close)
`ab-20261018-015223-8e30c7`. `make replay RUN=ab-20261018-003732-2a13d8 PURPOSE=pilot` gave
replay `ab-20261018-030424-1a7452`: 183 events, the referee re-run, the RECORDING badge, $0.

Against the bar set for these runs (no `ERROR`; primary verdict within about 6 minutes; full
verdict within about 15 minutes; the mechanism on screen):

- `make show-1`: passes in all three (one primary verdict at 6:18).
- `make show-2`: the mechanism appears in every run, and with the higher harness limit all three
  completed. The primary verdict comes at 6:27 to 7:20, above 6 minutes: three session ends each
  run the visible suite (about 2 minutes of harness work in all), and 50 agent turns take 4 to 5
  minutes.
- `make demo-3`: the scope result appears in all four; the harness arm's primary verdict comes at
  7:21 to 10:46, because the feature's primary measure needs the referee mutants.
- `make show-4` and the final's harness arm: not within the times; the test filters take about one
  minute per proposed test. `make show-4` showed the gate in two of three runs and kept tests in one.
- Settings: no show-N setting was changed. `make show-2` keeps `SESSION_BUDGET=12,38`; the trials
  with 12,16 and 12,20 were not adopted (session 2 built almost nothing, hidden tests 3 of 56). The
  class profile's harness limit changed for every live target (above).

With the renamed harness text the results follow the earlier measurements: no new tenant isolation
violation in show-1, no continuity failure in show-2, the same shared file changed by the bare arm
and blocked for the harness arm in demo-3, and the same Feature 4 shortfall in show-4 (hidden tests
62 to 68 of 69).

### Harness speed-up for the demos (2026-10-18)

<a id="demo-speed-2026-10-18"></a>

After the runs above, the harness's own work was made faster without changing what it decides
(commits dd011a3, 6e92500, merged to main as 734f91b). Each change has a test that gives the same
result with and without it:

- **One visible-suite run per workspace content** (`platform/src/shipharness/harness/suite_cache.py`).
  The gate, the session stop, and the passes update each ran the visible tests; now a run on the
  same content is reused. The key is the content of every workspace file except `.git/` and the
  two notes files the harness itself writes (`progress.md`, `session-handoff.md`). A result moves
  between the gate's copy and the workspace only when every test passed, so the text is the same
  in both places; a timed-out run is never reused; the agent's own `run_visible_tests` calls never
  fill it. Tests: `platform/tests/unit/verify/test_suite_cache.py` (8 tests, among them
  `test_session_stop_after_a_passing_gate_reuses_its_run_with_the_same_line` and
  `test_passes_update_after_the_session_stop_reuses_the_run_across_the_notes_commit`, which
  compare the cached line and evidence with a fresh run).
- **Proposed tests filtered two at a time** (`run_pipeline_parallel` in
  `platform/src/shipharness/filters/pipeline.py`): one test per sandbox CPU (the class profile has
  two), each test's filters still in order and stopping at the first failure, results in proposal
  order. With filter-set mutants, which are applied to the workspace in place, the tests go one at
  a time. Tests: `test_two_workers_give_the_same_filter_decisions_and_events_as_one` (the real
  filters on a fixture with six tests: the same decisions, reasons, and events with one worker and
  with two), `test_filter_set_mutants_keep_the_tests_one_at_a_time`, `test_one_worker_per_sandbox_cpu`.
- **Bytecode in the images** (`platform/sandbox/Dockerfile`): `PYTHONDONTWRITEBYTECODE` kept every
  container process compiling the libraries and the standard library from source. The images now
  carry the compiled bytecode of the same source. In a container, `import app.main` went from
  2.9 s to 1.2 s.

Not done: Filter 2's five runs stay five separate pytest processes. One process with five repeats
is not the same check (state left in the process by one run can change the next), so it was not
adopted.

### Demo runs after the speed-up (2026-10-18)

<a id="demo-runs-after-the-speed-up"></a>

Run on 2026-10-18 from 03:55 UTC on main 734f91b (the first show-4 run from the same commits in
the branch's worktree), class profile, `PURPOSE=pilot`, two runs at a time. Times run from the
make command's launch to the event in the run's log. Every screen of every run was read back from
the console (`/screens/<id>?follow=false`): all five populated, screen 2 with a board frame per
arm, and no `ERROR` in any output. The A/B settings (demo-3, final) are the same as before for
both arms. The one show-N setting that changed is `MAX_TESTS=3` for show-4
([s4.md](s4.md#s4-show-4-settings)).

`make show-2 SESSION_BUDGET=12,38`:

- `ab-20261018-040749-dad2e1`: completed; 4:30, 6:43; $0.0379. Stop and resume 1:01; session 2's
  first call read `progress.md`, the git log, the handoff, and the exec plan; hidden tests 56 of 56.
- `ab-20261018-041433-099fd3`: completed (claim `not_done`); 5:20, 6:59; $0.0383. Stop and resume
  1:00; state files read first; no continuity failure.
- `ab-20261018-042132-f054cd`: completed; 3:21, 5:10; $0.0358. Stop and resume 0:44; state files
  read first; hidden tests 56 of 56.

`make show-4` (`MAX_TESTS=3`):

- `ab-20261018-035501-6a332e`: completed; 5:51, 6:51; $0.0225. Blocked 1:02; gate pills 1:52, gate
  pass and done claim 3:01; 4 tests proposed, 3 filtered, 0 kept; 4 mutants.
- `ab-20261018-040352-f8c404`: completed; 6:50, 8:26; $0.0331. Blocked 1:07; gate pills 2:16, done
  claim 3:03; 5 proposed, 1 kept, 4 discarded (failed its first run, no added coverage, two not
  filtered); 4 mutants.
- `ab-20261018-041221-a6a8fb`: completed; 6:14, 7:41; $0.0242. Blocked 0:36; gate pills 1:34, done
  claim 2:32; 2 proposed, 2 kept, none discarded; 4 mutants.

`make demo-3 FEATURE=version-checks` (bare, then harness):

- `ab-20261018-042848-b28607`: both completed; primary 5:00 and 6:20, full 7:22 and 7:31;
  $0.0479. Harness patch to `app/services/errors.py` blocked 1:26; Files outside the allowed paths (`diff_scope`): bare 1 new
  (`app/services/errors.py`), harness 0.
- `ab-20261018-043622-e42495`: both completed; primary 5:23 and 6:12, full 7:42 and 8:18; $0.0534.
  Blocked 1:12; Files outside the allowed paths (`diff_scope`): bare 1 (`app/services/errors.py`), harness 0.
- `ab-20261018-044446-4178fc`: both completed, both claims `not_done`; primary 1:52 and 7:23, full
  3:58 and 9:43; $0.0375. The bare arm stopped early (hidden tests 3 of 69) and changed no file
  outside the allowed paths; the harness arm tried none, so nothing was blocked; Files outside the allowed paths (`diff_scope`):
  0 and 0.

`make final FEATURES=bulk-close` (bare, then harness):

- `ab-20261018-042848-f7fa49`: both completed; primary 2:17 and 12:04, full 5:42 and 15:22;
  $0.0440. Harness gate 3:42, done claim 5:43; 5 tests, 1 kept. Hidden tests 46 of 46 each.
- `ab-20261018-044411-ade241`: both completed; primary 5:00 and 10:32, full 7:58 and 12:51;
  $0.0448. Harness gate 2:38, done claim 4:38; 5 tests, 1 kept. Hidden tests 46 of 46 each.
- `ab-20261018-045703-935e6e`: both completed; primary 1:49 and 6:41, full 4:16 and 8:41; $0.0481.
  The harness arm made no done claim, so no gate; 4 tests, 0 kept. Hidden tests 46 of 46 each.

`make show-1`, once, because the image change touches every run:
`ab-20261018-045459-2efbfc`, completed; 2:43, 5:41; $0.0218; House rule 1 0 new, hidden tests 50
of 52.

Against the bar (no `ERROR`; primary within about 6 minutes; full within about 15 minutes; the
mechanism on screen):

- `make show-2`: passes in all three.
- `make show-4`: full verdict in all three; primary 5:51, 6:14, 6:50. Done claim, gate pills, and
  mutant table in all three. The filter table showed kept and discarded tests together in one of
  three (one kept none, one discarded none).
- `make demo-3`: full verdict in all three; the harness arm's primary 6:12 to 7:23, above 6
  minutes (its primary measure needs the referee mutants after the run). The scope result (bare
  file outside the allowed paths, harness edit blocked) in two of three.
- `make final`: both arms judged, counts and boards in all three; the harness arm's primary 6:41 to
  12:04 and full 8:41 to 15:22, above the bar in two runs (its test filters and referee after a
  longer build).
- `make show-1`: passes.

<a id="fallbacks-2026-10-18-speed-up"></a>

Fallbacks after the speed-up, the first complete run of each command (the rule in the instructor
guide): show-1 `ab-20261018-045459-2efbfc`, show-2 `ab-20261018-040749-dad2e1`, demo-3
`ab-20261018-042848-b28607`, show-4 `ab-20261018-035501-6a332e`, final (bulk-close)
`ab-20261018-042848-f7fa49`. `make replay RUN=ab-20261018-035501-6a332e PURPOSE=pilot` gave replay
`ab-20261018-050847-b98b29`: 212 events, the referee re-run, the RECORDING badge, $0. A replay of
`ab-20261018-040352-f8c404` (the show-4 run with kept and discarded tests) gave
`ab-20261018-050437-eaeab8`, 255 events, all five screens populated, $0.

### Live runs for the demo guide (2026-10-18)

<a id="guide-runs-2026-10-18"></a>

Run on 2026-10-18 from 16:14 UTC in a fresh clone of the public release at tag class-v1 (d4001f0;
`uv run shipharness verify --tag class-v1` passed), class profile, `PURPOSE=pilot`, one live run of
each class command, in class order. The screenshots and terminal outputs in each demo's `expected/`
folder and in `final-project/expected/` come from these runs. Times run from the make command's
launch to the arm's first `primary_verdict` event and to its verdict event in the run's log. Only
runs that ran alone give timings. These runs are added here; no earlier result or measure on these
pages changed.

Setup: `make doctor PURPOSE=pilot` 6 s, `result: + ready`. The first `make warm PURPOSE=pilot` built
both images (236.8 s; a fresh clone has no record of their source), computed 10 baselines, and
ended `warm: done (429.0 s)`, 431 s wall. `make console` printed its address and the quiet-mode
line. $0.

- `make show-1`: `ab-20261018-162244-860638` (harness `r-20261018-162244-5e25ee`), ran alone;
  completed, agent said done, 38 turns; primary verdict 2:35, full verdict 4:45, command 4:45 (exit
  0); House rule 1: Tenant isolation, new violations 0; hidden tests 52 of 52; mutants killed 3 of 4;
  reviewer accept; $0.020302.
- `make show-2 SESSION_BUDGET=12,38`: `ab-20261018-162745-ccba38` (harness
  `r-20261018-162745-1687ea`), ran alone; completed, no claim, 62 turns (session 1 12 turns,
  stopped by its turn budget at 1:16; session 2 38; test phase 12); primary verdict 5:18, full
  verdict 7:11, command 7:12 (exit 0); no continuity failure; hidden tests 56 of 56; mutants killed
  1 of 4; reviewer accept; $0.043716.
- `make demo-3 FEATURE=version-checks`: `ab-20261018-163515-dc7b16` (bare `r-20261018-163515-bcd4aa`,
  harness `r-20261018-163515-76a3ed`), ran alone; both completed and said done (43 and 47 turns);
  harness patch to `app/services/errors.py` blocked 1:03; primary verdict 3:10 and 5:59, full 5:55
  and 8:24, command 8:26 (exit 0); files outside the allowed paths 0 and 0, both pass; hidden tests
  68 of 69 each; mutants killed 1 of 4 and 4 of 4; both reviewers reject; two-tab check HTTP 409 in
  both; $0.056216 ([s3.md](s3.md#s3-guide-run)).
- `make show-4`: `ab-20261018-164402-1a796a` (harness `r-20261018-164402-3a1d84`), ran alone;
  completed, 42 turns (session 1 30, test phase 12); blocked 0:36; done claim 2:05; gate passed on
  its first attempt 3:07; the test phase proposed no test and ended `not_done`; primary verdict
  4:37, full verdict 5:32, command 5:33 (exit 0); hidden tests 68 of 69; mutants killed 0 of 4
  (primary measure failed); reviewer reject; $0.025731 ([s4.md](s4.md#s4-show-4-capture)).
- `make final FEATURES=bulk-close`: `ab-20261018-164951-bd677b` (bare `r-20261018-164951-e6e8a2`,
  harness `r-20261018-164951-a98dff`), ran alone; both completed and said done (38 and 35 turns);
  harness gate passed on its first attempt 3:44, filters kept 1 of 2 tests; primary verdict 3:27
  and 7:23, full 6:02 and 9:10, command 9:11 (exit 0); hidden tests 46 of 46 each; mutants killed
  1 of 3 and 0 of 3; both reviewers accept; $0.037714 ([final.md](final.md#final-project-captures)).
- `make replay RUN=ab-20261018-162244-860638 PURPOSE=pilot` (the fallback procedure on the show-1
  run): replay `ab-20261018-165923-1d87bd`, 195 recorded events, the RECORDING badge, the referee
  re-run live (primary verdict 0:02, full verdict 2:06, the same counts: House rule 1 0 new, hidden
  tests 52 of 52, mutants killed 3 of 4), reviewer not run, $0. After it the documented `cp -a` of
  the screenshots made screen 2 show the board frames.

Total model spend of the five class commands: $0.183679 (the `session` figure of the last `Cost:`
line). Fallbacks in the demo guide's clone, the first complete run of each command there: show-1
`ab-20261018-162244-860638`, show-2 `ab-20261018-162745-ccba38`, demo-3 `ab-20261018-163515-dc7b16`,
show-4 `ab-20261018-164402-1a796a`, final (bulk-close) `ab-20261018-164951-bd677b`; the replay check
is the entry above. They live in that clone's `.shipharness/runs/`, not on the class machine; the
class machine's fallbacks are [listed above](#fallbacks-2026-10-18-speed-up).

### Score records shipped with the course (2026-10-18)

<a id="before-class-records"></a>

Owner-directed. The score records of the runs this page and the section pages count (99 records:
the current referee version, no constructed example, the run or A/B id named on an evidence page)
are in [scores/](scores/), one JSON file per run. Their LangSmith links (`trace_url`,
`referee_trace_url`) are removed, because they name the course's workspace; no record holds a key
or a host path (`platform/tests/unit/test_before_class_records.py` checks both, and that the release
build keeps the folder). [score-sections.json](score-sections.json) records which section each A/B
ran as, so screen 4 judges Section 3 demo records by that demo's measure
([s3.md](s3.md#s3-demo-measure)). Screen 4 always shows these records, labelled "measured before
class"; runs scored after them, from `exports/`, are added next to them as new dots.

## Captures

<a id="captures-root"></a>

### Root README screenshots

Since 2026-10-18, 17:20 UTC, the five screenshots come from the live runs for the demo guide
([above](#guide-runs-2026-10-18)), taken from the console with the demo guide's numbered callouts,
scaled to 1920 wide: `screen-1-ab-live.png` (renamed from `screen-1-ab-minute-3.png`) is screen 1 of
`ab-20261018-164951-bd677b` seconds after both arms started (taken live, event 62);
`screen-1-primary-verdict.png` is the harness panel of screen 1 of `ab-20261018-162244-860638`
after the run; `screen-2-boards.png` and `screen-4-report.png` are screens 2 and 4 of
`ab-20261018-164951-bd677b` after the run; `screen-3-scope-blocked.png` is screen 3 of
`ab-20261018-042848-b28607` (recorded before class), taken on 2026-10-18 in the current console,
because the live demo-3 run had no out-of-scope edit in the bare arm. Before that:

All from `make console` on the course machine, 2026-10-18, taken after the runs with a headless
browser at 1920 by 1080. The two minute screens were taken from a console fed with the run's log cut
at that minute of the console clock (see [s1.md](s1.md#s1-show-1-capture)).

| File | Run | Taken |
|---|---|---|
| `docs/images/screen-1-ab-minute-3.png` | `ab-20261018-042848-f7fa49` (`make final FEATURES=bulk-close`) | Minute 3 of the run |
| `docs/images/screen-1-primary-verdict.png` | `ab-20261018-045459-2efbfc` (`make show-1`) | Minute 3 of the run |
| `docs/images/screen-2-boards.png` | `ab-20261018-042848-f7fa49` | After the run |
| `docs/images/screen-4-report.png` | `ab-20261018-042848-f7fa49` | After the run |
| `docs/images/screen-3-scope-blocked.png` | `ab-20261018-042848-b28607` (`make demo-3 FEATURE=version-checks`) | After the run |

<a id="captures-setup"></a>

### Setup and reference captures

- `make doctor` in a checkout with no `.env`, `make warm` with no class date, `make help`,
  `uv run shipharness --help`, the console start lines, `git tag -l 'm1-*'`, the image sizes, and
  every `make -n` line on the reference page: captured 2026-10-17 17:28 UTC in a clean checkout of
  the course-first layout, commit 6ed6c33.
- The `make warm` lines with the class date set: captured 2026-10-17 11:18 UTC before the quiet
  timing runs (images rebuilt because their source had changed).
- WSL, Docker, git, uv, and make version lines on the Windows and Linux pages: captured
  2026-10-17 on the course machine (version commands, no run id).
- The terminal lines of the first live run: `make show-1`, `ab-20261017-112101-c5d839`.

## Sources and findings

<a id="sources"></a>

Quotes on the root README and the shared pages, with their finding ids (the full list of sources
and findings is [REFERENCES.md](../REFERENCES.md)):

- **F-a-05** (A1, OpenAI, "Harness engineering"): "From the agent’s point of view, anything it
  can’t access in-context while running effectively doesn’t exist."
- **F-a-08** (A2, Anthropic, "Effective harnesses for long-running agents"): "each new session
  begins with no memory of what came before."
- **F-a-20** (A1): "Codex replicates patterns that already exist in the repository—even uneven or
  suboptimal ones."
- **F-a-18** (A4, Anthropic, "Building a C compiler"): "(Run this in a container, not your actual
  machine)"
- **F-a-15** (A3, Anthropic, "Harness design for long-running application development"): "agents
  reliably skew positive when grading their own work"
- **F-a-02** (A1): "design environments, specify intent, and build feedback loops" (the basis for
  the course's word "harness").
- **F-a-124** (A3): "every component in a harness encodes an assumption about what the model can't
  do on its own, and those assumptions are worth stress testing"
- **F-a-125** (A3): "removing one component at a time and reviewing what impact it had on the final
  result."
- **F-a-143** (A1): its results should "not be assumed to generalize without similar investment".
- **F-a-28** (A1): "A short AGENTS.md (roughly 100 lines) is injected into context and serves
  primarily as a map, with pointers to deeper sources of truth elsewhere."
- **F-b-19** (B11, Meta, TestGen-LLM): "five executions" (the flakiness re-runs).
- **F-a-110** (A3): a separate evaluator judges the work (the harness, not the agent, sets
  `passes`; course design).
- **F-a-126** (A3): "read its traces on realistic problems"
- LangSmith billing page (read 2026-10-17): "Base traces have the base retention and are short-lived
  (14 days)"
- **F-a-108** (A2): A2 lets the agent set `passes` after testing; the course moves that to the
  harness.

Account and plan facts on the setup pages come from the providers' pages, each read on 2026-10-17
and linked where used: OpenAI's model page for gpt-6-luna and its rate-limits guide, LangSmith's
pricing and billing pages, and Microsoft's and Docker's install pages.

## Commits and tags

<a id="commits"></a>

| What | Commit or tag |
|---|---|
| Early primary verdict, five flakiness re-runs | 76ff2ca |
| Class profile (effort low, Fast tier, 2 CPUs) | 3f5a7c7 |
| Class profile agent time limit 420 s; class-date checks in `make doctor` and `make warm` | e15eae1 |
| `finish(not_done)` ends only the session (F2 fix) | 501be88 |
| S3 confirmation registered, before its runs | a87136d |
| S3 confirmation run on | main 1a70f84 |
| `make demo-3 FEATURE=F4` | da92e38 |
| Release tag for the class | `class-v1` (no `harness-frozen` tag) |

The 8 checkpoint tags (`m1-s1-start` to `m1-alt-b`) were rebuilt on 2026-10-17; the `teamtrack/`
tree of each differs from the old commit only in a comment in `reference/checkpoints.toml`, and the
old commits stay reachable, so recorded checkpoint commits still resolve.
