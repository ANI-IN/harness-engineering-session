# Frequently asked questions

The questions learners ask most, answered from what is in this repository. New words are in the
[glossary](glossary.md). The order of the course is on [start here](start-here.md).

## Money and keys

### What does the course cost me?

The commands that set up, check, replay, or re-score cost nothing: they make no model calls. A live
command costs at most its caps: $0.24 for one `make show-N`, $0.48 for one A/B, and $0.58 per final
feature. The class commands, measured 2026-10-18, cost $0.021 to $0.053 per run. The course's budget for the
four assignments together is $6 of OpenAI usage and 400 LangSmith traces (course policy). Every number, and how to
check your spending, is on the [costs page](costs.md).

### Which keys do I need?

Two, both in `.env` at the repository root:

- **OpenAI**: use the OpenAI key from the program's email if you received one; otherwise create
  your own (Build tier) at platform.openai.com. The Build tier takes $5 of credit, because the agent
  model has no free tier.
- **LangSmith**: a free Developer account at smith.langchain.com. Do not add a card.

Then run `make doctor`. `make doctor` confirms the key can use the course models, checks that
LangSmith accepts its key, and must end with `result: + ready`. It never prints any part of a key. Never
paste `.env` or a key into a chat, a ticket, an issue, or a screenshot.

### Which model does the course use?

gpt-6-luna for the agent and gpt-5.6-luna for the blinded reviewer (`OPENAI_MODEL` and
`OPENAI_EVAL_MODEL` in `.env.example`). Both arms of an A/B always use the same model and settings.
Every measured result in the course comes from these two models. You can set other models in `.env`
and add their prices to `platform/config/prices.toml`, but then your results are your own
measurement, not the course's.

### What happens when a run reaches a cap?

The cost tracker refuses the call that would cross the cap, and the arm ends as `ABORTED: cap`. The
referee still scores it and the console still shows it, so keep it: it is a result. The session cap
($2.50) is shared by every command under one class date or one `PURPOSE`. For your own runs after
class, add `PURPOSE=assignment`, which has its own session.

## Setup

### Can I use Windows?

Yes, through WSL2: Ubuntu running inside Windows. Every course command runs in the Ubuntu terminal.
Native Windows shells (PowerShell, cmd) are not supported. Windows is the setup the course tested:
WSL2, Ubuntu, and Docker Engine inside Ubuntu. Follow [setup on Windows](../setup/windows.md).

### Does it work on macOS?

The [macOS page](../setup/macos.md) follows the official install pages, but the course has not
tested it on a Mac. If a step fails, bring the exact message to Wednesday technical coaching or a
support ticket.

### Why do I need Docker?

Every agent run and every referee run happens in a container with no network, the same for both
arms. That keeps a run from touching your machine, and it keeps the comparison fair. You need about
6 GB of free disk; the two images take about 4 GB. A run with `SANDBOX_MODE=none` runs commands on
your machine and is labelled `UNSANDBOXED`: its results are not official.

## Running the demos

### What do I do if a demo fails?

First read the "If it fails" table on the demo page: it lists the exact messages and their fixes.
Then check the [troubleshooting page](troubleshooting.md). Two things are not failures:

- An arm that ends `ABORTED: timeout` or `ABORTED: cap` hit a time or cost limit. It is still scored
  and shown. Read its verdict as usual.
- A run whose verdict is FAIL is a result, not a broken demo.

If you cannot run it at all, you still have two ways to follow the demo:

- Each demo's `expected/` folder holds the terminal output and the screenshots of one real run, for
  example [the run of Section 1: Instructions](../section-1-instructions/demo/expected/README.md).
- `make replay RUN=<id>` shows a run you recorded earlier, on every screen, with no model calls. The
  id comes from the console's run list, and every screen shows a `RECORDING` badge.

### Why does my run look different from the pages?

Model output changes on every run: the times, the ids, the agent's wording, and sometimes the
verdict. Compare your run with the course's runs, never alone. One run is one result.

## Results

### Why didn't the harness always win?

Because the course measured it, and on these tickets with this model, most layers made no
measurable difference. In Section 1: Instructions and Section 2: State and sessions, both arms
passed every run before class; in Section 4: Verification, both arms failed every run. The scope
layer did show: on the confirmation ticket of Section 3: Scope and sandbox, every bare arm changed a file outside its allowed paths, and the harness arm kept inside them in 3 of 3
runs ([evidence](evidence/general.md#s3-confirmation)). The harness also costs turns, time, and
money. The course reports what it found, so you can run the same measurement on your own model and
code.

### How far can I trust the results?

They are counts from a small number of runs, on one model, on one ticket per section (two in
Section 3). They are specific to TeamTrack and these tickets. The "Known limitations" section of the
[README](../README.md#known-limitations) lists every limit, and the
[evidence page](evidence.md) has every run id and count.

## Assignments and help

### How is an assignment graded?

Each assignment is out of 100 points, with its grading criteria on its README. `make
check-assignment-N` runs the visible checks offline, at no cost; on a fresh clone every check fails,
with lines that name what to fix. The instructor's grader adds hidden cases and is not in this
repository. A live step is graded on the files it produced, not on which arm passed, so never re-run
it for a nicer result. Feedback comes at the review session.

### Where are the solutions?

In each assignment's `solution/` folder, next to the starter, with a step-by-step walkthrough. Try
each assignment yourself first, then compare your choices with the walkthrough's.

### Do LangSmith traces last?

No. LangSmith keeps an ordinary trace for 14 days
([LangSmith billing](https://docs.langchain.com/langsmith/billing)). Copy the trace links you need
for a report or your portfolio before then. Your score records in `exports/scores/` stay on disk.

### Where do I get help?

Use the program's channels: a support ticket on Uplevel at any time, Wednesday technical coaching,
Discord for peer learning, and the teaching assistants (TAs) during the live class. Bring the exact terminal message. The
review session goes through each assignment. To report a security problem, follow
[SECURITY.md](../SECURITY.md), and never post a key.

## Sources

- Source 1: LangSmith billing, <https://docs.langchain.com/langsmith/billing>, LangChain (LangSmith docs), n.d.
