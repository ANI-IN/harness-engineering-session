# SPEC: failure-triage

Attributes agent-run failures to harness subsystems by applying mechanical
rules to a transcript of observable events. Both tracks implement this
contract; `expected/` is the grading authority.

## CLI surface

```text
main <transcript.jsonl>
```

The transcript is JSONL: one event object per line (blank lines ignored;
LF and CRLF both accepted per the repository's input rule). Every event has:

| Field | Meaning |
| --- | --- |
| `run` | run identifier; events of a run appear in execution order |
| `type` | `task`, `agent_question`, `shell_error`, `rework`, `verification`, `claim`, or `outcome` |
| `detail` | human-readable payload of the event |
| `result` | only on `verification`: `pass` or `fail` |

A run's first `task` event carries its task description.

## Attribution rules

For each run, scan events in order; the **first** event matching any rule
attributes the run and scanning stops. Rules are checked in this order:

| Subsystem | Rule id | Matches |
| --- | --- | --- |
| instructions | `asked-for-repo-fact` | any `agent_question` event (the agent had to ask a human for something the repository should have answered) |
| tools | `command-unavailable` | `shell_error` whose detail contains `command not found` or `permission denied` |
| environment | `dependency-or-runtime-missing` | `shell_error` whose detail contains `ModuleNotFoundError`, `Cannot find module`, or `version` |
| state | `repeated-prior-work` | any `rework` event |
| feedback | `claim-without-passing-verification` | a `claim` event with no earlier `verification` event with `result: "pass"` in the same run |

A run matching no rule is `unattributed` (a healthy run).

## Output

A JSON report on stdout:

```json
{
  "runs": [
    { "id": "...", "task": "...", "subsystem": "...", "rule": "...", "evidence": "..." }
  ],
  "summary": { "instructions": 0, "tools": 0, "environment": 0, "state": 0, "feedback": 0, "unattributed": 0 },
  "total_runs": 0,
  "harness_failure_rate": 0
}
```

- `runs` is ordered by each run's first appearance in the transcript.
- `evidence` is exactly `<type>: "<detail>"` of the attributing event;
  `rule` and `evidence` are `null` for unattributed runs.
- `summary` always contains all six keys.
- `harness_failure_rate` is attributed runs divided by total runs (IEEE 754
  division; 5/6 must serialize as 0.8333333333333334), and the number 0 when
  the transcript has no runs.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted (including an empty transcript) |
| 1 | malformed transcript: a non-JSON line or an event missing `run`/`type`/`detail`; stdout empty, diagnostic on stderr names the line number |
| 2 | usage error or unreadable file; stdout empty |

## Expected output

- `basic` case: `fixtures/runs.jsonl` → `expected/triage-report.json` (six
  runs, one per subsystem plus one healthy).
- `empty-transcript` case: `fixtures/empty.jsonl` → `expected/empty-report.json`.
- `malformed-line` case: `fixtures/malformed.jsonl` → exit 1 (the seeded
  defect: line 2 is not JSON; the parse stage catches it in both tracks with
  the same exit code and an empty stdout).
