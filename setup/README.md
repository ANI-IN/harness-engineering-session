# Module 1: Harness Engineering for Coding Agents - Setup

> **Terms on this page**
>
> - **Harness arm**: the same run with the harness turned on.
> - **Referee**: the program that scores each run after the agent stops.
> - **Console**: the browser page that shows a run live, on five screens.
> - **Class date**: the day you run the class commands, as `YYYY-MM-DD` in `.env`.
> - **Trace**: the record of one run's steps (each model call and tool call), stored in LangSmith.

These pages take a machine with nothing installed to a first live run. At the end, a coding agent
with the first harness layer works on TeamTrack in a Docker sandbox, the referee scores what it
shipped, and you watch it on the console. They assume no tool is installed and no account exists.

## What you will install

| Item | Why you need it | Cost |
|---|---|---|
| OpenAI API account, Build tier | The agent model and the reviewer model | $5 in credit to reach the tier |
| LangSmith account, Developer plan | Traces of every run | $0; do not add a card |
| WSL2 and Ubuntu (Windows only) | A Linux shell for every course command | $0 |
| Docker | Each run and the referee run in containers | $0 for Docker Engine and Colima |
| git, uv, make | Clone the repository, install Python and packages, run the commands | $0 |

Use the OpenAI key from the program's email if you received one; otherwise create your own (Build tier). `make doctor` confirms the key can use the course models.

You need at least 6 GB of free disk. The two sandbox images alone take about 4 GB (1.28 GB
and 2.81 GB on the course machine). uv installs Python 3.12 for you, so you do not install Python yourself.

What the course commands cost:

| Command | Model calls | At most, at the caps |
|---|---|---|
| `make setup`, `make doctor`, `make warm`, `make console` | None | $0 |
| `make show-1`, your first live run | One agent arm and one review | $0.24 |
| The four assignments together | Several runs | $6 and 400 LangSmith traces (the course's budget) |

The caps come from `.env.example`. Every live command prints a `Cost:` line, and the cost tracker
refuses any model call that would cross a cap.

How long it takes: the course has not timed a first install on a clean machine. On the course
machine, building both images took 145 s (236.8 s in a fresh clone of the release on 2026-10-18,
where the whole first `make warm` took 429 s), and the first `make show-1` ended about 10 minutes after
launch ([evidence](../docs/evidence/general.md#timings)); in two runs of 2026-10-18 that ran alone,
3:37 to 4:45 ([evidence](../docs/evidence/general.md#guide-runs-2026-10-18)). Account sign-up, downloads, and the WSL
restart depend on you and your network.

## Pick your system

| Your machine | Page | Tested for the course |
|---|---|---|
| Windows 10 (version 2004 or later) or Windows 11 | [windows.md](windows.md) | Yes: WSL2, Ubuntu, Docker Engine inside Ubuntu |
| Linux with `apt` (Ubuntu, Debian) | [linux.md](linux.md) | In Ubuntu on WSL2; the commands are the same |
| macOS | [macos.md](macos.md) | No: the steps follow the official pages |

Every page has the same steps in the same order: the two accounts, the tools, the clone, `.env`,
`make doctor`, `make warm`, and the first live run. Each step says why, what to do, what you should
see, how to check it worked, and what to do if it fails. Official pages are linked instead of
copied.

Native Windows shells (PowerShell, cmd) are not supported. On Windows, every command after the WSL
install runs in the Ubuntu terminal.

If you are taking the live class, also read [pre-class.md](pre-class.md): it lists what must work
before class and the class date to set.

## Get help

- [Troubleshooting](../docs/troubleshooting.md): the exact messages and their fixes, grouped by
  command.
- [Reference](../docs/reference.md): every make target, setting, and cap.
- Bring the exact error message to the start of class. Never share your `.env` or a key.
