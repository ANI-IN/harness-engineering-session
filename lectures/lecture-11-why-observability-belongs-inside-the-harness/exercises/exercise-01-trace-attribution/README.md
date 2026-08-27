# Exercise 01: trace-attribution

## Objective

Fix an audit that blames the wrong recorded write, so that every failing
check is attributed to the write that actually changed the value it reads
and the report matches all three shared expected outputs.

## Why this matters

[Lecture 11](../../README.md)'s claim is that the overwritten value
survives only in the harness's record. Having the record is the first
half; reading it correctly is the second. A failing check hands you a
file and a key, and the natural search is by file, because that is what
you were staring at when the check failed. The trap fixture is what every
real session looks like: it touched `config/app.conf` three times, and
the write that landed last is not the write that broke anything. An audit
that stops at the file blames a harmless change, proposes restoring a
value nothing lost, and leaves the actual break in place while reporting
that it located the cause.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the demo contract's
  event shape and check rules ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's [evidence](../../../../docs/glossary.md#working-discipline)
  entry: the recorded command and observable result behind a claim.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the trace format, and the
  starter's naive decision (shared).
- [`fixtures/workspaces/workspace-clobbered`](./fixtures/workspaces/workspace-clobbered/):
  the settings a build session left, with `chunk_size=0`; one check fails
  (shared).
- [`fixtures/workspaces/workspace-healthy`](./fixtures/workspaces/workspace-healthy/):
  the same settings with `chunk_size=512`; every check passes (shared).
- [`fixtures/traces/`](./fixtures/traces/): two recorded logs.
  `trace-clobber.jsonl` is the trap, seven events, with a later write to
  a different key in the same file. `trace-scoped.jsonl` is a real log
  from a harness whose logging covered `src/` and `index/` only (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the check engine, the report,
  and the unattributed path are complete; attribution matches on the file.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Make `attribute` match the failing check's `key` as well as its
   `path`, so it returns the last `workspace/write` whose `detail.path`
   and `detail.key` both match.
2. Pass the check's key through to it from the audit loop.
3. Leave the unattributed path exactly as it is: a check whose key never
   appears in the trace is still `unattributed`.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: matching on the key selects event 5,
the write that set `chunk_size` to 0, instead of event 6, the later
`retries` write, so `clobber-attributed` reports the attribution and the
repair the expected output pins; the other two cases were already
matching.

## Expected outcome

Before your change:

```text
[FAIL] clobber-attributed (python) -- stdout mismatch vs expected/clobber-attributed.json: diverges at $.diagnosis[0].attribution: 'event 6 recorded step 5 setting retries in config/app.conf from 1 to 3' != 'event 5 recorded step 4 setting chunk_size in config/app.conf from 512 to 0'
[pass] scoped-blind (python)
[pass] healthy-nothing-failing (python)
[pass] missing-trace (python)
```

The audit reports a located cause and the wrong one. After your change
all four cases match, and:

```text
verify: PASS (starter)
```

## How to verify

### Python

```sh
./verify.sh --stack=python
```

### TypeScript

```sh
./verify.sh --stack=typescript
```

## Hints

<details>
<summary>Hint 1: what the failing check gives you</summary>

The audit already destructures `path` and `key` out of the check and uses
both when it reads the observed value. Only the attribution search
narrows to one of them.

</details>

<details>
<summary>Hint 2: why the other cases already pass</summary>

`trace-scoped.jsonl` records no write to `config/app.conf` at all, so
searching by file and searching by key both come up empty and both report
`unattributed`. `workspace-healthy` has no failing check to attribute.
Searching by file misleads only when one file was written more than once,
which is the one condition the trap trace arranges and every real session
satisfies.

</details>

<details>
<summary>Hint 3: read the wrong answer closely</summary>

The starter's attribution names `retries` while the diagnosis row it sits
in names `chunk_size`. A report that contradicts itself in two adjacent
fields is the shape this class of bug takes: the search and the question
were about different things.

</details>

## Solution walkthrough

The fix adds one condition and threads one argument. What it buys is the
difference between "the trace mentions this file" and "the trace records
this value being replaced", which is the only claim an evidence-based
repair can rest on. The unattributed branch is worth leaving alone
deliberately: `trace-scoped.jsonl` is not a corrupt file or a missing
one, it is a well-formed log of a session that really happened, and it
still cannot answer this question, because logging was scoped to
directories rather than to the state anyone would later need to explain.
[Project 04](../../../../projects/project-04-runtime-feedback-and-scope-control/)
takes the same care with scope in the other direction: its `kb` commands
log on write surfaces and stay silent on read surfaces, so the log's
contents are predictable. Cross-track note: both tracks read the trace
line by line and skip blanks, and the TypeScript track splits on
`/\r?\n/` so a CRLF trace would grade identically.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-11-why-observability-belongs-inside-the-harness/exercises/exercise-01-trace-attribution -->
```text
starter/python: exit 1 (as intended: diverges at $.diagnosis[0].attribution: 'event 6 recorded step 5 setting retries in config/app.conf from 1 to 3' != 'event 5 recorded step 4 setting chunk_size in config/app.conf from 512 to 0')
starter/typescript: exit 1 (as intended: diverges at $.diagnosis[0].attribution: 'event 6 recorded step 5 setting retries in config/app.conf from 1 to 3' != 'event 5 recorded step 4 setting chunk_size in config/app.conf from 512 to 0')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
