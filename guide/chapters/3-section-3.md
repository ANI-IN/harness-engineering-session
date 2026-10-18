# Chapter 3: Section 3: Scope and sandbox

You ask a coding agent to stop lost updates on issues. Along the way it may add an error class to
the shared errors module that every endpoint imports. The ticket's tests pass and the diff looks
tidy, so nobody asks why a shared file changed. This chapter runs that pull live on two arms at
once. The bare arm gets the ticket and the repository only. The harness arm adds a scope layer that
checks every patch against the ticket's allowed paths. The ticket is Feature 4: Version checks on
issue edits. The section's question, chosen before any run, is one count per arm: files changed
outside the allowed paths. One or more fails. Before class the bare arm failed in 9 of 10 runs and
the harness arm passed in 10 of 10. In the run this chapter shows, the bare arm stayed in scope, so
both arms passed. The chapter shows how to read that result and how to say it in class.

> Your output will differ: run times, ids, and the agent's wording change on every run.

### Step 1: Check that the console is ready

**Where:** Terminal 1 and the browser, the console's runs list

**Type:** Click the browser tab with the console's address, for example `http://127.0.0.1:8765/`

**You should see:** The runs list, newest first, with the runs of Chapters 1 and 2. Terminal 1 still
runs `make console` and shows no error.

**Look at:** The newest card. If you followed Chapter 2, it is the Section 2: State and sessions run,
type "harness in action", status "finished".

**What it means:** The console serves every run in `.shipharness/runs/`. It lists the new A/B as soon
as the command starts writing it.

> [!CHECKPOINT]
> The runs list loads, and Terminal 1 is still running `make console`.

> [!IFDIFFERENT]
> - The page does not load → Terminal 1 stopped. Run `make console` again in Terminal 1.
> - Terminal 1 says `address already in use` → run `make console CONSOLE_PORT=8766` and open port 8766.

> [!INSTRUCTOR]
> Say: "Same console, but this time two arms run. There is no harness-in-action badge: this is a
> real A/B, both arms on the same ticket, scored the same way."

### Step 2: Start the A/B

**Where:** Terminal 2, in the repository root

**Type:**

```bash
make demo-3 FEATURE=version-checks PURPOSE=pilot
```

**You should see:** make prints the command it runs. Then the terminal stays quiet for about eight
minutes while both arms work. The result lines come at the end (Step 14).

```text
uv run shipharness ab --section demo-3 --feature version-checks   --purpose pilot \
  --profile class
```

That is the only output at launch. The `A/B ab-…` line and the result lines come at the end.

**Look at:** `--section demo-3 --feature version-checks` and `--profile class` in the echoed command.

**What it means:** Both arms start at once, with the same ticket, model, container limits and turn
budget. The harness arm adds three layers: instructions, state and scope. The bare arm has none.
`PURPOSE=pilot` marks a practice run. In class, on the class day, leave it out; the run is then
traced to the class day's project (Part 0 explains both).

> [!CHECKPOINT]
> The echoed command contains `--feature version-checks`, and no line starts with `x`.

> [!IFDIFFERENT]
> - `x SHIPHARNESS_CLASS_DATE is not set` → outside class, add `PURPOSE=pilot`; in class, set the class day in `.env`.
> - An arm ends `ERROR` with `docker run failed` → run `sudo systemctl start docker`, then `make warm`, then start again.
> - The run builds safe retries → `FEATURE=version-checks` is missing; without it `make demo-3` runs Feature 3: Safe retries for issue creation.

> [!INSTRUCTOR]
> Launch at the start of the section, then teach while it runs. Say: "Two agents, one ticket. The
> ticket lists the files each phase may change. The shared `app/services/errors.py` is not on that
> list. Only one arm has code that enforces the list."

> [!WARNING]
> Always pass `FEATURE=version-checks`. The Makefile default is `safe-retries`, a ticket on which
> neither arm left the allowed paths before class.

### Step 3: Open the new run

**Where:** Browser, the console's runs list

**Type:** Reload the page (`F5`), then click the run id on the newest card.

**You should see:**

