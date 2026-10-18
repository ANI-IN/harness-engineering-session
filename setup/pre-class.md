# Module 1: Harness Engineering for Coding Agents - Before class

> **Terms on this page**
>
> - **Class date**: the day you run the class commands, as `YYYY-MM-DD` in `.env`.
> - **Console**: the browser page that shows a run live, on five screens.
> - **Baseline**: the referee's or gate's result on the app before the agent changes it, saved so
>   each run is compared against it.
> - **Primary verdict**: the referee's answer to the one question the section asks.

Do this in the days before the live class. It takes your machine from "installed" to "ready for
class". If nothing is installed yet, start with the page for your system: [Windows](windows.md),
[macOS](macos.md), or [Linux](linux.md).

## The checklist

| Check | Command | Ready when |
|---|---|---|
| Both keys work | `make doctor` | The last line is `result: + ready` |
| Images and baselines are ready | `make warm` | The last line before the cost line is `warm: done` |
| The console opens | `make console` | http://127.0.0.1:8765/ shows the run list |
| One live run works (optional, at most $0.24) | `make show-1` | The console shows a run with a primary verdict |

Run every command in the repository folder (`~/shipharness`), in the Ubuntu terminal on Windows.

## Set the class date

The class commands trace to the LangSmith project `shipharness-class-<date>` and share one $2.50
session cap per date. They refuse to start without the date, and so do `make doctor` and
`make warm`.

1. Open `.env` in the repository folder.
2. Set the date to the day you run the commands, for example on the morning of class:
   `SHIPHARNESS_CLASS_DATE=YYYY-MM-DD`, with the real date in place of `YYYY-MM-DD`.
3. Run `make doctor` again. The `SHIPHARNESS_CLASS_DATE` line must start with `+ ok`.

For a test run on another day, set that day's date, or add `PURPOSE=pilot` to the command, for
example `make show-1 PURPOSE=pilot`. A new date starts a new project and a new session cap.

## What to bring

- A machine that passed the checklist, plugged in.
- The exact text of any error you could not fix, from the terminal. Never share your `.env` or a
  key.

If a check fails, the fix is in the "If it fails" part of the matching step on your system's page,
or in [troubleshooting](../docs/troubleshooting.md).
