# SPEC: claim-gate

Two surfaces over one workspace contract: `session`, the scripted session
that declares done, and `gate`, the evidence gate that re-executes the
declaration's checks. The demo is the divergence between the two.

## CLI surface

```text
main session <workspace-dir>     # the premature declaration
main gate <workspace-dir>        # the re-execution of its claim
```

A workspace is a directory carrying `checks.json` (below) plus the files
the checks probe.

## The workspace contract (`checks.json`)

```json
{
  "task": "...",
  "checks": [ { "id", "layer", "cost", "kind", ...kind fields } ]
}
```

`layer` is `static`, `tests`, or `system` (descriptive here; exercise 02
makes it load-bearing). `cost` is the step price of executing the check.
`kind` selects one of four executable probes, the deterministic stand-in
for running a real command (the plug point where a shell would sit in a live
harness):

| kind | fields | passes when | detail strings (pass / fail) |
| --- | --- | --- | --- |
| `file-exists` | `path` | the file exists | `<path> present` / `<path> missing` |
| `file-has-line` | `path`, `prefix` | some line starts with the prefix | `<path> has a line starting with <prefix>` / `<path> has no line starting with <prefix>`, or `<path> missing` |
| `file-lacks-marker` | `path`, `marker` | the file exists and lacks the marker | `<path> carries no <marker> marker` / `<path> contains <marker>`, or `<path> missing` |
| `values-agree` | `left{path,key}`, `right{path,key}` | both `key=value` reads exist and agree | `<lp> <lk>=<v> matches <rp> <rk>=<v>` / `<lp> <lk>=<a> but <rp> <rk>=<b>`, or `<path> missing`, or `<path> has no <key>= line` |

Key reads take the first line starting `<key>=`; the value is the rest of
that line, trimmed. Implementations treat LF and CRLF alike as line
separators (see docs/conventions.md, semantic rules).

## The session (the declaration, pinned)

The scripted session replays three fixed implementation events, then
reaches its completion decision with a **check budget of 4** steps. It
walks the declared checks in order:

- if `cost <=` the remaining budget, it **executes** the check (spending
  the cost) and records the result;
- otherwise it **predicts** a pass at zero cost: the code it just wrote
  looks right, so the check surely would too.

If every executed check passed, it declares done; the claim lists every
check as `{"id", "status", "basis": "executed" | "predicted"}`. Output:
`{"workspace", "task", "check_budget", "events": [{"step", "action",
"outcome"}], "claim": {"done", "checks", "executed", "predicted"}}`. Exit
0 when the session declared done, 1 when an executed check failed (never
reached on the committed fixtures: both workspaces pass the two checks
the budget affords). The session's exit code reports only that the
session ran to its declaration; by design it carries no information about
whether the claim is true.

On the committed fixtures the session executes 2 checks (static and
tests, both green) and predicts 3 (the system layer), then declares done
in **both** workspaces. The two pinned transcripts differ only in the
`workspace` field: from inside the session, the premature claim and the
earned one are indistinguishable.

## The gate (the re-execution)

`gate` replays the session to obtain the claim, then re-executes every
claimed check through the same engine and compares claim to check.
Output: `{"workspace", "claim": {"done", "green", "executed",
"predicted"}, "reexecution": [{"id", "layer", "claimed", "basis",
"actual", "detail", "verdict"}], "verdict": {"divergences", "result"}}`.
`verdict` per row is `confirmed` when `actual` equals `claimed`,
`diverged` otherwise; `result` is `earned` when no row diverged,
`premature` otherwise. If the session declares no completion, there is
nothing to audit: exit 2 (not reached on the committed fixtures).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `session`: ran to a done declaration. `gate`: every claimed check reproduced (`earned`) |
| 1 | `session`: an executed check failed, no claim. `gate`: at least one claimed check failed re-execution (`premature`) |
| 2 | usage error, `<workspace-dir>` not a directory or lacking `checks.json`, or a gate over a session that declares nothing; stdout empty |

## Fixtures and seeded symptoms

Both workspaces declare the same five checks over the same task. The
session's budget covers `todo-markers-cleared` (static, cost 1) and
`unit-exporter-green` (tests, cost 2); both pass in both workspaces, so
the claim is locally honest everywhere.

`workspaces/workspace-premature` seeds three gaps, all in the predicted
system layer, each caught by the gate's re-execution with the exact
detail string:

| Seeded gap | Caught by | Detail |
| --- | --- | --- |
| `config/app.conf` has no `export_dir=` line | `config-export-dir` | `config/app.conf has no line starting with export_dir=` |
| migration recorded through 2 while the schema says 3 | `migration-applied` | `db/schema.version version=3 but db/applied.txt applied=2` |
| the end-to-end flow never ran | `e2e-export-ran` | `logs/e2e-export.log missing` |

`workspaces/workspace-earned` closes all three gaps; the same gate run
confirms all five rows and exits 0. The `gate-premature-diverges` case
(exit 1) and the `gate-earned-confirms` case (exit 0) pin the pair.
