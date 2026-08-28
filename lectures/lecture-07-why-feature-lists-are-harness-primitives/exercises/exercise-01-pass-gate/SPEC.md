# SPEC: exercise-01 pass-gate

The harness side of a feature list. An agent never edits a status; it
submits a transition request, and this gate decides against the list's
state machine. The lecture's claim is that a feature list is a primitive
because components execute against it; the gate is the component that
makes `passing` mean "the verification command passed" and nothing
weaker.

## CLI surface

```text
main <feature_list.json> <request.json>
```

`feature_list.json` is a canonical feature list
(`library/templates/feature_list.schema.json`). `request.json` is
`{"feature": <id>, "to": <status>, "evidence"?: {"command", "observed",
"date"}}`.

## The rules (evaluated in this order)

| Rule | Decision | Reason string |
| --- | --- | --- |
| the feature is `passing` | refused | `passing is final: <id> cannot leave passing` |
| `not-started` or `blocked` to `in-progress`, another feature already `in-progress` | refused | `WIP limit: <other-id> is already in-progress` (the first such feature in list order) |
| `not-started` or `blocked` to `in-progress`, none in progress | allowed | `WIP=1 holds: no other feature in-progress` |
| `in-progress` to `blocked` | allowed | `blocked is reachable from in-progress` |
| `in-progress` to `passing`, no `evidence` in the request | refused | `no evidence recorded; passing requires evidence` |
| `in-progress` to `passing`, `evidence.command` differs from the feature's `verification` | refused | `evidence command '<command>' does not match verification '<verification>'` |
| `in-progress` to `passing`, `evidence.observed` does not start with `exit 0` | refused | `evidence records a failing run ('<observed>'), not a pass` |
| `in-progress` to `passing`, evidence matches and records a pass | allowed | `evidence matches the verification command (<verification>)` |
| any other pair | refused | `illegal transition: <from> -> <to>` |

## Output

```json
{ "feature": "cart", "from": "in-progress", "to": "passing", "decision": "allowed", "reason": "..." }
```

`decision` is `allowed` or `refused`; `from` is the feature's current
status in the list. The gate reports; it never rewrites the list.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | allowed |
| 1 | refused; the reason is on stdout |
| 2 | usage error, unreadable input, or a request naming a feature the list does not contain; stdout empty |

## Fixtures

- `lists/fresh/feature_list.json`: four features, all `not-started`.
- `lists/mid-task/feature_list.json`: `auth` `passing` with evidence,
  `cart` `in-progress`, `payments` `blocked`, `csv-export` `not-started`.
  Both lists validate against the canonical schema.
- `requests/`: `start-csv-export.json` (to `in-progress`; allowed on the
  fresh list, refused on `mid-task` by WIP=1), `pass-cart-verified.json`
  (evidence from `./verify.sh cart` recording `exit 0`),
  `pass-cart-foreign.json` (evidence from `echo done`: the trap),
  `pass-cart-failing.json` (the right command, a recorded `exit 1`),
  `pass-cart-bare.json` (no evidence), `resume-auth.json` (`auth` back to
  `in-progress`).

## Starter state (the intended failure)

The state machine, WIP=1, and finality are all correct. The passing
branch is naive: any recorded evidence is accepted, with the reason
`evidence recorded`, and nothing asks what command produced it or what it
showed. Verification fails first on `pass-cart-verified` at
`$.reason: 'evidence recorded' != 'evidence matches the verification command (./verify.sh cart)'`
(the verdict is right, the gate's stated grounds are not); then
`pass-cart-foreign` and `pass-cart-failing` both exit 0 where the
expected verdict is refused, exit 1: an `echo done` and a recorded test
failure each get a feature marked passing. The starter must run cleanly
and fail only by producing that wrong reason and those two wrong
verdicts.

## Expected output

| Case | List | Request | Expected | Exit |
| --- | --- | --- | --- | --- |
| `start-work` | fresh | `start-csv-export` | `expected/start-work.json` | 0 |
| `wip-limit` | mid-task | `start-csv-export` | `expected/wip-limit.json` | 1 |
| `pass-cart-verified` | mid-task | `pass-cart-verified` | `expected/pass-cart-verified.json` | 0 |
| `pass-cart-foreign` | mid-task | `pass-cart-foreign` | `expected/pass-cart-foreign.json` | 1 |
| `pass-cart-failing` | mid-task | `pass-cart-failing` | `expected/pass-cart-failing.json` | 1 |
| `passing-is-final` | mid-task | `resume-auth` | `expected/passing-is-final.json` | 1 |
| `no-evidence` | mid-task | `pass-cart-bare` | `expected/no-evidence.json` | 1 |
| `usage` | mid-task | (none) | stdout empty | 2 |