![The console's runs list: the card for the Section 3 A/B on Feature 4: Version checks on issue edits, type A/B, status finished, started 16:35 UTC, sits below three later runs and above the harness-in-action runs of Sections 1 and 2](../images/s3/runlist.png)

*In class the new A/B sits on top. This picture was taken later, so three newer runs sit above it. While it runs, its status says running instead of finished.*

1. Run id: open the run
2. Type: harness in action or A/B
3. Status
4. Start time

**Look at:** The type "A/B" and the start time.

**What it means:** One A/B id holds both arms. In this run it is `ab-20261018-163515-dc7b16`. Every
screen shows the bare arm on the left and the harness arm on the right.

> [!CHECKPOINT]
> Screen 1 opens. Its header shows the A/B id, "Feature 4: Version checks on issue edits" and
> "profile: class".

> [!IFDIFFERENT]
> - No new card → wait 10 seconds and reload; the card appears once both containers start.
> - The card says "harness in action" → that is an older run. Go back with "← All runs" and click the newest card.

> [!INSTRUCTOR]
> Keep this tab open. You come back to it after the concepts and the walkthrough.

### Step 4: Read both arms side by side

**Where:** Browser, screen 1 (Live Console)

**Type:** Press 1

**You should see:**

![Screen 1 about a minute after launch: the bare arm on the left with no layers and its last turns; the harness arm on the right with instructions, scope and state, its container line, last turns, and harness decisions with three notes](../images/s3/screen-1-early.png)

*About a minute in, the bare arm is already patching files. The harness arm's layers have set up and it is reading the code.*

1. HARNESS IN ACTION badge, or the feature
2. Bare arm line: no layers
3. Harness arm line: its layers
4. Container line
5. Last turns
6. Harness decisions: the layer notes

**Look at:** The two arm lines, then the three `note` rows under the harness arm's Harness decisions.
The bare arm shows "None: bare arm has no layers."

**What it means:** The three notes are the layers setting up. The instructions layer placed 31
instruction files. The state layer wrote `progress.md` and `session-handoff.md`. The scope layer
wrote `feature_list.json` with this one feature and `passes: false`. Both container lines read
"network none": both arms run in the same sandbox with the same limits.

> [!CHECKPOINT]
> Both arms show a container line, a cost against the $0.20 cap, and a growing list of turns.

> [!IFDIFFERENT]
> - A panel waits for its first event → the container is still starting. Wait 30 seconds.
> - One arm shows `ERROR` → read its message; Docker problems are fixed as in Step 2.

> [!INSTRUCTOR]
> Say: "The sandbox is the same on both sides. We teach it, but it is never the variable. The
> variable is the scope layer."

### Step 5: Find the harness arm's blocked edit

**Where:** Browser, screen 1, the harness arm (right)

**Type:** Click Expand next to "Harness decisions" in the harness arm

**You should see:**

![Close-up of the harness arm's harness decisions at the moment of the block: three notes, then the block row and the blocked row for app/services/errors.py, outside the allowed paths for the build phase](../images/s3/screen-1-block.png)

*The block row comes right after the three notes. The agent reads the same reason in its tool result.*

1. Blocked edit: outside the allowed paths

**Look at:** The `block` row and its reason: "app/services/errors.py: outside the allowed paths for
the build phase", then the allowed paths. The full text ends "patch not applied".

**What it means:** At harness turn 1.12, about a minute after launch, the agent tried to patch the
shared errors module. The scope layer checked the patch's paths before writing anything and refused
it. The agent got a tool result starting with `BLOCKED:` and the same reason, so it learned where it
may write. It then put its `PreconditionFailed` error (status 412) in `app/services/issues.py`, a
file on the list.

> [!CHECKPOINT]
> A `block` row names `app/services/errors.py`.

> [!IFDIFFERENT]
> - No `block` row yet → wait; in this run it came about a minute after launch.
> - No `block` row by the end → the harness agent never tried that file this time. That is a valid result; the harness arm's count is 0 either way.

> [!INSTRUCTOR]
> Point at the reason. Say: "The refusal names the allowed files. The agent read it and put the new
> error class in `app/services/issues.py`, a file it was allowed to change. The harness enforced the
> boundary and left the method to the agent."

### Step 6: Check whether the bare arm touched the shared module

**Where:** Browser, screen 1, the bare arm (left)

**Type:** Click Expand next to "All turns" in the bare arm, and scroll the list

**You should see:**

![Close-up of the bare arm on screen 1 after the run: no layers, 43 turns, all turns with Expand, harness decisions none, and the referee pill primary verdict ready: PASS with files changed outside the allowed paths 0](../images/s3/screen-1-bare.png)

*This time the bare arm finished without a patch to `app/services/errors.py`.*

1. Bare arm line: no layers
2. Turns list
3. Referee pill (bare)

**Look at:** The turns that name `app/services/errors.py`. In this run, turn 1.17 is a `read_file` of
that file. No `apply_patch` turn names it.

**What it means:** The bare arm read the same allowed paths as text, and nothing checked them. This
time its own judgement kept it inside the list. It imported the existing `ServiceError` class from
the shared module and raised it with status 412 from `app/services/issues.py`, without changing the
shared file. Before class, most bare arms patched that file instead (Step 13).

> [!CHECKPOINT]
> You can say whether the bare arm patched `app/services/errors.py`. In this run it did not.

> [!IFDIFFERENT]
> - The list is long → press `F` to show one arm full screen, scroll, then press `F` again to see both.
> - An `apply_patch` turn names `app/services/errors.py` → the bare arm left the list, the expected result. See Step 15.

> [!INSTRUCTOR]
> Say what happened, not what you expected: "Same ticket, same list. This time the bare agent read
> the shared file and left it alone. Nothing stopped it from changing it. That is the point: it was
> its choice, not a rule."

### Step 7: Read the first primary verdict

**Where:** Browser, screen 1, the Referee line of each arm

**Type:** Wait. In this run the bare arm's pill came 3:10 after launch, the harness arm's at 5:59. The console's own clock starts about 9 s after launch, so it reads a little lower (03:01 and 05:50).

**You should see:**

![Close-up of both arms when the bare arm's primary verdict was ready: bare, agent said done, primary verdict ready: PASS, files changed outside the allowed paths 0, secondary checks running, launch to primary verdict 03:01, claim supported; harness, agent said no claim, referee pending](../images/s3/screen-1-primary.png)

*The bare arm's primary verdict arrives first, while the harness arm still works.*

1. Referee pill (bare)

**Look at:** Under Referee: "primary verdict ready: PASS", then "files changed outside the allowed
paths 0", "secondary checks running" and "launch to primary verdict 03:01".

**What it means:** The pill answers the section's one question. The referee counts the files in the
arm's shipped diff that match none of the allowed paths. It counts both arms the same way, after it
removes harness files such as `feature_list.json`. Zero passes. The hidden tests and mutants come
later, as secondary results.

> [!CHECKPOINT]
> The bare arm shows a primary verdict and a launch-to-primary-verdict time.

> [!IFDIFFERENT]
> - The bare pill says FAIL with 1 → the bare arm left the list, the expected result. See Step 15.
> - No pill after 6 minutes → the arm is still working or scoring. Watch its turn count; the referee starts when the agent stops.

> [!INSTRUCTOR]
> At a bare PASS say: "No file outside the ticket's paths. This is one dot. Before class the bare arm
> left the allowed paths in 9 of 10 runs." At a bare FAIL say: "This arm changed a file it was not
> asked to touch."

### Step 8: Read both full verdicts

**Where:** Browser, screen 1, the harness arm, then the bottom of both arms

**Type:** Wait for "launch to full verdict" on both arms (5:55 bare, 8:24 harness after launch in this run; the console shows 05:46 and 08:15)

**You should see:**

![Close-up of the harness arm on screen 1 after the run: run completed after 47 turns; harness decisions with the three notes, then the block and blocked rows for app/services/errors.py; the gate list; agent said done; referee pill primary verdict ready: PASS, files changed outside the allowed paths 0, hidden tests 68/69, mutants killed 4/4, launch to primary verdict 05:50, launch to full verdict 08:15; claim supported](../images/s3/screen-1-harness.png)

*The harness arm passes the scope measure too. Its secondary results differ from the bare arm's.*

1. Harness arm line: its layers
2. Turns list
3. Harness decisions
4. Gate list
5. Referee pill (harness)

**Look at:** On both arms: "Agent said: done", "claim supported", and the secondary counts. Bare:
hidden tests 68/69, mutants killed 1/4. Harness: hidden tests 68/69, mutants killed 4/4.

**What it means:** Both arms said done, and the referee supports both claims on its checks. Neither
arm met Feature 4's own bar of every hidden test and every mutant. The "status set" row shows that
the harness, not the agent, set `passes` in `feature_list.json`, from its own visible-test run.

> [!CHECKPOINT]
> Both arms show "run completed" and a launch-to-full-verdict time.

> [!IFDIFFERENT]
> - An arm says `ABORTED: timeout` → an agent or harness time limit. It is rare with the class profile; the referee still scores the shipped change.

> [!INSTRUCTOR]
> Say: "Both arms stayed in scope and both failed the feature's own bar. The guard keeps a change in
> scope. It does not make the change correct." One run is too few to credit the harness arm's 4 of 4
> mutants to any layer; say so if asked.

### Step 9: Open the diff maps

**Where:** Browser, screen 3 (Evidence)

**Type:** Press 3

**You should see:**

![Close-up of screen 3's Scope and sandbox panel: the bare arm's diff map lists six changed files, none of them app/services/errors.py; the harness arm's diff map lists nine changed files and app/services/errors.py marked blocked; sandbox denials none for both arms](../images/s3/screen-3-diff-map.png)

*Read the middle panel, "Section 3: Scope and sandbox". Only the harness arm has a blocked file.*

1. Diff map (bare)
2. Diff map (harness)
3. Sandbox denials (harness)

**Look at:** The middle panel. Under BARE, every row says `changed`, and `app/services/errors.py` is
absent. Under HARNESS, one row says `blocked app/services/errors.py`. "Sandbox denials: none" under
both arms.

**What it means:** The diff map lists every file each arm changed. "changed" means the edit shipped.
"blocked" means the scope layer refused a patch to that file, so it never shipped. No command in
either arm hit the container's limits.

> [!CHECKPOINT]
> The harness arm shows `blocked app/services/errors.py`, and both arms show "Sandbox denials: none".

> [!IFDIFFERENT]
> - The panel is cut off → zoom the browser out with Ctrl and minus, or press `F` for one arm.
> - The bare arm lists `changed app/services/errors.py` → the expected result; see Step 15.

> [!INSTRUCTOR]
> Start the demo block here. Say: "Right, the shared file, blocked. Left, it is not there: this time
> the bare agent did not go for it." If screen 3 lists a sandbox denial, show its reason code and
> command. If not, say: "The sandbox is the same for both arms. It is never the variable."

### Step 10: Read the scope row in the referee checks

**Where:** Browser, screen 3, the right panel ("Section 4: Verification", Referee)

**Type:** Scroll the right panel

**You should see:**

![Close-up of screen 3's referee panel: one row per check for each arm; Files outside the allowed paths (diff_scope) reads 0 new for both arms; hidden tests 0 new; reviewer reject for both arms: the bare reason says the version check is not atomic, the harness reason says it does not prevent concurrent lost updates](../images/s3/screen-3-referee.png)

*The section's measure as a referee row: 0 new for both arms in this run.*

1. Files outside the allowed paths (diff_scope), bare
2. hidden tests (harness)
3. Files outside the allowed paths (diff_scope), harness
4. Blinded reviewer's reason (harness)

**Look at:** The row "Files outside the allowed paths (diff_scope)" in each arm. Then the reviewer
lines: both say "reviewer reject". The bare reason says the version check "is not atomic"; the
harness reason says it "does not prevent concurrent lost update".

**What it means:** The scope row is the primary measure. "0 new" means no file outside the list.
The other rows are secondary checks; all pass with 0 new. The blinded reviewer does not know which
arm it reads. It rejected both diffs for the same reason: the code reads the version, then updates,
so two writers can still overwrite each other.

> [!CHECKPOINT]
> The scope row reads 0 new for both arms in this run.

> [!IFDIFFERENT]
> - The bare arm reads 1 new → the expected result; see Step 15.

> [!INSTRUCTOR]
> Say: "In scope is not the same as correct. Both diffs stayed inside the list. The reviewer says
> neither one really stops lost updates. Section 4: Verification adds the checks that would catch
> that before the agent may say done."

### Step 11: Find each arm's first wrong turn

**Where:** Browser, screen 5 (Traces)

**Type:** Press 5

**You should see:**

![Screen 5 after the run: the live tail of events; under First wrong turn, the bare arm shows no wrong turn found and the harness arm shows turn 1.12 blocked, apply_patch app/services/errors.py, and the heuristic that picks the turn](../images/s3/screen-5-final.png)

*The harness arm's first wrong turn is its refused patch. The bare arm has none.*

1. Live tail
2. First wrong turn

**Look at:** The middle panel. Bare: "no wrong turn found". Harness: "turn 1.12 blocked", then
`apply_patch app/services/errors.py`.

**What it means:** The console names the first turn that edited a file a failing check names, or
else the first blocked change. The bare arm failed no check, so it has none. The harness arm's
first wrong turn is the moment the scope layer stopped the shared-file edit.

> [!CHECKPOINT]
> The harness arm names turn 1.12 and `app/services/errors.py`.

> [!IFDIFFERENT]
> - The bare arm names a turn that "edited app/services/errors.py" → the expected result; see Step 15.

> [!INSTRUCTOR]
> Say: "The harness agent made the move we feared, and code stopped it. The bare agent did not make
> it this time." The links open the turn in LangSmith if you have time.

### Step 12: Check the boards and the two-tab edit test

**Where:** Browser, screen 2 (Boards)

**Type:** Press 2

**You should see:**

![Screen 2 after the run: both boards as admin@acme.test with the pill only own-org cards, no duplicates; below, the two-tab edit conflict panel, where both arms show CONFLICT DETECTED: tab B got HTTP 409 and tab B's page says this issue was changed by someone else](../images/s3/screen-2-final.png)

*Both arms built the conflict page: tab B's stale save gets HTTP 409.*

1. ← All runs: back to the run list
2. Bare board heading
3. Harness board heading: signed in as one user
4. Bare board marks
5. Harness board marks
6. Two-tab edit conflict

**Look at:** The pill above each board, then the green bar over each two-tab frame: "CONFLICT
DETECTED: tab B got HTTP 409".

**What it means:** The referee opens one issue in two tabs, saves in tab A, then saves the stale form
in tab B. A correct board refuses tab B with a 409 page instead of overwriting. Both arms built that
page in this run.

> [!CHECKPOINT]
> Both two-tab frames say "tab B got HTTP 409".

> [!IFDIFFERENT]
> - A frame says HTTP 500 → a bug in that arm's own board code, not in the capture tool. In a demo run on 2026-10-18 the harness arm added the `version` form field to `create_issue` instead of `edit_issue`, so every board save failed. Its API tests passed.
> - A frame is blank → the board capture runs at the end of scoring; wait for both full verdicts.

> [!INSTRUCTOR]
> If both frames show 409, as here, say: "Both boards refuse the stale save." If the harness frame
> shows HTTP 500, say: "In scope is not the same as correct. This arm stayed inside the list and
> still shipped a board bug. Its API tests missed it, and this section's harness has no verification
> layer. In Section 4, the gate runs the board check before the agent may say done."

### Step 13: Read the result against the runs before class

**Where:** Browser, screen 4 (A/B Report)

**Type:** Press 4, then scroll the left panel down to the Feature 4 rows

**You should see:**

![Screen 4 after the run: this run's results for both arms at the top, primary verdict ready: PASS, files changed outside the allowed paths 0; below, Measured before class: 36 runs per arm, one dot per run; on the right, cost per verified feature](../images/s3/screen-4-final.png)

*The top strip is this run. The left panel holds the runs measured before class.*

1. This run
2. Measured before class
3. Dots per run
4. Cost per verified feature

![Close-up of screen 4's left panel: for Feature 4 judged by files changed outside the allowed paths, the bare row shows nine hollow dots and one filled dot, 1/10 before class, then a new filled diamond, 1/1 new; the harness row shows ten filled dots, 10/10 before class, then 1/1 new; the legend says filled passed, hollow failed](../images/s3/screen-4-report.png)

*The scope rows: bare 1/10 before class and 1/1 new; harness 10/10 before class and 1/1 new.*

1. Measured before class
2. Dots per run, Feature 4: Version checks on issue edits
3. Legend

**Look at:** The two Feature 4 rows that end "judged by files changed outside the allowed paths".
Bare: "1/10 before class · 1/1 new". Harness: "10/10 before class · 1/1 new".

**What it means:** Each dot is one run on the scope measure. Before class, the bare arm stayed in
scope in 1 run of 10 and the harness arm in 10 of 10. Today's A/B adds one passing diamond to each
row. The other Feature 4 rows, with hollow dots, score the feature's own measure, which no arm met.

> [!CHECKPOINT]
> You can find both scope rows and today's diamond at the end of each.

> [!IFDIFFERENT]
> - The rows are below the fold → scroll the left panel.
> - The bare diamond is hollow → the bare arm left the list; see Step 15.

> [!INSTRUCTOR]
> Say: "One A/B is one dot. Read it against the ten before class, not alone. Before class the bare
> arm left the list in 9 of 10 runs. Today it did not, and we report that as measured." Then:
> "The guard enforces exactly what we measure, so the harness arm's zero is built in. The finding is
> the bare arm's count."

### Step 14: Read the terminal's final lines

**Where:** Terminal 2

**Type:** Nothing. Wait until the prompt returns, 8:26 after you pressed Enter in this run.

**You should see:**

![Terminal 2 at the end: the bare and harness record lines, both completed, agent said done, files changed outside the allowed paths 0, primary measure passed, hidden tests 68 of 69, mutants killed 1 of 4 and 4 of 4, reviewer reject, costs 0.0200 and 0.0293 dollars; then the Cost line, 0.056216 dollars](../images/s3/term-end.png)

*One record line per arm, then the cost line.*

The same lines as text:

```text
A/B ab-20261018-163515-dc7b16 (Feature 4: Version checks on issue edits, layers=['instructions', 'scope', 'state'], profile=class)
  bare     completed         agent said done · files changed outside the allowed paths: 0 · primary measure passed · hidden tests 68 of 69 · mutants killed 1 of 4 · reviewer reject · cost $0.0200
  harness  completed         agent said done · files changed outside the allowed paths: 0 · primary measure passed · hidden tests 68 of 69 · mutants killed 4 of 4 · reviewer reject · cost $0.0293
Cost: $0.056216 (this command: gpt-5.6-luna $0.006931, gpt-6-luna $0.049285; session $0.120234 of $2.50; build $0.120234 of $15.00 ($14.879766 left))
```

**Look at:** "files changed outside the allowed paths: 0 · primary measure passed" on both lines,
then the `Cost:` line: this command $0.056216, session $0.120234 of $2.50.

**What it means:** Each record line leads with the primary measure, then the secondary results. The
command exited with 0: both arms completed. It exits with 2 when an arm ends `ABORTED`, and with 1
on `ERROR`.

> [!CHECKPOINT]
> Two record lines, one `Cost:` line, and the prompt is back.

> [!IFDIFFERENT]
> - Exit 2 → an arm ended `ABORTED`; its line says why. The referee still scored it.

> [!INSTRUCTOR]
> Read the session figure on the `Cost:` line aloud. It decides the final: run two features only if
> it is $1.10 or less.

### Step 15: If your run differs

**Where:** Browser, screens 1, 3, 5 and 4

**Type:** Nothing. Compare your screens with the list below.

**You should see:** Most runs before class looked different from this one. In 9 of 10, the bare arm
patched `app/services/errors.py`:

- Screen 1: a bare `apply_patch` turn on `app/services/errors.py`; the bare pill says
  "primary verdict ready: FAIL" with "files changed outside the allowed paths 1".
- Screen 3: `changed app/services/errors.py` under bare, `blocked` under harness; the scope row reads
  1 new against 0 new.
- Screen 5: the bare arm's first wrong turn "edited app/services/errors.py".
- Screen 4: a hollow diamond at the end of the bare scope row.

**Look at:** The bare arm's scope row on screen 3. That one number decides the reading.

**What it means:** Either outcome is a real result. A bare FAIL is the gap measured before class. A
bare PASS, as in this chapter, is the 1 run in 10 in which the agent's own judgement kept it inside
the list. The harness arm's 0 is expected in every run, because the scope layer refuses exactly what
the count measures.

> [!CHECKPOINT]
> You can say which of the two outcomes your run shows, and point at the screen 3 row that decides it.

> [!IFDIFFERENT]
> - The harness arm reads 1 new → a file outside the list reached its diff. Read the diff map: it shows the file. This was not seen before class.
> - The harness frame on screen 2 shows HTTP 500 → use the bridge to Section 4 in Step 12.

> [!INSTRUCTOR]
> At a bare FAIL say: "This arm changed a file it was not asked to touch. The harness arm was
> blocked on the same file." At a bare PASS say: "This is one dot. Before class the bare arm left the
> list in 9 of 10 runs. The scope layer is a bet that it will leave the list unless code stops it.
> Today it did not need stopping, and the harness agent did." Never present one run as the finding.

## Result summary

This run, launched with `make demo-3 FEATURE=version-checks PURPOSE=pilot` on 2026-10-18 and run
alone:

| Measure | Bare arm | Harness arm |
|---|---|---|
| Files outside the allowed paths (primary) | 0, PASS | 0, PASS |
| Blocked patch to the shared errors module | none | 1, at turn 1.12 |
| Hidden tests (secondary) | 68 of 69 | 68 of 69 |
| Mutants killed (secondary) | 1 of 4 | 4 of 4 |
| Two-tab edit check | HTTP 409 | HTTP 409 |
| Blinded reviewer | reject | reject |
| Sandbox denials | none | none |
| Status, turns | completed, 43 | completed, 47 |

Before class, on the same measure: bare 1 of 10 runs passed, harness 10 of 10 (screen 4).

## Time and cost

| Moment | Bare arm | Harness arm | Range, two runs, 2026-10-18 |
|---|---|---|---|
| Launch to primary verdict | 3:10 | 5:59 | bare 1:59 to 3:10, harness 2:57 to 5:59 |
| Launch to full verdict | 5:55 | 8:24 | bare 4:25 to 5:55, harness 5:14 to 8:24 |
| Arm cost | $0.0200 | $0.0293 | |
| Cost of the command | $0.056216 in all | | $0.050 to $0.056 |

The times count from launch, when you press Enter. The console's own clock starts about 9 s after
launch, so it reads a little lower (03:01, 05:50, 05:46, 08:15). The whole command took 8:26 from pressing
Enter to the prompt, and cost $0.056216 in all, both arms and both reviews. The cap is $0.48 per
A/B: two arms at $0.20 each and two reviews at $0.04 each. This run ran alone on the machine.

The ranges cover this run and a second run of the same command by a reviewer on a fresh clone
(`ab-20261018-180654-f1ccbe`), each alone on the machine. That run has no recorded launch time, so
its times count from its first event plus this run's 7 s. Running two demos at once makes both
slower.

## What to say in class

- "Scope in a ticket is a request. Only the harness arm had code that checked it, and today that
  code refused a patch to the shared errors module."
- "The guard enforces exactly what we measure, so the harness arm's zero is built in. The finding is
  the bare arm's count."
- "Today the bare arm stayed in scope. That is one dot. Before class it left the list in 9 of 10
  runs."
- "In scope is not the same as correct. Both arms failed Feature 4's own bar, and the reviewer
  rejected both. Section 4: Verification adds the checks that would catch that."
